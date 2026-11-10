"""HTTP surface for scene plans. Parses, delegates, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.planning.schemas import (
    PlanningErrorRead,
    SceneAggregateRead,
    SceneAggregateUpdate,
)
from app.capabilities.planning.service import NotFoundError, PlanningService, SceneRefusedError
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
