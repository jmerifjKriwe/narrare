"""Memory API services — wrap core memory services with DB persistence.

Two service classes:
    - ``MemoryFeedbackService`` — records feedback via core FeedbackService
    - ``MemoryPreferenceService`` — retrieves/resets preferences via core PreferenceService
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.memory.schemas import (
    FeedbackResponse,
    PreferenceResponse,
    ResetResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.memory.repository import FeedbackRepository
    from narrare.memory.schemas import FeedbackRequest
    from narrare_core.memory.feedback_service import FeedbackService
    from narrare_core.memory.preference_service import PreferenceService

logger = structlog.get_logger(__name__)


class MemoryFeedbackService:
    """Records feedback events via core FeedbackService with DB persistence.

    Delegates to the core ``FeedbackService`` for mem0 forwarding while
    using the API ``FeedbackRepository`` as the persist_fn callback.
    """

    def __init__(
        self,
        repository: FeedbackRepository,
        core_feedback: FeedbackService,
    ) -> None:
        self._repository = repository
        self._core_feedback = core_feedback

    async def record_feedback(self, request: FeedbackRequest, user_id: UUID) -> FeedbackResponse:
        """Record a feedback event and return the persisted response.

        Args:
            request: Feedback data from the client.
            user_id: Authenticated user ID from the JWT.

        Returns:
            FeedbackResponse with the persisted event ID and timestamp.
        """
        from narrare_core.memory.models import FeedbackAction, FeedbackEvent

        action = FeedbackAction(request.action)
        event = FeedbackEvent(
            user_id=user_id,
            project_id=request.project_id,
            suggestion_id=request.suggestion_id,
            action=action,
            intent=request.intent,
            suggestion_text=request.suggestion_text,
            modification=request.modification or "",
            context=request.context or {},
        )

        await self._core_feedback.record(event)

        logger.info(
            "feedback_recorded",
            user_id=str(user_id),
            project_id=str(request.project_id),
            action=action.value,
        )

        return FeedbackResponse(
            id=event.id,
            action=event.action.value,
            created_at=event.created_at,
        )


class MemoryPreferenceService:
    """Retrieves and resets user preferences via core PreferenceService.

    Combines DB-level event deletion with mem0 preference reset for
    complete preference clearance.
    """

    def __init__(
        self,
        repository: FeedbackRepository,
        core_preference: PreferenceService,
    ) -> None:
        self._repository = repository
        self._core_preference = core_preference

    async def get_preferences(self, user_id: UUID, project_id: UUID) -> PreferenceResponse:
        """Retrieve aggregated preferences for a user/project pair.

        Args:
            user_id: Authenticated user ID.
            project_id: Project to get preferences for.

        Returns:
            PreferenceResponse with style, content, and constraint data.
        """
        profile = await self._core_preference.get_preferences(user_id, project_id)

        return PreferenceResponse(
            user_id=profile.user_id,
            project_id=profile.project_id,
            event_count=profile.event_count,
            confidence=profile.confidence,
            style=profile.style,
            content=profile.content,
            constraints=profile.constraints,
            last_updated=profile.last_updated,
        )

    async def reset_preferences(self, user_id: UUID, project_id: UUID) -> ResetResponse:
        """Clear all feedback events and preferences for a user/project pair.

        Deletes DB feedback events first, then resets mem0 preferences.

        Args:
            user_id: Authenticated user ID.
            project_id: Project to reset preferences for.

        Returns:
            ResetResponse with confirmation message and deleted count.
        """
        deleted_count = await self._repository.delete_by_user_project(user_id, project_id)
        await self._core_preference.reset(user_id, project_id)

        logger.info(
            "preferences_reset",
            user_id=str(user_id),
            project_id=str(project_id),
            deleted_count=deleted_count,
        )

        return ResetResponse(
            message="Preferences reset successfully",
            deleted_count=deleted_count,
        )
