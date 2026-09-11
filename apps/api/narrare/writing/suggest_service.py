"""Inline suggest service — lightweight ghost-text suggestion engine.

This service provides inline suggestions (ghost text) for the TipTap editor.
Unlike the main :class:`WritingService`, it has no pipeline, no graph, no
multi-step generation.  It directly:

- Uses :class:`PromptComposer` to build a ``SUGGEST`` prompt
- Uses :class:`ModelRegistry` to stream a short completion (max 60 tokens)
- Validates chapter access before streaming
- Assembles minimal chapter context (title, POV) for prompt enrichment

Implements :class:`SuggestServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.schemas import InlineSuggestRequest
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.result import StreamChunk
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Soft rate limiting: minimum interval between requests per chapter.
# Non-blocking — logs a warning but still processes the request.
_MIN_SUGGEST_INTERVAL_S: float = 0.5

# Module-level dict for in-memory rate tracking.
# Key: "{chapter_id}:{user_id}", Value: monotonic timestamp of last request.
_last_request_time: dict[str, float] = {}


class InlineSuggestService:
    """Lightweight ghost-text suggestion service (DI, RULE-07).

    Provides inline completions for the TipTap editor.  Uses composer
    and registry directly — no pipeline, no graph overhead.

    Args:
        registry: LLM model registry for streaming completions.
        composer: Prompt composer for SUGGEST intent prompts.
        config: Resolved model configuration (temperature, max_tokens).
        chapter_repo: Chapter repository for access validation and context.
        novel_repo: Novel repository for the chapter-ownership gate (IDOR S6).
        api_key: Optional API key override for the LLM provider.
        base_url: Optional base URL override for the LLM provider.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._config = config
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._api_key = api_key
        self._base_url = base_url

    # -- Ownership gate (IDOR S6, chapter-only path) ------------------------

    async def _verify_chapter_ownership(self, chapter_id: UUID, user_id: str) -> Chapter:
        """Load the chapter and verify its novel belongs to the caller.

        The suggest endpoint has no ``novel_id`` parameter, so the gate
        scopes by the chapter's OWN novel: chapter exists ∧
        ``novel_repo.get_by_id(chapter.novel_id, user)``.  Every failure
        raises the same ``NotFoundError`` (foreign ≡ unknown) BEFORE any
        prompt building, LLM call, or chapter-metadata enrichment.

        Raises:
            NotFoundError: If the chapter does not exist or its novel
                belongs to another user.
        """
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        novel = await self._novel_repo.get_by_id(chapter.novel_id, UUID(user_id))
        if novel is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        return chapter

    # -- Pre-validation (called before SSE starts) -------------------------

    async def validate_suggest(
        self,
        chapter_id: UUID,
        user_id: str,
        request: InlineSuggestRequest,
    ) -> None:
        """Pre-validate suggest request before starting SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 404) are returned with proper HTTP
        status codes instead of causing RuntimeError after headers are
        sent.  Ownership runs FIRST (IDOR S6).

        Raises:
            ValidationError: If text_before is empty or whitespace-only.
            NotFoundError: If the chapter does not exist or its novel
                belongs to another user.
        """
        if not request.text_before.strip():
            raise ValidationError(
                "text_before must not be empty",
                code="MISSING_INPUT",
            )

        await self._verify_chapter_ownership(chapter_id, user_id)

    # -- Public API --------------------------------------------------------

    async def suggest_inline(
        self,
        chapter_id: UUID,
        user_id: str,
        request: InlineSuggestRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Stream an inline suggestion for ghost text.

        Lightweight endpoint: no graph, no multi-step pipeline, no context
        assembly.  Uses ``LLMIntent.SUGGEST`` → ``writing/inline_suggest``
        prompt mode.  Max ~60 tokens per suggestion for low latency.

        The prompt context carries the user's ``text_before``/``text_after``
        as extra variables so the governed template renders them XML-wrapped
        in the SYSTEM channel (RULE-22 §6 injection defense).
        ``author_instructions`` is intentionally NOT set: the composer's
        fallback would pass the raw manuscript text through the user channel,
        duplicating it alongside the wrapped system copy (R2 Slice B',
        2026-09-11). ``kb_characters`` is supplied empty — lean ruling, no
        KB assembly on the <500 ms path (ADR-045 bypass, see below).

        ADR-045 Decision 3 Option C exception — intentional pipeline bypass:
            This method intentionally does NOT use ``InvocationPipeline``
            (prepare/finalize) or ``compose_invocation()``.  The pipeline
            overhead (enricher network calls for mem0 preferences, KB
            retrieval, budget resolution) exceeds the <500 ms latency
            target for inline ghost text.  The adoption registry declares
            this exception for the ``inline_suggest`` mode:

            - ``budget_resolution: none``
            - ``final_validation: optional``
            - ``evidence_sink: optional``
            - ``preference_enrichment: not_applicable``

            A lightweight log event (``inline_suggest_invocation``)
            provides observability without pipeline overhead.  If latency
            budgets improve (e.g., cached enrichers), migrate to
            ``compose_invocation()`` Mode 1 with ``invocation_pipeline``
            wired in ``deps_suggest.py``.

        Args:
            chapter_id: Chapter the user is editing (for routing context).
            user_id: Authenticated user identifier.
            request: Inline suggestion request with text_before/text_after.

        Yields:
            StreamChunk instances with incremental text.  The final chunk
            has ``is_final=True`` and populated ``usage``.

        Raises:
            narrare_core.shared.errors.NotFoundError: If the chapter does
                not exist or its novel belongs to another user (IDOR S6).
            narrare_core.shared.errors.PromptNotFoundError: If no prompt
                file exists for ``LLMIntent.SUGGEST``.
        """
        # Ownership gate FIRST (IDOR S6): foreign ≡ unknown 404s before
        # rate-limit tracking, prompt building, or chapter-metadata
        # enrichment — a foreign chapter's title/POV must never reach
        # the prompt (GAP-MINOR metadata leak).
        await self._verify_chapter_ownership(chapter_id, user_id)

        # Lightweight evidence — invocation tracked via log event (ADR-045
        # Decision 3 Option C exception for low-latency inline suggest).
        logger.info(
            "inline_suggest_invocation",
            feature_id="writing_suggest",
            intent=LLMIntent.SUGGEST.value,
            user_id=str(user_id),
            chapter_id=str(chapter_id),
            pipeline_bypass_reason="latency_target_sub_500ms",
        )

        # Soft rate-limit check (non-blocking).
        _track_request(chapter_id, user_id)

        # Load minimal chapter context for prompt enrichment.
        chapter_context = await self._build_chapter_context(chapter_id)

        ctx = PromptContext(
            language=request.language,
            mode="inline_suggest",
            extra={
                "user_id": str(user_id),
                "chapter_id": str(chapter_id),
                # SYSTEM-channel XML wrapping via the governed template
                # (<user_provided_text> blocks) — R2 Slice B'. Never map
                # text_before to author_instructions: the composer fallback
                # would leak raw manuscript text into the user channel.
                "text_before": request.text_before,
                "text_after": request.text_after or "",
                # Lean ruling (ADR-045 <500 ms bypass): no KB assembly on the
                # suggest path — the Characters section renders empty.
                "kb_characters": "",
                "chapter_context": chapter_context,
            },
        )

        prompt = await self._composer.build(
            LLMIntent.SUGGEST,
            ctx,
        )

        async for chunk in self._registry.stream(
            intent=LLMIntent.SUGGEST,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
        ):
            yield chunk

    # -- Private helpers ---------------------------------------------------

    async def _build_chapter_context(self, chapter_id: UUID) -> str:
        """Assemble minimal chapter context for prompt enrichment.

        Returns a short string with chapter title and POV (if set).
        Intentionally minimal — the full ContextAssembler is too slow
        for the <500ms latency target of inline suggestions.
        """
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            return ""

        parts: list[str] = []
        if chapter.title:
            parts.append(f"Chapter: {chapter.title}")
        if chapter.pov_character_id:
            parts.append(f"POV: {chapter.pov_character_id}")
        return "\n".join(parts)


def _track_request(chapter_id: UUID, user_id: str) -> None:
    """Track request timing for soft rate limiting (non-blocking).

    Logs a warning if requests are coming too fast but does NOT
    reject the request.  This keeps the UX responsive during
    rapid typing while providing observability for abuse detection.
    """
    now = time.monotonic()
    key = f"{chapter_id}:{user_id}"
    last = _last_request_time.get(key, 0.0)
    if last and (now - last) < _MIN_SUGGEST_INTERVAL_S:
        logger.debug(
            "suggest_rate_throttled",
            chapter_id=str(chapter_id),
            elapsed_ms=round((now - last) * 1000),
        )
    _last_request_time[key] = now
