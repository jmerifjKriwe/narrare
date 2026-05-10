"""Chapter repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from narrare.chapters.models import Chapter

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterMetaRequest,
    )


class ChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> Chapter | None:
        result = await self._session.execute(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Chapter]:
        result = await self._session.execute(
            select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.position)
        )
        return list(result.scalars())

    async def max_position(self, novel_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(Chapter.position)).where(Chapter.novel_id == novel_id)
        )
        return result.scalar_one_or_none() or -1

    async def create(
        self,
        novel_id: uuid.UUID,
        request: CreateChapterRequest,
        position: int,
    ) -> Chapter:
        chapter = Chapter(
            novel_id=novel_id,
            title=request.title,
            content=request.content,
            position=position,
            word_count=count_words(request.content),
        )
        self._session.add(chapter)
        await self._session.flush()
        return chapter

    async def update_content(self, chapter: Chapter, content: str, word_count: int) -> Chapter:
        chapter.content = content
        chapter.word_count = word_count
        chapter.embeddings_dirty = True
        await self._session.flush()
        return chapter

    async def update_meta(self, chapter: Chapter, request: UpdateChapterMetaRequest) -> Chapter:
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(chapter, field, value)
        await self._session.flush()
        return chapter

    async def reorder(self, novel_id: uuid.UUID, chapter_ids: list[uuid.UUID]) -> list[Chapter]:
        """Set positions 0..n based on chapter_ids order. Atomic."""
        for position, chapter_id in enumerate(chapter_ids):
            await self._session.execute(
                update(Chapter)
                .where(Chapter.id == chapter_id, Chapter.novel_id == novel_id)
                .values(position=position)
            )
        await self._session.flush()
        return await self.list_by_novel(novel_id)

    async def delete(self, chapter: Chapter) -> None:
        await self._session.delete(chapter)
        await self._session.flush()


def count_words(text: str) -> int:
    return len(text.split()) if text.strip() else 0
