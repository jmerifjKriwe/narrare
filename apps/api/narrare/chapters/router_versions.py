"""Chapter version routes — extracted from router.py for RULE-04 compliance."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.chapters.repository import ChapterRepository
from narrare.chapters.schemas import (
    ChapterResponse,
    ChapterVersionListResponse,
    ChapterVersionResponse,
)
from narrare.chapters.service import ChapterService
from narrare.novels.repository import NovelRepository
from narrare.novels.service import NovelService
from narrare.volumes.repository import VolumeRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/novels/{novel_id}/chapters",
    tags=["chapters"],
)


def _get_service(
    session: AsyncSession = Depends(get_async_session),
) -> ChapterService:
    return ChapterService(
        repo=ChapterRepository(session),
        novel_service=NovelService(
            repo=NovelRepository(session),
            volume_repo=VolumeRepository(session),
        ),
        volume_repo=VolumeRepository(session),
    )


@router.get("/{chapter_id}/versions", response_model=ChapterVersionListResponse)
async def list_chapter_versions(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterVersionListResponse:
    """List all versions of a chapter, newest first."""
    versions = await service.list_versions(chapter_id, novel_id, uuid.UUID(user_id))
    return ChapterVersionListResponse(
        versions=[ChapterVersionResponse.model_validate(v) for v in versions],
        total=len(versions),
    )


@router.post("/{chapter_id}/versions/{version_id}/restore", response_model=ChapterResponse)
async def restore_chapter_version(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterResponse:
    """Restore a chapter to a previous version."""
    chapter = await service.restore_version(chapter_id, version_id, novel_id, uuid.UUID(user_id))
    return ChapterResponse.model_validate(chapter)
