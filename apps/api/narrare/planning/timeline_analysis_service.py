"""Timeline analysis service — AI-powered timeline generation and event confirmation.

Extracted from ``timeline_service.py`` (AD-5) to separate CRUD concerns
from AI analysis. This service calls the TimelineAgent to produce
chronological timeline analysis with conflict and gap detection.

Temporal expression extraction (``extract_temporal_expressions``,
``stream_extraction``) moved to ``timeline_extraction_service.py``
to keep files under the 300-line limit (RULE-04).

Pattern: Service → Core Agent (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.schemas import TimelineEventResponse, TimelineResponse
from narrare.planning.timeline_schemas import TimelineEventCRUDResponse
from narrare_core.ai_invocation import ManualInjectionDeclaration
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration: TimelineAgent composes its prompt internally
# from TimelineDeps (genre, language) and chapter context passed as user prompt.
_TIMELINE_ANALYSIS_INJECTION = ManualInjectionDeclaration(
    reason=(
        "TimelineAgent composes its prompt internally from TimelineDeps "
        "(genre, language) and chapter context passed as the user prompt."
    ),
    variables=("genre", "language"),
    injection_mechanism="agent_deps",
)


class TimelineAnalysisService:
    """Service for AI-powered chronological timeline analysis.

    Generates a structured timeline via the TimelineAgent and persists
    confirmed extracted expressions as timeline events.

    Args:
        novel_repo: For novel metadata (genre, language).
        chapter_repo: For listing chapters and their summaries.
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        event_repo: For persisting confirmed extracted events.
        api_key: Optional API key override.
        base_url: Optional base URL override.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        event_repo: TimelineEventRepository | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._event_repo = event_repo
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline

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

        # Gather chapters with summaries
        chapters = await self._chapter_repo.list_by_novel(novel_id)

        # Get model from registry
        from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps

        model = await self._registry.get_model(self._config)

        # Build deps
        deps = TimelineDeps(
            genre=novel.genre or "",
            language=novel.writing_language or "en",
        )

        # Build a compact chapter summary context
        chapter_context = "\n\n".join(
            f"Chapter {ch.position + 1}: {ch.title}\n"
            f"Summary: {ch.summary or '(no summary yet)'}\n"
            f"Timeline: {ch.timeline_position or '(not set)'}"
            for ch in chapters
        )

        agent = TimelineAgent(model=model)
        from narrare._app.invocation_context import safe_compose_invocation
        from narrare_core.llm.intents import LLMIntent

        await safe_compose_invocation(
            self._invocation_pipeline,
            feature_id="planning_timeline_analysis",
            intent=LLMIntent.PLAN,
            project_id=novel_id,
            manual_injection=_TIMELINE_ANALYSIS_INJECTION,
        )
        result = await agent.run(
            prompt=(
                f"Analyze the timeline for '{novel.title}'.\n\n"
                f"Genre: {novel.genre or 'Unspecified'}\n"
                f"Language: {novel.writing_language or 'en'}\n\n"
                f"Chapters:\n{chapter_context}"
            ),
            deps=deps,
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

        Creates a TimelineEvent with source='extracted' and confidence
        from the extraction result.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            extracted: The confirmed extracted expression to persist.

        Returns:
            The created timeline event as a CRUD response.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no event_repo is available.
        """
        if self._event_repo is None:
            raise ConfigurationError(
                "Event repository not available for confirming extracted events.",
                code="NO_EVENT_REPO",
            )

        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        event = await self._event_repo.create(
            novel_id=novel_id,
            event_name=extracted.event_name or extracted.expression,
            description=extracted.context,
            event_type="plot_point",
            timestamp_raw=extracted.timestamp_raw,
            timestamp_normalized="",
            source="extracted",
            confidence=extracted.confidence,
            is_confirmed=True,
        )

        logger.info(
            "extracted_event_confirmed",
            event_id=str(event.id),
            novel_id=str(novel_id),
            expression=extracted.expression,
        )
        return TimelineEventCRUDResponse.model_validate(event)
