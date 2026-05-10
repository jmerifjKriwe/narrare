"""Chapter service — business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException, status

from narrare.chapters.repository import ChapterRepository, count_words
from narrare.novels.service import NovelService

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.models import Chapter
    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterContentRequest,
        UpdateChapterMetaRequest,
    )

logger = structlog.get_logger(__name__)

_MAX_CONTENT_LENGTH = 100_000  # characters


class ChapterService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ChapterRepository(session)
        self._novel_service = NovelService(session)

    async def get(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Chapter:
        """Get a chapter, verifying novel ownership."""
        await self._novel_service.get(novel_id, user_id)  # ownership check
        chapter = await self._repo.get_by_id(chapter_id, novel_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )
        return chapter

    async def list_chapters(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> list[Chapter]:
        await self._novel_service.get(novel_id, user_id)
        return await self._repo.list_by_novel(novel_id)

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: CreateChapterRequest,
    ) -> Chapter:
        await self._novel_service.get(novel_id, user_id)
        position = request.position
        if position is None:
            position = (await self._repo.max_position(novel_id)) + 1
        chapter = await self._repo.create(novel_id, request, position)
        logger.info("chapter_created", chapter_id=str(chapter.id), novel_id=str(novel_id))
        return chapter

    async def update_content(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterContentRequest,
    ) -> Chapter:
        if len(request.content) > _MAX_CONTENT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Chapter content exceeds {_MAX_CONTENT_LENGTH:,} character limit",
            )
        chapter = await self.get(chapter_id, novel_id, user_id)
        word_count = request.word_count or count_words(request.content)
        updated = await self._repo.update_content(chapter, request.content, word_count)
        logger.debug("chapter_content_updated", chapter_id=str(chapter_id), words=word_count)
        return updated

    async def update_meta(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterMetaRequest,
    ) -> Chapter:
        chapter = await self.get(chapter_id, novel_id, user_id)
        return await self._repo.update_meta(chapter, request)

    async def reorder(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID],
    ) -> list[Chapter]:
        await self._novel_service.get(novel_id, user_id)
        chapters = await self._repo.reorder(novel_id, chapter_ids)
        logger.info("chapters_reordered", novel_id=str(novel_id), count=len(chapters))
        return chapters

    async def delete(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        chapter = await self.get(chapter_id, novel_id, user_id)
        await self._repo.delete(chapter)
        logger.info("chapter_deleted", chapter_id=str(chapter_id))
