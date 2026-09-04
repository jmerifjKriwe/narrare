"""Preference analysis service — runs PreferenceAnalysisAgent on accumulated feedback.

Takes feedback events from the DB, formats them for the core
``PreferenceAnalysisAgent``, runs the analysis, and persists the
result to the ``preference_profiles`` table.

Model acquisition follows the per-user model-routing cascade: the DI
factory (``router_analysis._get_analysis_service``) resolves
``LLMIntent.EXTRACT`` for the authenticated user and passes the resolved
config + credentials in; the agent runner threads them to its ACTUAL
``registry.prepare()`` resolution point (the single assembly point).
All prompts come from PromptComposer (RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare.memory._agent_runner import run_preference_analysis_agent
from narrare.memory.schemas import AnalyzeResponse

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.memory.models import FeedbackEventModel
    from narrare.memory.repository import FeedbackRepository, PreferenceProfileRepository
    from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Minimum feedback events required before analysis can run
MIN_EVENTS_FOR_ANALYSIS = 5


class PreferenceAnalysisService:
    """Runs PreferenceAnalysisAgent on accumulated feedback.

    Args:
        registry: LLM ModelRegistry for creating the agent's model.
        feedback_repo: Repository for querying feedback events.
        profile_repo: Repository for persisting analysis results.
        composer: PromptComposer for building prompts (RULE-02).
        config: Resolved model config from the per-user routing cascade
            (resolved at the DI boundary in ``router_analysis``).
        invocation_pipeline: Optional InvocationPipeline for evidence recording.
        api_key: Per-user provider API key (model-routing cascade).
        base_url: Optional per-user provider base URL override.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        feedback_repo: FeedbackRepository,
        profile_repo: PreferenceProfileRepository,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._feedback_repo = feedback_repo
        self._profile_repo = profile_repo
        self._composer = composer
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url

    async def analyze(self, user_id: UUID, project_id: UUID) -> AnalyzeResponse:
        """Run PreferenceAnalysisAgent on accumulated feedback.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            AnalyzeResponse with the analysis results.

        Raises:
            ValueError: If fewer than ``MIN_EVENTS_FOR_ANALYSIS`` events exist.
        """
        from narrare.memory.models import PreferenceProfileModel

        # 1. Get feedback events from repo
        event_count = await self._feedback_repo.get_event_count(user_id, project_id)
        if event_count < MIN_EVENTS_FOR_ANALYSIS:
            raise ValueError(
                f"Need at least {MIN_EVENTS_FOR_ANALYSIS} feedback events, "
                f"but only {event_count} found"
            )

        events = await self._feedback_repo.get_events_batch(user_id, project_id, limit=50)

        # 2. Format as text for agent input
        feedback_text = self._format_events_for_agent(events)

        # 3. Create and run the agent
        result = await self._run_agent(
            feedback_text,
            event_count,
            user_id=user_id,
            project_id=project_id,
        )

        # 4. Persist result to preference_profiles
        profile = PreferenceProfileModel(
            user_id=user_id,
            project_id=project_id,
            style_patterns=list(result.style_patterns),
            content_patterns=list(result.content_patterns),
            avoidance_patterns=list(result.avoidance_patterns),
            confidence=result.confidence,
            summary=result.summary,
            event_count_at_analysis=event_count,
        )
        persisted = await self._profile_repo.upsert(profile)

        logger.info(
            "preference_analysis_completed",
            user_id=str(user_id),
            project_id=str(project_id),
            event_count=event_count,
            confidence=result.confidence,
        )

        return AnalyzeResponse(
            id=persisted.id,
            user_id=persisted.user_id,
            project_id=persisted.project_id,
            confidence=persisted.confidence,
            summary=persisted.summary,
            style_patterns=cast("list[str]", list(persisted.style_patterns)),
            content_patterns=cast("list[str]", list(persisted.content_patterns)),
            avoidance_patterns=cast("list[str]", list(persisted.avoidance_patterns)),
            event_count_at_analysis=persisted.event_count_at_analysis,
            created_at=persisted.created_at,
            updated_at=persisted.updated_at,
        )

    async def get_profile(self, user_id: UUID, project_id: UUID) -> AnalyzeResponse | None:
        """Get the latest preference profile for a user/project pair.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            AnalyzeResponse if a profile exists, None otherwise.
        """
        profile = await self._profile_repo.get(user_id, project_id)
        if profile is None:
            return None

        return AnalyzeResponse(
            id=profile.id,
            user_id=profile.user_id,
            project_id=profile.project_id,
            confidence=profile.confidence,
            summary=profile.summary,
            style_patterns=cast("list[str]", list(profile.style_patterns)),
            content_patterns=cast("list[str]", list(profile.content_patterns)),
            avoidance_patterns=cast("list[str]", list(profile.avoidance_patterns)),
            event_count_at_analysis=profile.event_count_at_analysis,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _format_events_for_agent(events: Sequence[FeedbackEventModel]) -> str:
        """Format feedback events as text for the analysis agent.

        Args:
            events: List of FeedbackEventModel instances.

        Returns:
            Formatted text summarising the feedback history.
        """
        parts: list[str] = []
        for event in events:
            line = f"- {event.action} ({event.intent}): {event.suggestion_text[:150]}"
            if event.modification:
                line += f" → modified to: {event.modification[:100]}"
            if event.rating:
                line += f" [rating: {event.rating}/5]"
            parts.append(line)

        return "\n".join(parts)

    async def _run_agent(
        self,
        feedback_text: str,
        event_count: int,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> PreferenceAnalysisOutput:
        """Run the PreferenceAnalysisAgent with the given feedback.

        Delegated to :mod:`narrare.memory._agent_runner` (RULE-04 split —
        agent invocation is a separate responsibility from the
        analyze/persist flow).
        """
        return await run_preference_analysis_agent(
            model_registry=self._registry,
            model_config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            feedback_text=feedback_text,
            event_count=event_count,
            user_id=user_id,
            project_id=project_id,
        )
