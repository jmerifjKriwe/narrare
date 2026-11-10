"""HTTP surface for scene plans and timeline events. Parses, delegates, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.planning.schemas import (
    PlanningErrorRead,
    SceneAggregateRead,
    SceneAggregateUpdate,
    TimelineEventCreate,
    TimelineEventRead,
    TimelineEventUpdate,
)
from app.capabilities.planning.service import (
    NotFoundError,
    PlanningService,
    SceneRefusedError,
    TimelineRefusedError,
)
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session

router = APIRouter(prefix="/api/planning", tags=["planning"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> PlanningService:
    """Build the planning service with the request session and current owner."""
    return PlanningService(session, user_id)


ServiceDep = Annotated[PlanningService, Depends(_service)]


@router.get(
    "/novels/{novel_id}/chapters/{chapter_id}/scenes",
    response_model=SceneAggregateRead,
    responses={404: {"model": PlanningErrorRead, "description": "Chapter not found"}},
)
async def read_scenes(novel_id: UUID, chapter_id: UUID, service: ServiceDep) -> SceneAggregateRead:
    """Read the chapter's scenes in position order, with the version stamp.

    No auto-create: a chapter without plans answers with an empty list.
    Raise HTTP 404 for an absent or unowned chapter — a foreign novel reads
    as missing, never as an oracle.
    """
    try:
        return await service.get_aggregate(novel_id, chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None


@router.put(
    "/novels/{novel_id}/chapters/{chapter_id}/scenes",
    response_model=SceneAggregateRead,
    responses={
        404: {"model": PlanningErrorRead, "description": "Chapter not found"},
        409: {"model": PlanningErrorRead, "description": "Setup required"},
        422: {"model": PlanningErrorRead, "description": "A refused aggregate, named in `detail`"},
    },
)
async def save_scenes(
    novel_id: UUID, chapter_id: UUID, payload: SceneAggregateUpdate, service: ServiceDep
) -> SceneAggregateRead:
    """Diff the chapter's whole scene list by stable id and return the result.

    A known id updates, an id from another chapter is a 422, a doubled id is
    a 422 before any write, an absent id deletes, and positions renumber 1..N
    by payload order. Raise HTTP 404 for an absent or unowned chapter, or HTTP
    409 when setup has not created the owning user.
    """
    try:
        return await service.save_aggregate(novel_id, chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    except SceneRefusedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post(
    "/novels/{novel_id}/timeline-events",
    response_model=TimelineEventRead,
    status_code=201,
    responses={
        404: {"model": PlanningErrorRead, "description": "Novel not found"},
        409: {"model": PlanningErrorRead, "description": "Setup required"},
        422: {"model": PlanningErrorRead, "description": "A refused event, named in `detail`"},
    },
)
async def create_timeline_event(
    novel_id: UUID, payload: TimelineEventCreate, service: ServiceDep
) -> TimelineEventRead:
    """Create one event on the novel's timeline and return it.

    Raise HTTP 404 for an absent or unowned novel — a foreign novel reads as
    missing, never as an oracle — HTTP 409 without the setup-created user,
    or HTTP 422 for a blank title or a chapter link the novel does not hold.
    """
    try:
        return await service.create_timeline_event(novel_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    except TimelineRefusedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get(
    "/novels/{novel_id}/timeline-events",
    response_model=list[TimelineEventRead],
    responses={404: {"model": PlanningErrorRead, "description": "Novel not found"}},
)
async def list_timeline_events(novel_id: UUID, service: ServiceDep) -> list[TimelineEventRead]:
    """List the novel's events in manual order, unordered rows last.

    Raise HTTP 404 for an absent or unowned novel.
    """
    try:
        return await service.list_timeline_events(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None


@router.get(
    "/novels/{novel_id}/timeline-events/{event_id}",
    response_model=TimelineEventRead,
    responses={404: {"model": PlanningErrorRead, "description": "Event not found"}},
)
async def get_timeline_event(
    novel_id: UUID, event_id: UUID, service: ServiceDep
) -> TimelineEventRead:
    """Return one event of the novel; raise HTTP 404 when it, the novel, or
    the ownership is missing."""
    try:
        return await service.get_timeline_event(novel_id, event_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="timeline event not found") from None


@router.put(
    "/novels/{novel_id}/timeline-events/{event_id}",
    response_model=TimelineEventRead,
    responses={
        404: {"model": PlanningErrorRead, "description": "Event not found"},
        409: {"model": PlanningErrorRead, "description": "Setup required"},
        422: {"model": PlanningErrorRead, "description": "A refused event, named in `detail`"},
    },
)
async def update_timeline_event(
    novel_id: UUID, event_id: UUID, payload: TimelineEventUpdate, service: ServiceDep
) -> TimelineEventRead:
    """Edit the carried fields of one event and return it.

    A carried ``null`` clears the chapter link or the position; an absent
    field leaves it alone. Raise HTTP 404 for an absent or unowned event or
    novel, or HTTP 422 for a blank title or a chapter link the novel does
    not hold.
    """
    try:
        return await service.update_timeline_event(novel_id, event_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="timeline event not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    except TimelineRefusedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.delete(
    "/novels/{novel_id}/timeline-events/{event_id}",
    status_code=204,
    responses={
        404: {"model": PlanningErrorRead, "description": "Event not found"},
        409: {"model": PlanningErrorRead, "description": "Setup required"},
    },
)
async def delete_timeline_event(novel_id: UUID, event_id: UUID, service: ServiceDep) -> None:
    """Delete one event of the novel; raise HTTP 404 for an absent or
    unowned event or novel."""
    try:
        await service.delete_timeline_event(novel_id, event_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="timeline event not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
