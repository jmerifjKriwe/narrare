"""Chapter routes — CRUD and reorder. Version routes in router_versions.py."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.analytics.dependencies import WritingStatsRecorderDep
from narrare.chapters.repository import ChapterRepository
from narrare.chapters.schemas import (
    ChapterResponse,
    ChapterSummaryResponse,
    CreateChapterRequest,
    ReorderChaptersRequest,
    UpdateChapterContentRequest,
    UpdateChapterMetaRequest,
)
from narrare.chapters.service import ChapterService
from narrare.events.publisher import WikiEventPublisherDep
from narrare.novels.repository import NovelRepository
from narrare.novels.service import NovelService
from narrare.volumes.repository import VolumeRepository

router = APIRouter(prefix="/novels/{novel_id}/chapters", tags=["chapters"])


def _get_service(
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
    writing_stats_recorder: WritingStatsRecorderDep,
) -> ChapterService:
    return ChapterService(
        repo=ChapterRepository(session),
        novel_service=NovelService(
            repo=NovelRepository(session),
            volume_repo=VolumeRepository(session),
        ),
        volume_repo=VolumeRepository(session),
        event_publisher=event_publisher,
        writing_stats_recorder=writing_stats_recorder,
    )


@router.get("", response_model=list[ChapterSummaryResponse])
async def list_chapters(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    volume_id: uuid.UUID | None = None,
    service: ChapterService = Depends(_get_service),
) -> list[ChapterSummaryResponse]:
    chapters = await service.list_chapters(novel_id, uuid.UUID(user_id), volume_id=volume_id)
    return [ChapterSummaryResponse.model_validate(c) for c in chapters]


@router.post("", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    novel_id: uuid.UUID,
    request: CreateChapterRequest,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterResponse:
    chapter = await service.create(novel_id, uuid.UUID(user_id), request)
    return ChapterResponse.model_validate(chapter)


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterResponse:
    chapter = await service.get(chapter_id, novel_id, uuid.UUID(user_id))
    return ChapterResponse.model_validate(chapter)


@router.put("/{chapter_id}/content", response_model=ChapterResponse)
async def update_chapter_content(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: UpdateChapterContentRequest,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterResponse:
    """Autosave endpoint — called on every editor save."""
    chapter = await service.update_content(chapter_id, novel_id, uuid.UUID(user_id), request)
    return ChapterResponse.model_validate(chapter)


@router.patch("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter_meta(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: UpdateChapterMetaRequest,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> ChapterResponse:
    chapter = await service.update_meta(chapter_id, novel_id, uuid.UUID(user_id), request)
    return ChapterResponse.model_validate(chapter)


@router.post("/reorder", response_model=list[ChapterSummaryResponse])
async def reorder_chapters(
    novel_id: uuid.UUID,
    request: ReorderChaptersRequest,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> list[ChapterSummaryResponse]:
    chapters = await service.reorder(novel_id, uuid.UUID(user_id), request.chapter_ids)
    return [ChapterSummaryResponse.model_validate(c) for c in chapters]


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: ChapterService = Depends(_get_service),
) -> None:
    await service.delete(chapter_id, novel_id, uuid.UUID(user_id))
