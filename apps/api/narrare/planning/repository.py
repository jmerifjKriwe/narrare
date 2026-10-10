"""Outline repository — DB queries only (RULE-07: repo → DB)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.planning.models import ChapterOutline

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class OutlineRepository(BaseRepository):
    """Persistence layer for chapter outlines."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_chapter_id(self, chapter_id: uuid.UUID) -> ChapterOutline | None:
        """Return the outline for a given chapter, or None."""
        result = await self._session.execute(
            select(ChapterOutline).where(ChapterOutline.chapter_id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_all_for_novel(self, novel_id: uuid.UUID) -> list[ChapterOutline]:
        """Return all outlines for chapters belonging to the given novel.

        Joins through the ``chapters`` table to filter by ``novel_id``.
        """
        from narrare.chapters.models import Chapter

        result = await self._session.execute(
            select(ChapterOutline)
            .join(Chapter, ChapterOutline.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.position)
        )
        return list(result.scalars())

    async def create(
        self,
        chapter_id: uuid.UUID,
        stage_assignment: str,
        outline_notes: str = "",
    ) -> ChapterOutline:
        """Create a new chapter outline.

        PLAN-001 T14: the beat write path is gone — scene plans
        (``ScenePlanRepository``) are the substrate. The legacy column is
        NOT NULL until the T17 drop; the ORM column default persists an
        empty list.
        """
        outline = ChapterOutline(
            chapter_id=chapter_id,
            stage_assignment=stage_assignment,
            outline_notes=outline_notes,
        )
        self._session.add(outline)
        await self._flush_and_refresh(outline)
        return outline

    async def update(self, chapter_id: uuid.UUID, **fields: object) -> ChapterOutline:
        """Update specific fields on the outline for the given chapter.

        Touches ``updated_at`` automatically via SQLAlchemy ``onupdate``.
        """
        outline = await self.get_by_chapter_id(chapter_id)
        if outline is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("ChapterOutline", identifier=str(chapter_id))

        for field, value in fields.items():
            setattr(outline, field, value)
        await self._flush_and_refresh(outline)
        return outline
