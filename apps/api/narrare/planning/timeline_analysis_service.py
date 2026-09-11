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
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.planning._event_render import render_confirmed_events
from narrare.planning._timeline_chapter_context import format_chapter_context
from narrare.planning._timeline_extraction_helpers import persist_extracted_event
from narrare.planning.schemas import TimelineEventResponse, TimelineResponse
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

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
        model_config: Resolved model config (provider + model ID).
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
        api_key: Optional API key override.
        base_url: Optional base URL override.
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
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        event_repo: TimelineEventRepository | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._event_repo = event_repo
        self._kb_context_provider = kb_context_provider
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

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
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

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

        # Compact chapter-summary context — runtime data (RULE-02a category 3)
        # that fills ``{{chapter_summaries}}`` + the agent run prompt below.
        chapter_context = format_chapter_context(chapters)

        language = novel.writing_language or "en"

        # Runtime imports kept local to match this module's existing import
        # convention (see TimelineAgent import below) and avoid any module-load
        # circular-import risk.
        from narrare_core.context._render_options import RenderOptions
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        # Canonical KB context (ADR-067): characters/locations/factions/
        # relationships are fetched+rendered through the reusable provider
        # (the ADR-050 envelope, with provenance annotated so planning gets the
        # same honest rendering as writing — FIND-017). Degrades to empty
        # strings when no provider is wired or the KB is empty (RULE-11).
        if self._kb_context_provider is None:
            from narrare.kb.context_contracts import KBContextBundle

            kb_bundle = KBContextBundle.empty(RenderOptions(annotate_provenance=True))
        else:
            kb_bundle = await self._kb_context_provider.fetch_context(
                novel_id,
                entity_types=["character", "location", "faction"],
                options=RenderOptions(annotate_provenance=True),
            )
        kb_vars = kb_bundle.to_prompt_variables()

        # Resolve the governed timeline system prompt via PromptComposer
        # (RULE-02 / ADR-049 D9). The template
        # ``_bundled/planning/en/timeline/system.md`` carries the task framing,
        # project metadata, and KB context variables.
        #
        # KB context variables (kb_characters, kb_locations, kb_factions,
        # kb_relationships) flow from the provider above (ADR-067).
        # ``entity_events`` is wired from the already-injected event_repo
        # (confirmed events rendered compactly; §7 closed). Corrects the
        # prior stale "ADR-049 D8 notes" comment (D8 governs the timeline
        # template, not this slot).
        # ``culture_guidelines`` is NOT set here: it is unconditionally
        # auto-injected by the PromptComposer (resolved from ``name_style``
        # or empty string — see composer.py).
        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            mode="timeline",
            extra={
                "chapter_summaries": chapter_context,
                # Confirmed entity events, rendered from the event_repo;
                # empty-but-valid when none exist or no repo is wired (RULE-11).
                "entity_events": await render_confirmed_events(self._event_repo, novel_id),
                # kb_* spread from the provider — non-empty when the KB has
                # those entities, empty on degradation (RULE-11). Spread (not
                # a literal) so the §7 stub guard treats the slots as fed.
                **kb_vars,
            },
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
        # ``run()``). Chapter data flows as the run prompt (user channel).
        agent = TimelineAgent(model=prepared.model, system_prompt=composed.system)
        result = await agent.run(
            prompt=composed.user or chapter_context,
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
