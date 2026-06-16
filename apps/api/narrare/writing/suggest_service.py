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

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
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
        api_key: Optional API key override for the LLM provider.
        base_url: Optional base URL override for the LLM provider.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._config = config
        self._chapter_repo = chapter_repo
        self._api_key = api_key
        self._base_url = base_url

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
        status codes instead of causing RuntimeError after headers are sent.

        Raises:
            ValidationError: If text_before is empty or whitespace-only.
            NotFoundError: If the chapter does not exist.
        """
        if not request.text_before.strip():
            raise ValidationError(
                "text_before must not be empty",
                code="MISSING_INPUT",
            )

        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

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

        The prompt context includes the user's ``text_before`` as the
        primary completion trigger, ``text_after`` for forward context,
        and minimal chapter metadata (title, POV).

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
            narrare_core.shared.errors.PromptNotFoundError: If no prompt
                file exists for ``LLMIntent.SUGGEST``.
        """
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
            author_instructions=request.text_before,
            extra={
                "user_id": str(user_id),
                "chapter_id": str(chapter_id),
                "text_after": request.text_after or "",
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
