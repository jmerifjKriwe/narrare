"""Inline suggest service — lightweight ghost-text suggestion engine.

This service provides inline suggestions (ghost text) for the TipTap editor.
Unlike the main :class:`WritingService`, it has no pipeline, no graph, no
multi-step generation.  It directly:

- Uses :class:`PromptComposer` to build a ``SUGGEST`` prompt
- Uses :class:`ModelRegistry` to stream a short completion (max 60 tokens)
- Validates chapter access before streaming
- Assembles minimal chapter context (title, POV) for prompt enrichment

Model acquisition is LAZY (ADR-086): the factory wires a
``LazyModelResolution`` (SUGGEST cascade, user scope); the service
resolves it on first use — :meth:`ensure_resolved` at the end of
:meth:`validate_suggest` (the router's pre-stream seam) and after the
ownership gate in :meth:`suggest_inline` — so request validation and the
IDOR gate stay ahead of resolution and an unconfigured provider surfaces
as a loud 400 before any SSE headers exist. The eager factory's sampling
composition (``replace(config, temperature=0.3,
max_tokens=SUGGEST_MAX_TOKENS)``) is reproduced exactly once at first
use — WHAT unchanged, only WHEN.

Implements :class:`SuggestServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._suggest_support import build_chapter_context, track_request
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.schemas import InlineSuggestRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.llm.result import StreamChunk
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Eager-factory sampling overrides for the SUGGEST intent, now composed
# at the service's first use (ADR-086 L36 — timing-only migration).
_SUGGEST_TEMPERATURE: float = 0.3


class InlineSuggestService:
    """Lightweight ghost-text suggestion service (DI, RULE-07).

    Provides inline completions for the TipTap editor.  Uses composer
    and registry directly — no pipeline, no graph overhead.

    Args:
        registry: LLM model registry for streaming completions.
        composer: Prompt composer for SUGGEST intent prompts.
        model_resolution: Lazy per-user model resolution (ADR-086) —
            the SUGGEST routing cascade resolves on first use, never
            at construction; the suggest sampling overrides are
            composed onto the resolved config at that same first use.
        chapter_repo: Chapter repository for access validation and context.
        novel_repo: Novel repository for the chapter-ownership gate (IDOR S6).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        model_resolution: ModelResolution,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user SUGGEST routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        composes the effective suggest config — the eager factory's
        ``replace(resolved.config, temperature=0.3,
        max_tokens=SUGGEST_MAX_TOKENS)`` — caching the composed triple;
        repeat calls return the cache without re-running the cascade.
        Errors propagate uncached (RULE-11): ``ConfigurationError``
        (``NO_AI_PROVIDER``) surfaces as a pre-header 400 on this SSE
        endpoint.
        """
        if self._resolved is None:
            resolved = await self._model_resolution.resolve()
            self._resolved = replace(
                resolved,
                config=replace(
                    resolved.config,
                    temperature=_SUGGEST_TEMPERATURE,
                    max_tokens=SUGGEST_MAX_TOKENS,
                ),
            )
        return self._resolved

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
        sent.  Ownership runs FIRST (IDOR S6), the lazy routing cascade
        resolves LAST (ADR-086) — so validation and ownership failures
        keep precedence over an unconfigured provider's 400, and that
        400 itself still fires before any SSE headers are sent.

        Raises:
            ValidationError: If text_before is empty or whitespace-only.
            NotFoundError: If the chapter does not exist or its novel
                belongs to another user.
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use resolve).
        """
        if not request.text_before.strip():
            raise ValidationError(
                "text_before must not be empty",
                code="MISSING_INPUT",
            )

        await self._verify_chapter_ownership(chapter_id, user_id)

        # ADR-086 L36: first-use lazy resolve — AFTER text validation and
        # the ownership gate (gates stay ahead of resolution) and BEFORE
        # the router constructs the StreamingResponse, so an unconfigured
        # provider stays a loud pre-header 400, never a mid-stream error.
        await self.ensure_resolved()

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
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use resolve).
        """
        # Ownership gate FIRST (IDOR S6): foreign ≡ unknown 404s before
        # rate-limit tracking, prompt building, or chapter-metadata
        # enrichment — a foreign chapter's title/POV must never reach
        # the prompt (GAP-MINOR metadata leak).
        await self._verify_chapter_ownership(chapter_id, user_id)

        # ADR-086 L36: first-use lazy resolve (idempotent — the router's
        # pre-stream validate_suggest call already resolved on this
        # request; direct callers resolve here, after the gate).
        resolved = await self.ensure_resolved()

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
        track_request(chapter_id, user_id)

        # Load minimal chapter context for prompt enrichment.
        chapter_context = await build_chapter_context(self._chapter_repo, chapter_id)

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
            config=resolved.config,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        ):
            yield chunk
