"""Timeline analysis service — AI-powered timeline generation and event confirmation.

Extracted from ``timeline_service.py`` (AD-5) to separate CRUD concerns
from AI analysis. This service calls the TimelineAgent to produce
chronological timeline analysis with conflict and gap detection.

Temporal expression extraction (``extract_temporal_expressions``,
``stream_extraction``) moved to ``timeline_extraction_service.py``
to keep files under the 300-line limit (RULE-04).

Prompt resolution is Mode 1 (composer-driven) per ADR-049 FIND-011 / D9:
the service resolves its system prompt via
``PromptComposer.build(LLMIntent.PLAN, mode="timeline")`` and passes the
composed system prompt to the ``TimelineAgent`` constructor. The previous
inline f-string feature prompt and the premature ADR-048 Mode 2
``_TIMELINE_ANALYSIS_INJECTION`` declaration were removed (ADR-049 D10).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

Model acquisition (ADR-086 L22): the per-user PLAN routing cascade is
injected as a ``ModelResolution`` and resolved on first use inside
``generate_timeline`` — after the uid-scoped novel guard, never at
construction (the eager factory resolved at wiring time). Graceful
degradation is entry-point policy: a missing provider is logged
(``no_ai_provider_configured``) and the preserved ``NO_AI_PROVIDER``
outcome fires exactly as it did when the eager factory swallowed this
error at wiring time. The non-AI ``confirm_extracted_event`` path never
resolves. Prompt-context assembly lives in
``_timeline_analysis_support.py`` (RULE-04 split for this slice).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.planning._timeline_analysis_support import build_prompt_context
from narrare.planning._timeline_chapter_context import format_chapter_context
from narrare.planning._timeline_extraction_helpers import persist_extracted_event
from narrare.planning.schemas import TimelineEventResponse, TimelineResponse
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.planning.timeline_schemas import TimelineEventCRUDResponse
    from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class TimelineAnalysisService:
    """Service for AI-powered chronological timeline analysis.

    Generates a structured timeline via the TimelineAgent and persists
    confirmed extracted expressions as timeline events.

    The timeline prompt is resolved through ``PromptComposer`` in Mode 1
    (ADR-049 FIND-011 / D9): the governed
    ``_bundled/planning/en/timeline/system.md`` template carries the task
    framing, project metadata, and KB context variables; chapter summaries
    are supplied as a template variable; the chapter data additionally
    flows as the agent run prompt (runtime data, RULE-02a category 3). No
    inline f-string feature prompt is assembled in the service
    (RULE-02 / RULE-02a).

    Args:
        novel_repo: For novel metadata (genre, language).
        chapter_repo: For listing chapters and their summaries.
        model_registry: Shared LLM model registry.
        model_resolution: Lazy per-user model resolution (ADR-086 L22) —
            the PLAN routing cascade resolves on first use, never at
            construction. A ``ConfigurationError`` (no AI provider) is
            degraded at the entry point (AI-optional policy).
        composer: PromptComposer for resolving the governed timeline system
            prompt via the cascade (RULE-02b / ADR-049 D9). Required for
            ``generate_timeline``.
        event_repo: For persisting confirmed extracted events.
        kb_context_provider: Canonical KB-context provider (ADR-067) for the
            ``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
            ``kb_relationships`` prompt variables. When ``None`` or when the
            KB is empty, all four degrade to empty strings (RULE-11) so the
            template still composes. Provenance is rendered inline
            (``RenderOptions(annotate_provenance=True)``) so planning gets the
            same honest KB rendering as writing (FIND-017).
        invocation_pipeline: Retained for DI-contract stability. Per ADR-049
            D10 the premature ADR-048 Mode 2 ``ManualInjectionDeclaration``
            was removed; Mode 1 evidence adoption is deferred (the sibling
            ``KBConsistencyAnalyzer`` operates without a pipeline call, which
            is the pattern followed here).
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        event_repo: TimelineEventRepository | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        # Resolved triple — unset until first use; a failed (graceful)
        # resolve leaves it unset for the instance's lifetime.
        self._config: ResolvedModelConfig | None = None
        self._api_key: str | None = None
        self._base_url: str | None = None
        self._resolve_attempted = False
        self._composer = composer
        self._event_repo = event_repo
        self._kb_context_provider = kb_context_provider
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> None:
        """Resolve the per-user PLAN routing cascade once (ADR-086 L22).

        First call awaits the injected ``ModelResolution`` and caches the
        resolved triple into ``_config``/``_api_key``/``_base_url``; repeat
        calls are idempotent — the cascade runs at most once per instance,
        success or failure (eager-world timing also resolved exactly once
        per request). ``ConfigurationError`` propagates UNCHANGED: the
        graceful swallow is entry-point policy (see
        :meth:`generate_timeline`), so this method stays honest about
        what happened (RULE-11).
        """
        if self._resolve_attempted:
            return
        self._resolve_attempted = True
        resolved = await self._model_resolution.resolve()
        self._config = resolved.config
        self._api_key = resolved.api_key
        self._base_url = resolved.base_url

    async def generate_timeline(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TimelineResponse:
        """Generate a chronological timeline analysis for a novel.

        Gathers all chapters with their summaries, builds a timeline
        prompt, and runs the TimelineAgent.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.

        Returns:
            Timeline analysis with events, conflicts, and gaps.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no AI provider is configured (the
                preserved degraded outcome; ADR-086 L22 graceful entry
                policy), the PromptComposer is missing, or prompt
                composition fails (RULE-11).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # ADR-086 L22: first-use lazy resolve — the uid-scoped novel guard
        # above stays ahead of the cascade (eager-world precedence; the
        # ADR-086 planning guard ruling). Degradation is entry-point
        # policy: a missing AI provider is logged (the eager factory's
        # event, byte-identical) and leaves the triple unset, so the
        # preserved ``NO_AI_PROVIDER`` outcome below fires exactly as it
        # did when the eager factory swallowed this error at wiring time —
        # timing only. The resolve is attempted at most once per instance.
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

        # Guard: no AI provider configured — cannot generate timeline
        if self._config is None:
            raise ConfigurationError(
                "No AI provider configured. Configure one in Settings to use timeline analysis.",
                code="NO_AI_PROVIDER",
            )

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail loudly
            # (RULE-11) rather than silently falling back to inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for timeline analysis.",
                code="NO_COMPOSER",
            )

        # Gather chapters with summaries
        chapters = await self._chapter_repo.list_by_novel(novel_id)

        language = novel.writing_language or "en"

        # Runtime imports kept local to match this module's existing import
        # convention (see TimelineAgent import below) and avoid any module-load
        # circular-import risk.
        from narrare_core.llm.intents import LLMIntent

        # Prompt-context assembly (chapter summaries, canonical KB context
        # ADR-067, confirmed events) — extracted to
        # ``_timeline_analysis_support.py`` (RULE-04 split, ADR-086 L22).
        ctx = await build_prompt_context(
            novel=novel,
            chapters=chapters,
            language=language,
            novel_id=novel_id,
            event_repo=self._event_repo,
            kb_context_provider=self._kb_context_provider,
        )
        composed = await self._composer.build(LLMIntent.PLAN, ctx)

        from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps

        # Task 6b single assembly point: coherent (model, model_settings, usage_limits) triple.
        resolved = self._run_limit_resolver.resolve(
            config=self._config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._registry.prepare(
            self._config,
            intent=LLMIntent.PLAN,
            usage_limits=resolved.usage_limits,
            api_key=self._api_key,
            base_url=self._base_url,
        )

        # Build deps
        deps = TimelineDeps(
            genre=novel.genre or "",
            language=language,
        )

        # pydantic-ai binds ``system_prompt`` at agent construction, so the
        # composed system prompt is supplied to the constructor (not to
        # ``run()``). Chapter data flows as the run prompt (user channel);
        # when the template has no "## First Message" the compact chapter
        # summary context IS the run prompt (same derivation the context
        # assembly in ``_timeline_analysis_support`` performs).
        agent = TimelineAgent(model=prepared.model, system_prompt=composed.system)
        result = await agent.run(
            prompt=composed.user or format_chapter_context(chapters),
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        # Map core output to API response
        return TimelineResponse(
            timeline_events=[
                TimelineEventResponse(**e.model_dump()) for e in result.timeline_events
            ],
            temporal_conflicts=result.temporal_conflicts,
            coverage_gaps=result.coverage_gaps,
            overall_assessment=result.overall_assessment,
        )

    async def confirm_extracted_event(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        extracted: ExtractedTemporalExpression,
    ) -> TimelineEventCRUDResponse:
        """Convert a confirmed extracted expression into a timeline event.

        Delegates to
        :func:`narrare.planning._timeline_extraction_helpers.persist_extracted_event`
        (RULE-04 split; deps passed explicitly).
        """
        return await persist_extracted_event(
            novel_repo=self._novel_repo,
            event_repo=self._event_repo,
            kb_context_provider=self._kb_context_provider,
            novel_id=novel_id,
            user_id=user_id,
            extracted=extracted,
        )
