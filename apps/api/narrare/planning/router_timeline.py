"""Timeline routes — CRUD endpoints and AI analysis for timeline events.

Thin routers that delegate immediately to services (RULE-06).
CRUD operations use ``TimelineService``, analysis uses
``TimelineAnalysisService``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._timeline_analysis_factory import get_timeline_analysis_service
from narrare.planning._timeline_factory import get_timeline_crud_service
from narrare.planning.schemas import TimelineResponse
from narrare.planning.timeline_schemas import (
    TimelineEventCreateRequest,
    TimelineEventCRUDResponse,
    TimelineEventUpdateRequest,
)

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/{novel_id}/events", response_model=list[TimelineEventCRUDResponse])
async def list_timeline_events(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    event_type: str | None = None,
    chapter_id: uuid.UUID | None = None,
    source: str | None = None,
    is_confirmed: bool | None = None,
) -> list[TimelineEventCRUDResponse]:
    """List timeline events for a novel with optional filters."""
    service = await get_timeline_crud_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.list_events(
        novel_id,
        uuid.UUID(user_id),
        event_type=event_type,
        chapter_id=chapter_id,
        source=source,
        is_confirmed=is_confirmed,
    )


@router.post(
    "/{novel_id}/events",
    response_model=TimelineEventCRUDResponse,
    status_code=201,
)
async def create_timeline_event(
    novel_id: uuid.UUID,
    request: TimelineEventCreateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineEventCRUDResponse:
    """Create a new timeline event."""
    service = await get_timeline_crud_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.create_event(novel_id, uuid.UUID(user_id), request)


@router.get("/{novel_id}/events/{event_id}", response_model=TimelineEventCRUDResponse)
async def get_timeline_event(
    novel_id: uuid.UUID,
    event_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineEventCRUDResponse:
    """Get a single timeline event by ID."""
    service = await get_timeline_crud_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.get_event(event_id, uuid.UUID(user_id))


@router.put("/{novel_id}/events/{event_id}", response_model=TimelineEventCRUDResponse)
async def update_timeline_event(
    novel_id: uuid.UUID,
    event_id: uuid.UUID,
    request: TimelineEventUpdateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineEventCRUDResponse:
    """Update specific fields on a timeline event."""
    service = await get_timeline_crud_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.update_event(event_id, uuid.UUID(user_id), request)


@router.delete("/{novel_id}/events/{event_id}", status_code=204)
async def delete_timeline_event(
    novel_id: uuid.UUID,
    event_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> None:
    """Delete a timeline event."""
    service = await get_timeline_crud_service(session=session, user_id=user_id, novel_id=novel_id)
    await service.delete_event(event_id, uuid.UUID(user_id))


# AI analysis endpoint — moved from router.py for backward compat
@router.get("/{novel_id}", response_model=TimelineResponse)
async def get_timeline_analysis(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineResponse:
    """Generate a chronological timeline analysis for a novel."""
    service = await get_timeline_analysis_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    return await service.generate_timeline(novel_id, uuid.UUID(user_id))
