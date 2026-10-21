"""Novel and chapter persistence. Both scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select

from app.kernel.contracts.models import Chapter, Novel
from app.kernel.db.base import ScopedRepository


class NovelRepository(ScopedRepository[Novel]):
    model = Novel

    async def list(self) -> Sequence[Novel]:
        result = await self.session.scalars(self.query().order_by(Novel.created_at.desc()))
        return result.all()

    async def get(self, novel_id: UUID) -> Novel | None:
        return await self.session.scalar(self.query().where(Novel.id == novel_id))

    async def create(self, title: str) -> Novel:
        novel = Novel(user_id=self.user_id, title=title)
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
            select(func.max(Chapter.position)).where(
                Chapter.novel_id == novel_id, Chapter.user_id == self.user_id
            )
        )
        return 0 if current is None else current + 1

    async def create(self, novel_id: UUID, title: str) -> Chapter:
        chapter = Chapter(
            user_id=self.user_id,
            novel_id=novel_id,
            title=title,
            position=await self.next_position(novel_id),
        )
        self.session.add(chapter)
        await self.session.flush()
        return chapter
