"""Planning routes — storyboard, outlines, and structure remap endpoints.

Thin routers that delegate immediately to StoryboardService (RULE-06).
Timeline routes are in ``router_timeline.py`` and included here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._character_arc_factory import get_character_arc_service
from narrare.planning._service_factory import get_storyboard_service
from narrare.planning.router_timeline import router as timeline_router
from narrare.planning.schemas import (
    CharacterArcRequest,
    CharacterArcResponse,
    OutlineResponse,
    OutlineUpdateRequest,
    RemapRequest,
    RemapResponse,
    StoryboardResponse,
    SyncStatusResponse,
)

router = APIRouter(prefix="/planning", tags=["planning"])
router.include_router(timeline_router)


@router.get("/storyboard/{novel_id}", response_model=StoryboardResponse)
async def get_storyboard(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StoryboardResponse:
    """Return the full storyboard view for a novel."""
    service = await get_storyboard_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.get_storyboard(novel_id, uuid.UUID(user_id))


@router.get(
    "/storyboard/{novel_id}/sync",
    response_model=list[SyncStatusResponse],
)
async def get_sync_status(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> list[SyncStatusResponse]:
    """Return sync status for all chapters in a novel."""
    service = await get_storyboard_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.get_sync_status(novel_id, uuid.UUID(user_id))


@router.get(
    "/outlines/{novel_id}/{chapter_id}",
    response_model=OutlineResponse,
)
async def get_or_create_outline(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> OutlineResponse:
    """Get an existing outline or auto-create one."""
    service = await get_storyboard_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.get_or_create_outline(
        chapter_id, "three_act", uuid.UUID(user_id), novel_id=novel_id
    )


@router.put(
    "/outlines/{novel_id}/{chapter_id}",
    response_model=OutlineResponse,
)
async def update_outline(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: OutlineUpdateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> OutlineResponse:
    """Update specific fields on a chapter outline."""
    service = await get_storyboard_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.update_outline(chapter_id, request, uuid.UUID(user_id), novel_id=novel_id)


@router.post(
    "/storyboard/{novel_id}/remap",
    response_model=RemapResponse,
)
async def remap_storyboard(
    novel_id: uuid.UUID,
    request: RemapRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> RemapResponse:
    """Preview or confirm a structure remap for a novel."""
    service = await get_storyboard_service(session=session, user_id=user_id, novel_id=novel_id)
    uid = uuid.UUID(user_id)
    if request.confirm:
        return await service.confirm_remap(novel_id, request.new_structure, uid)
    return await service.preview_remap(novel_id, request.new_structure, uid)


@router.post("/character-arc/{novel_id}", response_model=CharacterArcResponse)
async def generate_character_arc(
    novel_id: uuid.UUID,
    request: CharacterArcRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> CharacterArcResponse:
    """Generate a character development arc for a character in a novel."""
    service = await get_character_arc_service(session=session, user_id=user_id, novel_id=novel_id)
    return await service.generate_character_arc(novel_id, uuid.UUID(user_id), request)
