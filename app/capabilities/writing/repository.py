"""Novel, chapter and entity persistence. Each repository is scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import and_, case, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert

from app.capabilities.writing.models import DailyWords
from app.kernel.contracts.models import Chapter, Entity, Novel, Scene, Series
from app.kernel.contracts.positions import next_chapter_position, next_scene_position
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


def _word_count_expression(body: Any) -> Any:
    """The one whitespace rule as a SQL expression over any body value:
    tokens of the trimmed body, zero when the trim is empty. The shelf's
    grouped sum and the activity's write-path diff count through this one
    expression, so the two cannot drift."""
    trimmed = func.regexp_replace(body, _TRIM_PATTERN, "", "g")
    return case(
        (
            trimmed != "",
            func.coalesce(
                func.array_length(func.regexp_split_to_array(trimmed, _SPLIT_PATTERN), 1), 0
            ),
        ),
        else_=0,
    )


class EntityRepository(ScopedRepository[Entity]):
    model = Entity

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Entity]:
        """Every kept entity of one novel, scoped to the user, any order —
        the continuation scan orders by first occurrence itself."""
        result = await self.session.scalars(self.query().where(Entity.novel_id == novel_id))
        return result.all()


class SeriesRepository(ScopedRepository[Series]):
    model = Series

    async def get(self, series_id: UUID) -> Series | None:
        return await self.session.scalar(self.query().where(Series.id == series_id))

    async def create(self, title: str) -> Series:
        """Flush a new series for this user, leaving the commit to the caller."""
        series = Series(user_id=self.user_id, title=title)
        self.session.add(series)
        await self.session.flush()
        return series


class NovelRepository(ScopedRepository[Novel]):
    model = Novel

    async def list(self, *, include_archived: bool = False) -> Sequence[Novel]:
        """The shelf's novels, newest first. Archived books stay out of
        the main grid unless ``include_archived`` asks for them — the
        archive view's one knob, default the shelf's own answer."""
        statement = self.query().order_by(Novel.created_at.desc())
        if not include_archived:
            statement = statement.where(Novel.archived_at.is_(None))
        result = await self.session.scalars(statement)
        return result.all()

    async def series_titles(self, novels: Sequence[Novel]) -> dict[UUID, str]:
        """The linked series' title per novel, one scoped query.

        Only the ids the novels actually carry are asked for, and the
        user predicate rides the series row too: a link can only name a
        series the update path already proved owned, and the read keeps
        that promise without trusting it. Novels without a link — or
        whose series is gone — have no entry; the caller reports None.
        """
        series_ids = {novel.series_id for novel in novels if novel.series_id is not None}
        if not series_ids:
            return {}
        rows = await self.session.execute(
            select(Series.id, Series.title).where(
                Series.user_id == self.user_id, Series.id.in_(series_ids)
            )
        )
        # ``.all()`` before ``dict``: the Result itself carries keys(), so
        # dict() would read it as a mapping and subscript it — the rows
        # are the pairs, not the result.
        titles = dict(rows.all())
        return {
            novel.id: titles[novel.series_id]
            for novel in novels
            if novel.series_id is not None and novel.series_id in titles
        }

    async def counts(self, novel_id: UUID | None = None) -> dict[UUID, tuple[int, int]]:
        """Chapter and word counts per novel, one grouped query.

        With ``novel_id``, aggregate that novel's chapters only — the
        single-row ask needs none of the shelf's other bodies. The words
        are the novel's SCENES now (W4 §5): a chapter is a grouping shell,
        its prose lives on its scenes, so the sum rides a left join from
        chapters to scenes — a chapter with no scenes still counts as a
        chapter and contributes zero words. Tokens are separated by the one
        whitespace class (``_WS``), counted by the one expression the
        activity's diff uses too — an empty (or whitespace-only) body is
        worth zero, which a bare split would count as its one empty token.
        The distinct chapter count keeps a chapter with several scenes from
        multiplying into several chapters. Novels with no chapters have no
        row here; the caller reports the zeros.
        """
        words = func.coalesce(func.sum(_word_count_expression(Scene.body)), 0)
        statement = (
            select(Chapter.novel_id, func.count(func.distinct(Chapter.id)), words)
            .outerjoin(Scene, and_(Scene.chapter_id == Chapter.id, Scene.user_id == self.user_id))
            .where(Chapter.user_id == self.user_id)
            .group_by(Chapter.novel_id)
        )
        if novel_id is not None:
            statement = statement.where(Chapter.novel_id == novel_id)
        rows = await self.session.execute(statement)
        return {row_novel: (chapters, word_count) for row_novel, chapters, word_count in rows}

    async def get(self, novel_id: UUID) -> Novel | None:
        return await self.session.scalar(self.query().where(Novel.id == novel_id))

    async def oldest(self) -> Novel | None:
        """The user's first book — the oldest ``created_at``, the one setup
        created in the same transaction as the user. The atelier's answers
        live on its row; the create path reads it once, without a lock: a
        create has no concurrent writer of the source row's settings.
        Archived books count — archiving is the shelf's organization, not
        an erasure of the answers. None while the user owns no novel."""
        return await self.session.scalar(self.query().order_by(Novel.created_at.asc()).limit(1))

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
        target_words: int | None = None,
        author_typology: str | None = None,
        dramatic_form: str | None = None,
        ai_role: str | None = None,
        canon_strictness: int | None = None,
    ) -> Novel:
        """Flush a new novel for this user, leaving the commit to the caller.

        The wizard's four settings ride as given — the service copies them
        from the atelier's first book; absent, they stay NULL, the honest
        no-answer.
        """
        novel = Novel(
            user_id=self.user_id,
            title=title,
            genre=genre,
            blurb=blurb,
            author=author,
            language=language,
            target_words=target_words,
            author_typology=author_typology,
            dramatic_form=dramatic_form,
            ai_role=ai_role,
            canon_strictness=canon_strictness,
        )
        self.session.add(novel)
        await self.session.flush()
        return novel

    async def duplicate(self, source: Novel, title: str) -> Novel:
        """Flush a copy of the novel for this user, leaving the commit to the caller.

        The book's own facts ride along: genre, blurb, the export's front
        matter, the wizard's settings, status and the series link. The
        shelf's tracking starts fresh — no volume (the number belongs to
        the original's place in the series), no archive stamp (the copy
        is on the shelf) and no export trace (it has never been exported).
        The timestamps are the copy's own, from the columns' defaults.
        """
        novel = Novel(
            user_id=self.user_id,
            title=title,
            genre=source.genre,
            blurb=source.blurb,
            author=source.author,
            language=source.language,
            target_words=source.target_words,
            author_typology=source.author_typology,
            dramatic_form=source.dramatic_form,
            ai_role=source.ai_role,
            canon_strictness=source.canon_strictness,
            status=source.status,
            series_id=source.series_id,
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

    async def copy_into(self, novel_id: UUID, chapters: Sequence[Chapter]) -> Sequence[Chapter]:
        """Flush copies of the chapters into a new novel, positions preserved.

        The copies are new rows — titles and positions as read, timestamps
        their own. The prose is not copied here: it lives on the scenes now
        (W4 §5), and the caller hangs each original's scenes off its own copy
        (``SceneRepository.copy_into``). No allocator and no lock: the target
        novel is brand new, so no other writer can append to it before this
        transaction commits, and the position invariant holds without
        the lock every append to a live book takes. The caller commits
        the copies together with the novel row. The copies come back in
        the order they were given, so the caller can hang each original's
        scenes off its own copy (W4 — the prose rides the scenes now).
        """
        copies = [
            Chapter(
                user_id=self.user_id,
                novel_id=novel_id,
                title=chapter.title,
                position=chapter.position,
            )
            for chapter in chapters
        ]
        self.session.add_all(copies)
        await self.session.flush()
        return copies

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


class SceneRepository(ScopedRepository[Scene]):
    model = Scene

    async def list_for_chapter(self, chapter_id: UUID) -> Sequence[Scene]:
        result = await self.session.scalars(
            self.query().where(Scene.chapter_id == chapter_id).order_by(Scene.position)
        )
        return result.all()

    async def get(self, scene_id: UUID) -> Scene | None:
        return await self.session.scalar(self.query().where(Scene.id == scene_id))

    async def counts(self, chapter_ids: Sequence[UUID]) -> dict[UUID, tuple[int, int]]:
        """Scene and word counts per chapter, one grouped query — the
        chapter read's derived figures. The words are tokens separated by
        the one whitespace class, counted by the one expression the
        activity's diff uses too. Chapters with no scenes have no row
        here; the caller reports the zeros (D16 — an empty chapter is real).
        """
        if not chapter_ids:
            return {}
        words = func.coalesce(func.sum(_word_count_expression(Scene.body)), 0)
        rows = await self.session.execute(
            select(Scene.chapter_id, func.count(Scene.id), words)
            .where(self.owned(), Scene.chapter_id.in_(chapter_ids))
            .group_by(Scene.chapter_id)
        )
        return {chapter: (scenes, word_count) for chapter, scenes, word_count in rows}

    async def count_words(self, *bodies: str) -> list[int]:
        """Word counts of the given bodies in one SELECT — the shelf's own
        rule, so the activity's diff and the shelf's totals agree. The
        bodies ride as bind parameters and the database does the counting;
        the order of the answers is the order of the bodies."""
        if not bodies:
            return []
        row = (
            await self.session.execute(
                select(*(_word_count_expression(literal(body)) for body in bodies))
            )
        ).one()
        return [int(words) for words in row]

    async def committed_body(self, scene_id: UUID) -> str | None:
        """The scene's body as committed, read fresh — the caller holds
        the novel lock, so this is the body the activity's diff counts
        from. A column SELECT bypasses the identity map by construction:
        the row the session loaded before the lock may predate a
        concurrent save (a double-fired autosave), and a diff counted
        from that stale snapshot would land on the day's row twice. The
        lock is the allocator's own — the second writer waits, then reads
        the first writer's committed scene (positions.py). None when
        the row is gone; the caller's own write path answers for that."""
        return await self.session.scalar(
            select(Scene.body).where(Scene.id == scene_id, Scene.user_id == self.user_id)
        )

    async def committed_chapter_words(self, chapter_id: UUID) -> int:
        """The words the chapter's scenes hold as committed, read fresh —
        the sum a chapter delete counts negative on today's activity row.
        The aggregate SELECT bypasses the identity map by construction: a
        concurrent scene save that grew the chapter after this session's
        pre-lock read must not stale the subtraction. The caller holds the
        novel lock, so this is the prose the book holds at the delete."""
        words = await self.session.scalar(
            select(func.coalesce(func.sum(_word_count_expression(Scene.body)), 0)).where(
                Scene.chapter_id == chapter_id, Scene.user_id == self.user_id
            )
        )
        return int(words or 0)

    async def create(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        title: str,
        body: str,
        setting: str | None,
        story_time: str | None,
    ) -> Scene:
        """Append a scene at the next position and update its novel's timestamp.

        Flush both changes without committing; an empty chapter starts at
        position 1 (the migration's wrap, the written-out ordinal). The
        number comes from the one allocator every scene append uses, which
        also takes the book's row lock that keeps two writers off one
        number (#521, one level down).
        """
        scene = Scene(
            user_id=self.user_id,
            chapter_id=chapter_id,
            title=title,
            body=body,
            setting=setting,
            story_time=story_time,
            position=await next_scene_position(
                self.session, user_id=self.user_id, novel_id=novel_id, chapter_id=chapter_id
            ),
        )
        self.session.add(scene)
        await self.touch_novel(novel_id)
        await self.session.flush()
        return scene

    async def copy_into(self, chapter_id: UUID, scenes: Sequence[Scene]) -> None:
        """Flush copies of the scenes into a new chapter, positions preserved.

        The copies are new rows — titles, bodies, the overline and in-story
        label and positions as read, timestamps their own. No allocator and
        no lock: the target chapter belongs to a brand-new novel, so no
        other writer can append to it before this transaction commits. The
        caller commits the copies together with the novel row.
        """
        self.session.add_all(
            [
                Scene(
                    user_id=self.user_id,
                    chapter_id=chapter_id,
                    title=scene.title,
                    body=scene.body,
                    setting=scene.setting,
                    story_time=scene.story_time,
                    position=scene.position,
                )
                for scene in scenes
            ]
        )
        await self.session.flush()

    async def save(self, scene: Scene, changes: dict[str, Any], novel_id: UUID) -> Scene:
        """Apply an edit and mark the novel written-in; one write, one bump."""
        apply_changes(scene, changes)
        await self.touch_novel(novel_id)
        await self.session.flush()
        return scene

    async def renumber(self, chapter_id: UUID, ordered_ids: Sequence[UUID]) -> None:
        """Write each listed scene's ordinal as its position, 1 to n.

        One Core UPDATE per scene, and the timestamp is assigned its own
        value: the column's ``onupdate`` fires only for a statement that
        leaves ``updated_at`` unset, so the self-assignment is what keeps a
        survivor's "last written" where it was — a delete moved a number,
        not a hand (D8). The writes ride the caller's one transaction, where
        the deferrable constraint checks the finished set instead of each
        intermediate step (#521, the chapters invariant one level down).
        """
        for position, scene_id in enumerate(ordered_ids, start=1):
            await self.session.execute(
                update(Scene)
                .where(Scene.id == scene_id, Scene.chapter_id == chapter_id)
                .where(self.owned())
                .values(position=position, updated_at=Scene.updated_at)
            )

    async def touch_novel(self, novel_id: UUID) -> None:
        """Advance the parent novel's updated_at from a scene write.

        The column's onupdate fires only for the row an UPDATE statement
        touches — the scene — and cannot reach the novel, whose row the
        write would otherwise leave alone. The start page reads the novel's
        timestamp to decide what was last written in, so the bump is here,
        with the write that earns it. The scene's parent is the chapter,
        but the book's row is the one the shelf reads and the lock holds.
        """
        novel = await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )
        if novel is not None:
            novel.updated_at = datetime.now(UTC)


class DailyWordsRepository(ScopedRepository[DailyWords]):
    model = DailyWords

    async def add_words(self, novel_id: UUID, day: date, delta: int) -> None:
        """Accumulate one day's net words for a novel; the commit is the caller's.

        One upsert against the (novel_id, date) primary key: the day's
        first write inserts, every later one adds to the row in the
        database — two writers on one day serialize at the constraint
        instead of racing a read-modify-write. The delta may be negative
        (text removed); the row keeps the honest net, no floor of zero.
        A zero delta is the caller's skip: nothing was written.
        """
        statement = insert(DailyWords).values(
            user_id=self.user_id, novel_id=novel_id, date=day, words=delta
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["novel_id", "date"],
                set_={"words": DailyWords.words + statement.excluded.words},
            )
        )

    async def daily_totals(self, through: date) -> dict[date, int]:
        """Net words per day across the user's novels, through ``through``.

        One grouped query over the scoped rows — the user predicate rides
        the activity row itself, no join through the novel. Days without
        a row are the caller's zeros. The streak walks past the display
        window, so the read is bounded by today, not by the window.
        """
        rows = await self.session.execute(
            select(DailyWords.date, func.sum(DailyWords.words))
            .where(self.owned(), DailyWords.date <= through)
            .group_by(DailyWords.date)
        )
        return {day: int(words) for day, words in rows}
