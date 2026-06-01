"""Timeline analysis service — AI-powered timeline generation.

Extracted from ``timeline_service.py`` (AD-5) to separate CRUD concerns
from AI analysis. This service calls the TimelineAgent to produce
chronological timeline analysis with conflict and gap detection.

Pattern: Service → Core Agent (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.schemas import TimelineEventResponse, TimelineResponse
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

logger = structlog.get_logger(__name__)


class TimelineAnalysisService:
    """Service for AI-powered chronological timeline analysis.

    Gathers chapter summaries, entity events, and structural info,
    then runs the TimelineAgent to produce a structured timeline
    with temporal conflict and coverage gap detection.

    Args:
        novel_repo: For novel metadata (genre, language).
        chapter_repo: For listing chapters and their summaries.
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        api_key: Optional API key override.
        base_url: Optional base URL override.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._api_key = api_key
        self._base_url = base_url

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
