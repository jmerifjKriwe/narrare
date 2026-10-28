"""Novel, chapter and entity persistence. Each repository is scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, datetime
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select

from app.kernel.contracts.models import Chapter, Entity, Novel
from app.kernel.db.base import ScopedRepository


class EntityRepository(ScopedRepository[Entity]):
    model = Entity

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Entity]:
        """Every kept entity of one novel, scoped to the user, any order —
        the continuation scan orders by first occurrence itself."""
        result = await self.session.scalars(self.query().where(Entity.novel_id == novel_id))
        return result.all()


class NovelRepository(ScopedRepository[Novel]):
    model = Novel

    async def list(self) -> Sequence[Novel]:
        result = await self.session.scalars(self.query().order_by(Novel.created_at.desc()))
        return result.all()

    async def get(self, novel_id: UUID) -> Novel | None:
        return await self.session.scalar(self.query().where(Novel.id == novel_id))

    async def create(self, title: str, genre: str | None = None, blurb: str | None = None) -> Novel:
        """Flush a new novel for this user, leaving the commit to the caller."""
        novel = Novel(user_id=self.user_id, title=title, genre=genre, blurb=blurb)
        self.session.add(novel)
        await self.session.flush()
        return novel


class ChapterRepository(ScopedRepository[Chapter]):
    model = Chapter

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Chapter]:
        result = await self.session.scalars(
            self.query().where(Chapter.novel_id == novel_id).order_by(Chapter.position)
        )
        return result.all()

    async def get(self, chapter_id: UUID) -> Chapter | None:
        return await self.session.scalar(self.query().where(Chapter.id == chapter_id))

    async def next_position(self, novel_id: UUID) -> int:
        current = await self.session.scalar(
            select(func.max(Chapter.position)).where(Chapter.novel_id == novel_id, self.owned())
        )
        return 0 if current is None else current + 1

    async def create(self, novel_id: UUID, title: str) -> Chapter:
        """Append a chapter at the next position and update its novel's timestamp.

        Flush both changes without committing; an empty novel starts at position 0.
        """
        chapter = Chapter(
            user_id=self.user_id,
            novel_id=novel_id,
            title=title,
            position=await self.next_position(novel_id),
        )
        self.session.add(chapter)
        await self._touch_novel(novel_id)
        await self.session.flush()
        return chapter

    async def save(self, chapter: Chapter, changes: dict[str, Any]) -> Chapter:
        """Apply an edit and mark the novel written-in; one write, one bump."""
        for field, value in changes.items():
            setattr(chapter, field, value)
        await self._touch_novel(chapter.novel_id)
        await self.session.flush()
        return chapter

    async def _touch_novel(self, novel_id: UUID) -> None:
        """Advance the parent novel's updated_at from a chapter write.

        The column's onupdate fires only for the row an UPDATE statement
        touches — the chapter — and cannot reach the novel, whose row the
        write would otherwise leave alone. The start page reads the novel's
        timestamp to decide what was last written in, so the bump is here,
        with the write that earns it.
        """
        novel = await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )
        if novel is not None:
            novel.updated_at = datetime.now(UTC)
