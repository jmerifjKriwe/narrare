"""Novel, chapter and entity persistence. Each repository is scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, datetime
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select

from app.kernel.contracts.models import Chapter, Entity, Novel
from app.kernel.contracts.positions import next_chapter_position
from app.kernel.db.base import ScopedRepository

# One whitespace class, both sides of the count (R31, fix round 2):
# the trim and the split derive from this one bracket expression, so
# they cannot drift. ``\s`` is the database's ``[[:space:]]`` — wider
# than ASCII, and as wide as the collation makes it; the three near
# spaces a browser counts are pinned by ``chr()`` because the database
# ctype classifies them differently than clients do. The trim strips
# the ends, the split breaks the middle, and the emptiness gate judges
# the trimmed value — never three sets, one. The web client's
# countWords (P12) repeats exactly this class; the two move together.
_WS = "[" + r"\s" + chr(0x00A0) + chr(0x2007) + chr(0x202F) + "]"
_TRIM_PATTERN = f"^{_WS}+|{_WS}+$"
_SPLIT_PATTERN = _WS + "+"


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

    async def counts(self, novel_id: UUID | None = None) -> dict[UUID, tuple[int, int]]:
        """Chapter and word counts per novel, one grouped query.

        With ``novel_id``, aggregate that novel's chapters only — the
        single-row ask needs none of the shelf's other bodies. The words
        are tokens separated by the one whitespace class (``_WS``),
        summed where the body trimmed by that same class is non-empty —
        the filter is what keeps an empty (or whitespace-only) chapter
        worth zero, which a bare split would count as its one empty
        token. Novels with no chapters have no row here; the caller
        reports the zeros.
        """
        trimmed = func.regexp_replace(Chapter.body, _TRIM_PATTERN, "", "g")
        words = func.coalesce(
            func.sum(
                func.array_length(func.regexp_split_to_array(trimmed, _SPLIT_PATTERN), 1)
            ).filter(trimmed != ""),
            0,
        )
        statement = (
            select(Chapter.novel_id, func.count(Chapter.id), words)
            .where(Chapter.user_id == self.user_id)
            .group_by(Chapter.novel_id)
        )
        if novel_id is not None:
            statement = statement.where(Chapter.novel_id == novel_id)
        rows = await self.session.execute(statement)
        return {row_novel: (chapters, word_count) for row_novel, chapters, word_count in rows}

    async def get(self, novel_id: UUID) -> Novel | None:
        return await self.session.scalar(self.query().where(Novel.id == novel_id))

    async def create(
        self,
        title: str,
        genre: str | None = None,
        blurb: str | None = None,
        *,
        author: str | None = None,
        language: str | None = None,
    ) -> Novel:
        """Flush a new novel for this user, leaving the commit to the caller."""
        novel = Novel(
            user_id=self.user_id,
            title=title,
            genre=genre,
            blurb=blurb,
            author=author,
            language=language,
        )
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

    async def create(self, novel_id: UUID, title: str) -> Chapter:
        """Append a chapter at the next position and update its novel's timestamp.

        Flush both changes without committing; an empty novel starts at position 0.
        The number comes from the one allocator every append path uses, which
        also takes the lock that keeps two writers off one number (#521).
        """
        chapter = Chapter(
            user_id=self.user_id,
            novel_id=novel_id,
            title=title,
            position=await next_chapter_position(
                self.session, user_id=self.user_id, novel_id=novel_id
            ),
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
