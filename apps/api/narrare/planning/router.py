"""Planning routes — storyboard, outlines, and remap endpoints.

Thin routers that delegate immediately to StoryboardService (RULE-06).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.repository import OutlineRepository
from narrare.planning.schemas import (
    OutlineResponse,
    OutlineUpdateRequest,
    RemapRequest,
    RemapResponse,
    StoryboardResponse,
    SyncStatusResponse,
)
from narrare.planning.service import StoryboardService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/planning", tags=["planning"])


def _get_service(
    session: AsyncSession = Depends(get_async_session),
) -> StoryboardService:
    """Wire up StoryboardService with all dependencies."""
    return StoryboardService(
        outline_repo=OutlineRepository(session),
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
    )


@router.get("/storyboard/{novel_id}", response_model=StoryboardResponse)
async def get_storyboard(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: StoryboardService = Depends(_get_service),
) -> StoryboardResponse:
    """Return the full storyboard view for a novel."""
    return await service.get_storyboard(novel_id, uuid.UUID(user_id))


@router.get(
    "/storyboard/{novel_id}/sync",
    response_model=list[SyncStatusResponse],
)
async def get_sync_status(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: StoryboardService = Depends(_get_service),
) -> list[SyncStatusResponse]:
    """Return sync status for all chapters in a novel."""
    return await service.get_sync_status(novel_id, uuid.UUID(user_id))


@router.get(
    "/outlines/{novel_id}/{chapter_id}",
    response_model=OutlineResponse,
)
async def get_or_create_outline(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: StoryboardService = Depends(_get_service),
) -> OutlineResponse:
    """Get an existing outline or auto-create one."""
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
    service: StoryboardService = Depends(_get_service),
) -> OutlineResponse:
    """Update specific fields on a chapter outline."""
    return await service.update_outline(chapter_id, request, uuid.UUID(user_id), novel_id=novel_id)


@router.post(
    "/storyboard/{novel_id}/remap",
    response_model=RemapResponse,
)
async def remap_storyboard(
    novel_id: uuid.UUID,
    request: RemapRequest,
    user_id: CurrentUserIdDep,
    service: StoryboardService = Depends(_get_service),
) -> RemapResponse:
    """Preview or confirm a structure remap for a novel."""
    uid = uuid.UUID(user_id)
    if request.confirm:
        return await service.confirm_remap(novel_id, request.new_structure, uid)
    return await service.preview_remap(novel_id, request.new_structure, uid)
