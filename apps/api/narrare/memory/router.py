"""Memory routes — thin, delegates immediately to memory services."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.memory.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    PreferenceResponse,
    ResetResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.memory.service import MemoryFeedbackService, MemoryPreferenceService

router = APIRouter(prefix="/memory", tags=["memory"])


async def _get_feedback_service(
    session: AsyncSession = Depends(get_async_session),
) -> MemoryFeedbackService:
    """Async factory for MemoryFeedbackService."""
    from narrare.memory.models import FeedbackEventModel
    from narrare.memory.repository import FeedbackRepository
    from narrare.memory.service import MemoryFeedbackService
    from narrare_core.memory.feedback_service import FeedbackService
    from narrare_core.memory.mem0_client import NullMemoryClient
    from narrare_core.memory.models import FeedbackEvent

    repo = FeedbackRepository(session)
    null_client = NullMemoryClient()

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
            context=event.context or None,
            created_at=event.created_at,
        )
        await repo.create(model)

    core_feedback = FeedbackService(
        mem0_client=null_client,
        persist_fn=_persist_adapter,
    )
    return MemoryFeedbackService(repository=repo, core_feedback=core_feedback)


async def _get_preference_service(
    session: AsyncSession = Depends(get_async_session),
) -> MemoryPreferenceService:
    """Async factory for MemoryPreferenceService."""
    from narrare.memory.repository import FeedbackRepository
    from narrare.memory.service import MemoryPreferenceService
    from narrare_core.memory.mem0_client import NullMemoryClient
    from narrare_core.memory.preference_service import PreferenceService

    repo = FeedbackRepository(session)
    null_client = NullMemoryClient()
    core_preference = PreferenceService(mem0_client=null_client)
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
