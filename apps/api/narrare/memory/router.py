"""Memory routes — feedback recording and preference retrieval.

Analysis endpoint is in ``router_analysis.py`` for RULE-04 compliance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.memory.dependencies import get_memory_client
from narrare.memory.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    PreferenceResponse,
    ResetResponse,
)

if TYPE_CHECKING:
    from narrare.memory.service import MemoryFeedbackService, MemoryPreferenceService

router = APIRouter(prefix="/memory", tags=["memory"])


async def _get_feedback_service(
    session: SessionDep,
    mem0_client: Any = Depends(get_memory_client),
) -> MemoryFeedbackService:
    """Async factory for MemoryFeedbackService with event publishing."""
    from narrare.events.publisher import EventPublisher
    from narrare.memory.models import FeedbackEventModel
    from narrare.memory.repository import FeedbackRepository
    from narrare.memory.service import MemoryFeedbackService
    from narrare_core.memory.feedback_service import FeedbackService
    from narrare_core.memory.models import FeedbackEvent

    repo = FeedbackRepository(session)

    async def _persist_adapter(event: FeedbackEvent) -> None:
        """Adapt core FeedbackEvent to SQLAlchemy FeedbackEventModel for persistence."""
        model = FeedbackEventModel(
            id=event.id,
            user_id=event.user_id,
            project_id=event.project_id,
            suggestion_id=event.suggestion_id,
            action=event.action.value,
            intent=event.intent,
            suggestion_text=event.suggestion_text,
            modification=event.modification or None,
            rating=event.rating,
            context=event.context or None,
            created_at=event.created_at,
        )
        await repo.create(model)

    core_feedback = FeedbackService(
        mem0_client=mem0_client,
        persist_fn=_persist_adapter,
    )
    publisher = EventPublisher()
    return MemoryFeedbackService(
        repository=repo,
        core_feedback=core_feedback,
        event_publisher=publisher,
    )


async def _get_preference_service(
    session: SessionDep,
    mem0_client: Any = Depends(get_memory_client),
) -> MemoryPreferenceService:
    """Async factory for MemoryPreferenceService."""
    from narrare.memory.repository import FeedbackRepository
    from narrare.memory.service import MemoryPreferenceService
    from narrare_core.memory.preference_service import PreferenceService

    repo = FeedbackRepository(session)
    core_preference = PreferenceService(mem0_client=mem0_client)
    return MemoryPreferenceService(repository=repo, core_preference=core_preference)


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def record_feedback(
    request: FeedbackRequest,
    user_id: CurrentUserIdDep,
    service: MemoryFeedbackService = Depends(_get_feedback_service),
) -> FeedbackResponse:
    """Record user feedback on an AI suggestion."""
    return await service.record_feedback(request, UUID(user_id))


@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    project_id: UUID,
    user_id: CurrentUserIdDep,
    service: MemoryPreferenceService = Depends(_get_preference_service),
) -> PreferenceResponse:
    """Retrieve aggregated preferences for a user/project pair."""
    return await service.get_preferences(UUID(user_id), project_id)


@router.delete("/preferences", response_model=ResetResponse)
async def reset_preferences(
    project_id: UUID,
    user_id: CurrentUserIdDep,
    service: MemoryPreferenceService = Depends(_get_preference_service),
) -> ResetResponse:
    """Clear all feedback events and preferences for a user/project pair."""
    return await service.reset_preferences(UUID(user_id), project_id)
