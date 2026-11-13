"""Novel, chapter and entity persistence. Each repository is scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, datetime
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select, update

from app.kernel.contracts.models import Chapter, Entity, Novel
from app.kernel.contracts.positions import next_chapter_position
from app.kernel.db.base import ScopedRepository


def apply_changes(row: Any, changes: dict[str, Any]) -> None:
    """Apply a field/value mapping onto a row in one place (novels + chapters)."""
    for field, value in changes.items():
        setattr(row, field, value)


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

    async def save(self, novel: Novel, changes: dict[str, Any]) -> Novel:
        """Apply a metadata edit and flush; the commit is the caller's.

        The novel is its own root — no parent to mark written-in — so
        ``updated_at`` rides the row's UPDATE through the column's
        ``onupdate``, and an empty change set writes nothing at all.
        """
        apply_changes(novel, changes)
        await self.session.flush()
        return novel

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

    async def delete(self, novel: Novel) -> None:
        """Mark the supplied novel for deletion; the caller commits the change.

        One DELETE of the one root row: the novel-scoped foreign keys cascade
        in the database (`ondelete="CASCADE"`), so the chapters, entities and
        their relations, suggestions and findings go with it — no manual
        child deletes, each of which would be a second statement the
        constraint already makes unnecessary.
        """
        await self.session.delete(novel)

    async def touch_exported(self, novel_id: UUID) -> None:
        """Stamp the novel's export trace; the caller commits the write.

        The export path's own timestamp writer, `touch_novel`'s shape for a
        different rule: only a successful export ever sets the column. One
        Core UPDATE naming both timestamps — the self-assignment is what
        keeps ``updated_at`` where it was (``renumber``'s idiom): an ORM
        flush that left the column unset would fire its ``onupdate`` and
        record the backup as the book's last write, and a later edit would
        no longer read as change against the backup the stamp names.
        """
        await self.session.execute(
            update(Novel)
            .where(Novel.id == novel_id, Novel.user_id == self.user_id)
            .values(last_exported_at=datetime.now(UTC), updated_at=Novel.updated_at)
        )


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
        await self.touch_novel(novel_id)
        await self.session.flush()
        return chapter

    async def save(self, chapter: Chapter, changes: dict[str, Any]) -> Chapter:
        """Apply an edit and mark the novel written-in; one write, one bump."""
        apply_changes(chapter, changes)
        await self.touch_novel(chapter.novel_id)
        await self.session.flush()
        return chapter

    async def delete(self, chapter: Chapter) -> None:
        """Drop the chapter and flush; the commit is the caller's.

        The flush is load-bearing: the delete must be visible to the
        survivor read that follows it, or the renumber would count the row
        it just removed. The chapter-scoped foreign key cascades in the
        database — its pending suggestions ride the delete — while the
        novel's findings, which belong to the book and not to a chapter,
        stay.
        """
        await self.session.delete(chapter)
        await self.session.flush()

    async def renumber(self, novel_id: UUID, ordered_ids: Sequence[UUID]) -> None:
        """Write each listed chapter's ordinal as its position, 0 to n-1.

        One Core UPDATE per chapter, and the timestamp is assigned its own
        value: the column's ``onupdate`` fires only for a statement that
        leaves ``updated_at`` unset, so the self-assignment is what keeps a
        survivor's "last written" where it was — a delete moved a number,
        not a hand (D8). The writes ride the caller's one transaction, where
        the deferrable constraint checks the finished set instead of each
        intermediate step (WP6 §1).
        """
        for position, chapter_id in enumerate(ordered_ids):
            await self.session.execute(
                update(Chapter)
                .where(Chapter.id == chapter_id, Chapter.novel_id == novel_id)
                .where(self.owned())
                .values(position=position, updated_at=Chapter.updated_at)
            )

    async def touch_novel(self, novel_id: UUID) -> None:
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
