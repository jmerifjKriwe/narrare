"""Consistency checker service — orchestrates consistency analysis.

Orchestrates: validate → collect context → staged pipeline or legacy
single-pass → map to API response.

Updated for ADR-044: delegates to ``ConsistencyOrchestrator`` for the
two-stage pipeline (FactExtractor → ConsistencyAgent) when an orchestrator
is injected. Falls back to legacy single-pass when no orchestrator is provided,
preserving the external ``ConsistencyCheckerProtocol`` interface unchanged.

ADR-086 L13: model routing resolves at FIRST USE (``ensure_resolved``),
never at construction — the entry points resolve only AFTER the uid-scoped
novel ownership gate in ``collect_check_context`` (gate-before-resolution),
so request-body validation errors surface as 422 before any routing
cascade runs, and ``ConfigurationError`` propagates loudly (RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.consistency.checker_context import collect_check_context
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.contracts import ConsistencyOrchestratorProtocol
    from narrare.consistency.stage_schemas import ConsistencyStageEvent
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.settings.token_limits.protocols import TokenLimitsServiceProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class ConsistencyCheckerService:
    """Implements ConsistencyCheckerProtocol.

    Orchestrates: validate → collect chapters + KB + timeline → build deps
    → run staged pipeline or legacy single-pass → map response.

    When an orchestrator is provided, uses the ADR-044 two-stage pipeline.
    Otherwise, falls back to legacy single-pass ConsistencyAgent invocation.

    Args:
        chapter_repo: Chapter persistence (fetch chapter content).
        novel_repo: Novel persistence (access control + language).
        kb_repo: KB persistence (fetch entity summaries for context).
        timeline_repo: Timeline event persistence (temporal context).
        relationship_repo: Optional KB relationship persistence. When provided
            and ``include_kb`` is set, relationships are fetched for
            relationship-aware consistency checking (FIND-001). Degrades
            gracefully to empty string when ``None``.
        registry: ModelRegistry for LLM model resolution.
        consistency_resolution: Lazy CONSISTENCY cascade (ADR-086 L13) —
            resolves at first use; backs the legacy single-pass config.
        composer: PromptComposer for system prompt assembly.
        token_limits_service: Optional TokenLimitsService for dynamic limit resolution.
        orchestrator: Optional ConsistencyOrchestrator for staged pipeline.
        invocation_pipeline: Optional InvocationPipeline for evidence recording.
    """

    def __init__(
        self,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        timeline_repo: TimelineEventRepository,
        registry: ModelRegistry,
        consistency_resolution: ModelResolution,
        composer: PromptComposer,
        relationship_repo: RelationshipRepository | None = None,
        token_limits_service: TokenLimitsServiceProtocol | None = None,
        orchestrator: ConsistencyOrchestratorProtocol | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._timeline_repo = timeline_repo
        self._relationship_repo = relationship_repo
        self._registry = registry
        self._consistency_resolution = consistency_resolution
        self._composer = composer
        self._token_limits_service = token_limits_service
        self._orchestrator = orchestrator
        self._invocation_pipeline = invocation_pipeline
        # Legacy triple — populated at first use (ADR-086 L13).
        self._config: ResolvedModelConfig | None = None
        self._api_key: str | None = None
        self._base_url: str | None = None

    async def ensure_resolved(self) -> None:
        """Resolve model routing at first use (ADR-086 L13). Idempotent.

        With the staged orchestrator, BOTH cascades (FACT_EXTRACT +
        CONSISTENCY, the eager factory's verbatim order) resolve through
        the orchestrator's composition — the legacy triple mirrors its
        composed CONSISTENCY stage. Without an orchestrator (legacy-only
        wiring), only the CONSISTENCY cascade resolves, passed through
        unchanged (the override policy lives with the composed staged
        wiring). ``ConfigurationError`` propagates loudly (RULE-11).
        """
        if self._config is not None:
            return
        if self._orchestrator is not None:
            composed = await self._orchestrator.ensure_resolved()
            self._config = composed.consistency_config
            self._api_key = composed.consistency_api_key
            self._base_url = composed.consistency_base_url
            return
        resolved = await self._consistency_resolution.resolve()
        self._config = resolved.config
        self._api_key = resolved.api_key
        self._base_url = resolved.base_url

    async def check(
        self,
        *,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check on the requested scope.

        Uses staged pipeline when orchestrator is available (ADR-044).
        Falls back to legacy single-pass otherwise.

        Args:
            novel_id: The novel to analyze.
            user_id: The user requesting analysis (for access control).
            request: Check parameters (check types, chapter scope, KB inclusion).

        Returns:
            Consistency response with issues grouped by severity and type.

        Raises:
            NotFoundError: If novel does not exist or user lacks access.
        """
        logger.info(
            "consistency_check_start",
            novel_id=str(novel_id),
            chapter_count=len(request.chapter_ids),
            include_kb=request.include_kb,
            staged=self._orchestrator is not None,
        )

        context = await collect_check_context(
            novel_id,
            user_id,
            request,
            chapter_repo=self._chapter_repo,
            novel_repo=self._novel_repo,
            kb_repo=self._kb_repo,
            timeline_repo=self._timeline_repo,
            relationship_repo=self._relationship_repo,
            token_limits_service=self._token_limits_service,
            include_timeline_envelopes=self._orchestrator is not None,
        )

        # ADR-086 L13: first-use resolution runs AFTER the ownership gate
        # (gate-before-resolution) and BEFORE any agent invocation.
        await self.ensure_resolved()

        if self._orchestrator is not None:
            # Staged pipeline via orchestrator (ADR-044).
            return await self._orchestrator.run_staged_check(
                novel_id=novel_id,
                deps=context.deps,
                kb_summaries=context.kb_summaries,
                timeline_envelopes=context.timeline_envelopes,
                language=context.language,
                max_chapter_tokens=context.max_chapter_tokens,
            )

        # Legacy single-pass — delegates to
        # narrare.consistency.legacy_check_runner.run_legacy_check
        # (RULE-04 extraction).
        from narrare.consistency.legacy_check_runner import run_legacy_check

        assert self._config is not None  # ensure_resolved ran above
        return await run_legacy_check(
            registry=self._registry,
            config=self._config,
            composer=self._composer,
            novel_id=novel_id,
            context=context,
            invocation_pipeline=self._invocation_pipeline,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def check_chapter(
        self,
        *,
        novel_id: uuid.UUID,
        chapter_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check focused on a single chapter.

        Delegates to ``check()`` with the chapter_id injected into a
        scoped request.

        Args:
            novel_id: The novel containing the chapter.
            chapter_id: The chapter to analyze.
            user_id: The user requesting analysis.
            request: Check parameters.

        Returns:
            Consistency response scoped to the single chapter.

        Raises:
            NotFoundError: If novel or chapter does not exist.
        """
        scoped_request = ConsistencyRequest(
            chapter_ids=[chapter_id],
            check_types=request.check_types,
            include_kb=request.include_kb,
        )
        return await self.check(
            novel_id=novel_id,
            user_id=user_id,
            request=scoped_request,
        )

    async def stream_check(
        self,
        *,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConsistencyRequest,
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        """Stream staged consistency check with progressive results (RULE-13).

        Only available when orchestrator is injected. Yields stage events
        then the final ConsistencyResponse.

        Args:
            novel_id: The novel to analyze.
            user_id: The user requesting analysis.
            request: Check parameters.

        Yields:
            ConsistencyStageEvent for progress, then final ConsistencyResponse.

        Raises:
            NotFoundError: If novel does not exist or user lacks access.
            RuntimeError: If no orchestrator is configured.
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "Streaming consistency check requires an orchestrator. "
                "Inject ConsistencyOrchestrator via deps.py."
            )

        context = await collect_check_context(
            novel_id,
            user_id,
            request,
            chapter_repo=self._chapter_repo,
            novel_repo=self._novel_repo,
            kb_repo=self._kb_repo,
            timeline_repo=self._timeline_repo,
            relationship_repo=self._relationship_repo,
            token_limits_service=self._token_limits_service,
            include_timeline_envelopes=True,
        )

        # ADR-086 L13: first-use resolution runs AFTER the ownership gate
        # (gate-before-resolution) and BEFORE any stage event is emitted;
        # the SSE router additionally resolves pre-header (Decision 3).
        await self.ensure_resolved()

        async for event in self._orchestrator.stream_staged_check(
            novel_id=novel_id,
            deps=context.deps,
            kb_summaries=context.kb_summaries,
            timeline_envelopes=context.timeline_envelopes,
            language=context.language,
            max_chapter_tokens=context.max_chapter_tokens,
        ):
            yield event
