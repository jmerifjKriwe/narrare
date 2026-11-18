"""Writing logic. Routers delegate here; this module knows the unit of work."""

import contextlib
import zlib
from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID  # noqa: TC003
from zipfile import BadZipFile

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.writing.metadata import (
    InvalidNovelUpdateError,
    duplicated_title,
    normalized_novel_updates,
)
from app.capabilities.writing.prompts import PredecessorScene, render_continuation, scaffold_length
from app.capabilities.writing.repository import (
    ChapterRepository,
    DailyWordsRepository,
    EntityRepository,
    NovelRepository,
    SceneRepository,
    SeriesRepository,
)
from app.capabilities.writing.schemas import (
    ActivityPoint,
    ActivityRead,
    ChapterRead,
    ChapterUpdate,
    ExportDone,
    NovelRead,
    NovelUpdate,
    SceneCreate,
    SceneRead,
    SceneUpdate,
)
from app.kernel.auth import SetupRequiredError
from app.kernel.context import allocate
from app.kernel.contracts.models import (
    WORD_GOAL_MAX,
    WORD_GOAL_MIN,
    Chapter,
    Entity,
    Novel,
    Scene,
    Series,
    User,
)
from app.kernel.contracts.positions import lock_novel
from app.kernel.interchange import (
    ArchiveError,
    ArchiveTree,
    open_directory,
    open_zip,
    write_directory,
    zip_bytes,
)
from app.kernel.interchange import engine as interchange_engine


class NotFoundError(Exception):
    """The row does not exist or belongs to another user; the two are one answer."""


class TargetNotEmptyError(Exception):
    """The export target exists and is non-empty; `path` names it."""

    def __init__(self, path: str) -> None:
        super().__init__(f"target not empty: {path}")
        self.path = path


class OrderMismatchError(Exception):
    """The body is not the parent's current whole of ids — a novel's chapters
    or a chapter's scenes; `current` is, in position order — the arrangement
    the client reverts to."""

    def __init__(self, current: list[UUID]) -> None:
        super().__init__("order mismatch")
        self.current = current


class ArchiveTooLargeError(Exception):
    """The archive is larger than MAX_ARCHIVE_BYTES."""


class ArchiveInvalidError(Exception):
    """The archive is unreadable or malformed; `file` names the offender."""

    def __init__(self, file: str, reason: str) -> None:
        super().__init__(f"{file}: {reason}")
        self.file = file
        self.reason = reason


class DuplicateSeriesError(Exception):
    """The user already owns a series with this name — one atelier, one
    series per name (the settings select resolves links by title)."""


class FieldRefusedError(ValueError):
    """The request breaks a field contract; `fields` names them.

    The settings gate's pattern: the router turns each field into a 422
    loc entry, so the client learns exactly which input was refused.
    """

    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.fields = fields


MAX_ARCHIVE_BYTES = 20_000_000
"""One archive, at most — read whole before it is parsed, so an unbounded
upload would hold the worker for no good novel (the knowledge cap's reason)."""

_ARCHIVE = "<archive>"
"""The whole archive, when no single file is at fault — the engine's own word."""


class WritingService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.novels = NovelRepository(session, user_id)
        self.chapters = ChapterRepository(session, user_id)
        self.scenes = SceneRepository(session, user_id)
        self.entities = EntityRepository(session, user_id)
        self.series = SeriesRepository(session, user_id)
        self.daily_words = DailyWordsRepository(session, user_id)

    async def _require_user(self) -> User:
        """Writes belong to a user that setup created; without one there is
        nothing to own the row, and the foreign key would say so at the worst
        possible time. The guard says it in the response instead. The row
        comes back for the callers that read the atelier's answers off it."""
        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError
        return user

    async def create_novel(
        self,
        title: str,
        genre: str | None = None,
        blurb: str | None = None,
        target_words: int | None = None,
    ) -> Novel:
        """Commit a novel with optional genre, blurb and word target; return
        the created row.

        The new-book dialog's inheritance note is the row's truth: the four
        wizard settings — author typology, dramatic form, AI role and canon
        strictness — are copied from the atelier's first book (the oldest
        ``created_at``, the one setup created). One read, no lock: a create
        has no concurrent writer of the source row's settings, and the copy
        never writes the source. A column without an answer stays without
        one; no source book at all leaves all four NULL. The atelier's
        standard author name rides the same promise (W4 Task 19, D22 — the
        book-settings note „wird automatisch in neue Manuskripte eingesetzt"):
        the user row's ``author_name`` becomes the new book's author, the
        unset name stays unset — the email label is the chrome's rendering,
        never a guessed book author.

        Raise SetupRequiredError if setup has not created the owning user.
        """
        user = await self._require_user()
        # Fold an empty/whitespace genre to None at the create boundary, the
        # way PATCH does, so "no genre" is one value everywhere.
        genre = (genre or "").strip() or None
        atelier = await self.novels.oldest()
        novel = await self.novels.create(
            title,
            genre=genre,
            blurb=blurb,
            target_words=target_words,
            author=user.author_name,
            author_typology=atelier.author_typology if atelier is not None else None,
            dramatic_form=atelier.dramatic_form if atelier is not None else None,
            ai_role=atelier.ai_role if atelier is not None else None,
            canon_strictness=atelier.canon_strictness if atelier is not None else None,
        )
        await self.session.commit()
        return novel

    async def list_novels(self, *, include_archived: bool = False) -> Sequence[NovelRead]:
        """The shelf's rows, each carrying its derived counts and series.

        The counts arrive as one grouped query (never one per novel, the
        bodies never in Python) and the series titles as one scoped
        lookup; the rows are the response shape because only they can
        carry what the raw novel has no column for. Archived books stay
        out unless ``include_archived`` asks for them.
        """
        novels = await self.novels.list(include_archived=include_archived)
        counts = await self.novels.counts()
        titles = await self.novels.series_titles(novels)
        return [
            self._with_counts(novel, counts.get(novel.id, (0, 0)), titles.get(novel.id))
            for novel in novels
        ]

    async def get_novel(self, novel_id: UUID) -> NovelRead:
        novel = await self.novels.get(novel_id)
        if novel is None:
            raise NotFoundError
        titles = await self.novels.series_titles([novel])
        return self._with_counts(
            novel,
            (await self.novels.counts(novel_id)).get(novel_id, (0, 0)),
            titles.get(novel.id),
        )

    def _with_counts(
        self, novel: Novel, counts: tuple[int, int], series_title: str | None = None
    ) -> NovelRead:
        """One novel row as the response shape, its derived facts filled in."""
        chapter_count, word_count = counts
        return NovelRead.model_validate(novel).model_copy(
            update={
                "chapter_count": chapter_count,
                "word_count": word_count,
                "series_title": series_title,
            }
        )

    async def update_novel(self, novel_id: UUID, changes: NovelUpdate) -> NovelRead:
        """Correct a novel's metadata fields: only the fields the body carries.

        The values are checked by ``metadata.normalized_novel_updates``, so a
        hand-written call cannot skip the contract: it normalizes only the
        carried fields and refuses an invalid one by name. The series link
        is checked here, where the database is: a carried ``series_id``
        must name a series the user owns, a carried ``series_volume``
        needs a series to belong to after the update, and leaving a
        series takes the volume number with it — the number belongs to
        the link, not the book.
        ``model_fields_set`` is what makes the update partial: a field the
        body does not carry is not a change, and a carried ``null`` is one —
        the cleared state. The write is one UPDATE through the repository's
        save, and ``updated_at`` rides it through the column's ``onupdate``,
        so an edit makes the export trace honestly stale; an empty body
        carries no field and writes nothing.

        Commit and return the novel, its derived facts filled the way the
        read paths fill them. Raise NotFoundError if it is absent or
        unowned, or InvalidNovelUpdateError for an invalid field, named.
        """
        novel = await self.novels.get(novel_id)
        if novel is None:
            raise NotFoundError
        updates = normalized_novel_updates(changes)
        if changes.series_id is not None and await self.series.get(changes.series_id) is None:
            raise InvalidNovelUpdateError("series_id")
        if changes.series_volume is not None:
            linked = updates.get("series_id", novel.series_id)
            if linked is None:
                raise InvalidNovelUpdateError("series_volume")
        if "series_id" in updates and updates["series_id"] is None:
            updates["series_volume"] = None
        # An empty body carries no field and must not advance updated_at:
        # save nothing, commit nothing, so "last written" stays where it was.
        if updates:
            novel = await self.novels.save(novel, updates)
            await self.session.commit()
        titles = await self.novels.series_titles([novel])
        return self._with_counts(
            novel,
            (await self.novels.counts(novel_id)).get(novel_id, (0, 0)),
            titles.get(novel.id),
        )

    async def create_series(self, title: str) -> Series:
        """Commit a new series for this user: the name trimmed like a
        book's, a whitespace-only one refused by field (the schema carries
        the width), a name the user already carries refused as a duplicate
        (409) — the select resolves a book's link by title, so one atelier
        holds one series per name. The check is the service's own: two
        concurrent creates of one name remain a race window no constraint
        closes (disclosed); the book-settings link rides the novel PATCH's
        own series check.

        Raise SetupRequiredError if setup has not created the owning user.
        """
        await self._require_user()
        name = title.strip()
        if not name:
            raise FieldRefusedError(("title",), "a series needs a name")
        if await self.series.find_by_title(name) is not None:
            raise DuplicateSeriesError
        series = await self.series.create(name)
        await self.session.commit()
        return series

    async def list_series(self) -> Sequence[Series]:
        """The user's own series, alphabetical — the settings select's list."""
        return await self.series.list()

    async def delete_novel(self, novel_id: UUID) -> None:
        """Delete a novel: the row goes, and everything it carried goes with it.

        The novel-scoped foreign keys cascade in the database — chapters,
        entities, suggestions, findings, and the entities' relations ride
        their ends — so one delete of the root row is the whole book, and
        the export is the safety net. Documents are the library's, not the
        novel's, and survive. Commit the deletion; raise NotFoundError for
        an absent or unowned novel.
        """
        result = await self.session.execute(
            delete(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )
        if getattr(result, "rowcount", 0) == 0:
            raise NotFoundError
        await self.session.commit()

    async def duplicate_novel(self, novel_id: UUID) -> NovelRead:
        """Copy a novel and all its chapters as one new book, in one transaction.

        The copy carries the book's own facts — genre, blurb, the export's
        front matter, the wizard's settings, status and the series link —
        under the name ``„<title> (Kopie)"``. The shelf's tracking starts
        fresh: no volume (the number belongs to the original's place in
        the series), no archive stamp (the copy is on the shelf) and no
        export trace (it has never been exported). The chapters ride with
        titles and positions as read, and each chapter's scenes with their
        prose, overline and in-story label; the new novel has no other
        writers yet, so the positions need no allocator's lock. Novel,
        chapters and scenes commit together or not at all.

        Return the copy with its derived facts, the read paths' shape.
        Raise SetupRequiredError if setup has not created the owning user,
        or NotFoundError for an absent or unowned novel.
        """
        await self._require_user()
        novel = await self.novels.get(novel_id)
        if novel is None:
            raise NotFoundError
        chapters = await self.chapters.list_for_novel(novel_id)
        copy = await self.novels.duplicate(novel, duplicated_title(novel.title))
        copied_chapters = await self.chapters.copy_into(copy.id, chapters)
        # The prose rides the scenes now: each original chapter's scenes
        # copy into its own copy, positions and labels preserved.
        for original, copied in zip(chapters, copied_chapters, strict=True):
            scenes = await self.scenes.list_for_chapter(original.id)
            await self.scenes.copy_into(copied.id, scenes)
        await self.session.commit()
        titles = await self.novels.series_titles([copy])
        return self._with_counts(
            copy,
            (await self.novels.counts(copy.id)).get(copy.id, (0, 0)),
            titles.get(copy.id),
        )

    async def activity(self, days: int = 30) -> ActivityRead:
        """The atelier's activity across all the user's novels.

        ``points`` cover the requested window oldest-first, zero-days
        included; ``streak_days`` counts consecutive days with a nonzero
        net ending today — or yesterday, which keeps the streak alive
        until the day after tomorrow without writing; ``weekly_average``
        is the mean net words per day over ALL days of the window, one
        decimal; ``today_words`` is today's net. The day boundary is the
        server's UTC date, the clock every other timestamp here rides.

        The daily goal (W4 row 25) is the user's stored answer — the
        settings PATCH owns the write; an absent user row or a null
        column is the honest unset, never a book target standing in.
        The progress is derived here the way the streak and the average
        are: met when today's net reaches the goal, remaining what the
        day still owes (a negative day owes the removal too).
        """
        today = datetime.now(UTC).date()
        totals = await self.daily_words.daily_totals(today)
        start = today - timedelta(days=days - 1)
        points = [
            ActivityPoint(date=day, words=totals.get(day, 0))
            for day in (start + timedelta(days=offset) for offset in range(days))
        ]
        # The streak anchors on today when today has a nonzero net, else on
        # yesterday — a streak survives until the day after tomorrow without
        # writing — and walks back through consecutive nonzero days. A day
        # nets across novels first: +50 in one book and -50 in another is a
        # zero day, not two active ones. The walk is not bounded by the
        # window: a 40-day streak reads 40 on a 7-day window.
        anchor = today if totals.get(today, 0) != 0 else today - timedelta(days=1)
        streak = 0
        day = anchor
        while totals.get(day, 0) != 0:
            streak += 1
            day -= timedelta(days=1)
        # The average's basis is every day of the window, zero-days included:
        # the honest daily rate, rest days and all. The net is the numerator,
        # so a window that removed more than it wrote averages negative.
        today_words = totals.get(today, 0)
        user = await self.session.get(User, self.user_id)
        goal = user.daily_goal_words if user is not None else None
        return ActivityRead(
            points=points,
            streak_days=streak,
            weekly_average=round(sum(point.words for point in points) / days, 1),
            today_words=today_words,
            daily_goal_words=goal,
            goal_met=goal is not None and today_words >= goal,
            goal_remaining=max(0, goal - today_words) if goal is not None else 0,
        )

    async def create_chapter(self, novel_id: UUID, title: str) -> Chapter:
        await self._require_user()
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        # The same rule as the update: spaces are not a name, and "" after
        # the trim is the honest unnamed.
        chapter = await self.chapters.create(novel_id, title.strip())
        # A chapter is born an empty shell: no scenes yet, zero words — the
        # activity has nothing to record until the first scene lands. The
        # router reads it as ChapterRead, whose derived defaults (0, 0) are
        # the fresh chapter's honest figures.
        await self.session.commit()
        return chapter

    async def list_chapters(self, novel_id: UUID) -> Sequence[ChapterRead]:
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        chapters = await self.chapters.list_for_novel(novel_id)
        counts = await self.scenes.counts([chapter.id for chapter in chapters])
        return [
            self._chapter_with_counts(chapter, counts.get(chapter.id, (0, 0)))
            for chapter in chapters
        ]

    async def get_chapter(self, chapter_id: UUID) -> Chapter:
        """The chapter row, scoped — the internal getter the write paths and
        the continuation build on. The router's read door is ``read_chapter``,
        which carries the scene-derived figures the raw row has no column for."""
        chapter = await self.chapters.get(chapter_id)
        if chapter is None:
            raise NotFoundError
        return chapter

    async def read_chapter(self, chapter_id: UUID) -> ChapterRead:
        chapter = await self.get_chapter(chapter_id)
        counts = await self.scenes.counts([chapter.id])
        return self._chapter_with_counts(chapter, counts.get(chapter.id, (0, 0)))

    def _chapter_with_counts(self, chapter: Chapter, counts: tuple[int, int]) -> ChapterRead:
        """One chapter row as the response shape, its scene-derived facts filled."""
        scene_count, word_count = counts
        return ChapterRead.model_validate(chapter).model_copy(
            update={"scene_count": scene_count, "word_count": word_count}
        )

    async def continuation_prompt(
        self,
        scene_id: UUID,
        *,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
        model: str | None = None,
        prompt: str | None = None,
    ) -> str:
        """The prompt for a scene continuation, or NotFoundError if the scene is not ours.

        `allocate` runs before any gathering, so an impossible pair refuses
        before the database is touched. The three facts default to unset —
        the allocator's own not-yet-resolved fallbacks (D7); the router passes
        the resolved profile's values. The render walks the override chain at
        the scene's novel scope and can refuse by name (`PromptRenderError`)
        when an override's glue grows past the immediate slice. Read-only: the
        streamed answer comes back to the editor, whose autosave writes it.
        The request that streams has no side effect of its own (D14).

        The unit is the scene (W4 §5). The tail is the active scene's own prose;
        the predecessors are the book's earlier scenes in reading order walked
        backwards — the active chapter's earlier scenes (reverse position), then
        earlier chapters' scenes (chapter reverse, scenes reverse within each),
        nearest first, chapter titles as separators. The budgeting machinery is
        the chapter predecessors' own, refined onto scenes: each scene's tail is
        hard-cut to the slice's remaining room and a scene that does not fit
        stops the packing.

        The optional writer instruction (W4 D5) rides the same budgets: the
        schema bounds it (the chat question's 1-2000), the render charges its
        block to the immediate slice — the entity scan window shrinks by it,
        the tail shrinks by it, and a block the slice cannot hold refuses
        `BudgetImpossibleError` before any provider call. None is today's
        continuation, byte for byte.
        """
        budgets = allocate(
            context_window=context_window, max_output_tokens=max_output_tokens, model=model
        )
        scene = await self.get_scene(scene_id)
        chapter = await self.get_chapter(scene.chapter_id)
        novel = await self.novels.get(chapter.novel_id)
        # Only the characters that survive into the rendered tail can name an
        # entity: the fixed scaffolding (header, Text-so-far, instruction) is
        # never part of the tail, so scanning it would rank entities that the
        # builder never renders and spend entity budget on them.
        scan_window = budgets.immediate_text - scaffold_length(
            novel.title if novel else "", chapter.title, prompt
        )
        tail = scene.body[-scan_window:] if scan_window > 0 else ""
        folded = tail.casefold()
        ranked: list[tuple[int, Entity]] = []
        for entity in await self.entities.list_for_novel(chapter.novel_id):
            positions = [
                index
                for index in (
                    folded.find(candidate.casefold())
                    for candidate in (entity.name, *entity.aliases)
                )
                if index >= 0
            ]
            if positions:
                ranked.append((min(positions), entity))
        ranked.sort(key=lambda pair: (pair[0], pair[1].name))
        predecessors = await self._continuation_predecessors(scene, chapter)
        return await render_continuation(
            self.session,
            self.user_id,
            chapter.novel_id,
            budgets=budgets,
            novel_title=novel.title if novel else "",
            chapter_title=chapter.title,
            body=scene.body,
            entities=[entity for _, entity in ranked],
            predecessors=predecessors,
            genre=novel.genre if novel else None,
            blurb=novel.blurb if novel else None,
            active_chapter_id=chapter.id,
            prompt=prompt,
        )

    async def _continuation_predecessors(
        self, scene: Scene, chapter: Chapter
    ) -> list[PredecessorScene]:
        """The book's earlier scenes, nearest first — the continuation's context.

        One scoped read of the novel's scenes in book reading order (chapter
        position, then scene position) and one of its chapters: the active
        chapter's earlier scenes reverse, then earlier chapters reverse with
        each chapter's scenes reverse. The active scene itself is excluded
        (only positions before it), and so is everything after it in reading
        order — a continuation builds on what precedes the cursor, not on what
        follows. Each entry carries its chapter's id and title so the packer
        can separate chapters without repeating the active chapter's header.
        """
        chapters = await self.chapters.list_for_novel(chapter.novel_id)
        by_chapter: dict[UUID, list[Scene]] = {}
        for earlier_scene in await self.scenes.list_for_novel(chapter.novel_id):
            by_chapter.setdefault(earlier_scene.chapter_id, []).append(earlier_scene)
        predecessors: list[PredecessorScene] = []
        # The active chapter's earlier scenes: nearest first, no separator (they
        # share the header's chapter). by_chapter holds them in position order.
        for earlier_scene in reversed(by_chapter.get(chapter.id, [])):
            if earlier_scene.position < scene.position:
                predecessors.append(PredecessorScene(chapter.id, chapter.title, earlier_scene.body))
        # Earlier chapters, nearest chapter first; each chapter's scenes nearest
        # first beneath its title separator.
        for earlier_chapter in reversed(chapters):
            if earlier_chapter.position < chapter.position:
                for earlier_scene in reversed(by_chapter.get(earlier_chapter.id, [])):
                    predecessors.append(
                        PredecessorScene(
                            earlier_chapter.id, earlier_chapter.title, earlier_scene.body
                        )
                    )
        return predecessors

    async def update_chapter(self, chapter_id: UUID, changes: ChapterUpdate) -> ChapterRead:
        """Commit a chapter's title and word-goal edits, and update the parent
        novel's timestamp.

        A chapter is a grouping shell now (W4 D1/D2): its prose lives on its
        scenes, so this door carries the title and the chapter's own word
        goal (W4 Task 19, D8/D20) — the body write moved to the scene. A
        carried title is trimmed here, in the service, so a hand-written call
        cannot skip it: spaces are not a name, and ``""`` after the trim is
        the chapter returned to unnamed — stored as it is, with the list's
        placeholder a rendering of it. Over-long stays the schema's 422.
        The goal is present-and-nullable through ``model_fields_set`` (the
        novel update's rule): an absent field keeps the stored goal, a
        carried ``null`` clears it, and a value outside the kernel
        contract's shared word-goal bounds is refused by name. A title or
        goal edit writes no activity — the atelier's ledger follows the
        prose, which the scene writes feed.

        The book's row is locked before the chapter's: the save's flush
        takes the chapter row, and a delete or reorder holding the book's
        row rewrites chapter rows under it — the same two rows, so the one
        order (book first, the delete's and the reorder's) is what keeps
        the pair from waiting on each other's row (Postgres 40P01).

        Return the chapter with its scene-derived figures; raise
        NotFoundError if it is absent or another user's, or
        InvalidNovelUpdateError for a goal outside the bounds, named.
        """
        chapter = await self.get_chapter(chapter_id)
        await lock_novel(self.session, user_id=self.user_id, novel_id=chapter.novel_id)
        updates: dict[str, object] = {}
        if changes.title is not None:
            updates["title"] = changes.title.strip()
        if "target_words" in changes.model_fields_set:
            goal = changes.target_words
            if goal is not None and not WORD_GOAL_MIN <= goal <= WORD_GOAL_MAX:
                raise InvalidNovelUpdateError("target_words")
            updates["target_words"] = goal
        chapter = await self.chapters.save(chapter, updates)
        await self.session.commit()
        counts = await self.scenes.counts([chapter.id])
        return self._chapter_with_counts(chapter, counts.get(chapter.id, (0, 0)))

    async def delete_chapter(self, chapter_id: UUID) -> None:
        """Delete one chapter and close the gap it leaves in the numbering.

        The delete, the survivors' renumber and the novel's timestamp bump
        are one transaction, so the rail never shows a missing number —
        held under the book's row lock, the one every append takes: a
        chapter created beside the delete either commits before the
        survivors are read (and is renumbered with them) or waits and
        allocates the number after the gap closed. The renumber moves a
        position, never a "last written" — ``renumber`` pins each
        survivor's ``updated_at`` to itself, and the novel's row is the
        one that advances: the archive lost a chapter (D8). The chapter's
        scenes and pending suggestions ride the foreign key's cascade;
        findings are the novel's and stay. The removed scenes' words count
        negative on today's activity row, in the same transaction. Raise
        NotFoundError for an absent or unowned chapter.
        """
        chapter = await self.get_chapter(chapter_id)
        novel_id = chapter.novel_id
        await lock_novel(self.session, user_id=self.user_id, novel_id=novel_id)
        # The chapter's prose lives on its scenes now, and the cascade takes
        # them with the row — so the day loses the words the scenes hold,
        # re-read fresh under the lock: the get above may predate a
        # concurrent scene save, and the day must lose the words the book
        # holds, not the ones this session remembers.
        removed_words = await self.scenes.committed_chapter_words(chapter_id)
        result = await self.session.execute(
            delete(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == self.user_id)
        )
        if getattr(result, "rowcount", 0) == 0:
            raise NotFoundError
        survivors = await self.chapters.list_for_novel(novel_id)
        await self.chapters.renumber(novel_id, [survivor.id for survivor in survivors])
        await self.chapters.touch_novel(novel_id)
        if removed_words:
            await self.daily_words.add_words(novel_id, datetime.now(UTC).date(), -removed_words)
        await self.session.commit()

    async def reorder_chapters(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> None:
        """Rewrite the novel's chapter order as the one whole the body carries.

        The body must be exactly the book's current ids — the same set, the
        same length. Both the comparison and the rewrite sit under the
        novel-row lock, the one every append takes: a chapter added or
        deleted beside the reorder either commits before the read (and the
        body, now short or long, is refused) or waits and takes its number
        after the rewrite. A body that repeats an id is refused the same
        way — its set or its length is wrong; the comparison is exact, no
        intersection. On a mismatch nothing is written and
        ``OrderMismatchError`` carries the stored ids in their position
        order, what the client reverts to. The rewrite is ``renumber``
        (each row's ``updated_at`` pinned to itself: an arrangement is not
        a write, D8); the novel's row is the one that advances. Commit
        once. Raise NotFoundError for an absent or unowned novel.
        """
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        await lock_novel(self.session, user_id=self.user_id, novel_id=novel_id)
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        current = [chapter.id for chapter in await self.chapters.list_for_novel(novel_id)]
        # Set and length, one comparison each: the set catches an id the
        # book does not hold (a deleted chapter, a foreign one), the length
        # a body that repeats an id. Nothing is written before both agree.
        if set(chapter_ids) != set(current) or len(chapter_ids) != len(current):
            raise OrderMismatchError(current)
        await self.chapters.renumber(novel_id, chapter_ids)
        await self.chapters.touch_novel(novel_id)
        await self.session.commit()

    # --- Scenes: the prose unit under a chapter (W4 §5, D1/D2) ------------

    async def create_scene(self, chapter_id: UUID, payload: SceneCreate) -> SceneRead:
        """Commit a scene under an owned chapter; return it with its word count.

        The title is trimmed and the labels folded — spaces are not a name,
        and a blank overline or in-story label is the honest unset (None).
        The scene appends at the chapter's next position under the book's
        row lock. A scene born with prose feeds the atelier's activity
        immediately (the chapter, born an empty shell, did not): the words
        it carries are today's diff, counted by the shelf's one rule. Raise
        SetupRequiredError if setup has not created the owning user, or
        NotFoundError for an absent or unowned chapter.
        """
        await self._require_user()
        chapter = await self.get_chapter(chapter_id)
        scene = await self.scenes.create(
            chapter.id,
            chapter.novel_id,
            payload.title.strip(),
            payload.body,
            (payload.setting or "").strip() or None,
            (payload.story_time or "").strip() or None,
        )
        (words,) = await self.scenes.count_words(scene.body)
        if words:
            await self.daily_words.add_words(chapter.novel_id, datetime.now(UTC).date(), words)
        await self.session.commit()
        return self._scene_with_words(scene, words)

    async def list_scenes(self, chapter_id: UUID) -> Sequence[SceneRead]:
        chapter = await self.get_chapter(chapter_id)
        scenes = await self.scenes.list_for_chapter(chapter.id)
        words = await self.scenes.count_words(*(scene.body for scene in scenes))
        return [
            self._scene_with_words(scene, count) for scene, count in zip(scenes, words, strict=True)
        ]

    async def get_scene(self, scene_id: UUID) -> Scene:
        """The scene row, scoped — the internal getter the write paths build
        on. The router's read door is ``read_scene``, which carries the
        derived word count the raw row has no column for."""
        scene = await self.scenes.get(scene_id)
        if scene is None:
            raise NotFoundError
        return scene

    async def read_scene(self, scene_id: UUID) -> SceneRead:
        scene = await self.get_scene(scene_id)
        (words,) = await self.scenes.count_words(scene.body)
        return self._scene_with_words(scene, words)

    def _scene_with_words(self, scene: Scene, word_count: int) -> SceneRead:
        """One scene row as the response shape, its derived word count filled."""
        return SceneRead.model_validate(scene).model_copy(update={"word_count": word_count})

    @staticmethod
    def _scene_updates(changes: SceneUpdate) -> dict[str, str | None]:
        """The carried fields as a change set: title and body keep the
        chapter's rule (None unchanged, "" the honest empty after the trim);
        the labels are present-and-nullable (a carried null clears them)."""
        updates: dict[str, str | None] = {}
        carried = changes.model_fields_set
        if "title" in carried and changes.title is not None:
            updates["title"] = changes.title.strip()
        if "body" in carried and changes.body is not None:
            updates["body"] = changes.body
        if "setting" in carried:
            updates["setting"] = (changes.setting or "").strip() or None
        if "story_time" in carried:
            updates["story_time"] = (changes.story_time or "").strip() or None
        return updates

    async def update_scene(self, scene_id: UUID, changes: SceneUpdate) -> SceneRead:
        """Commit the carried scene edits and update the parent novel's timestamp.

        Present-only: title and body keep the chapter's rule (None unchanged,
        ``""`` the honest empty after the trim); the two labels are
        present-and-nullable (a carried null clears them back to unset). The
        book's row is locked before the scene's — the one order that keeps a
        save and a delete from deadlocking over one book (Postgres 40P01).

        A carried body feeds the atelier's activity: the diff of the one
        whitespace rule, the old body re-read under the novel lock,
        accumulates on today's row in the same transaction. A title- or
        label-only edit is a zero diff and writes no activity row.

        Return the scene with its word count; raise NotFoundError if it is
        absent or another user's.
        """
        scene = await self.get_scene(scene_id)
        chapter = await self.get_chapter(scene.chapter_id)
        novel_id = chapter.novel_id
        await lock_novel(self.session, user_id=self.user_id, novel_id=novel_id)
        # The OLD body is re-read under the lock: the get above may have
        # loaded it before a concurrent save committed (a double-fired
        # autosave), and a diff counted from that stale snapshot would
        # land on the day's row twice. The second writer waits, then reads
        # the first writer's committed scene (positions.py).
        old_body = await self.scenes.committed_body(scene_id)
        updates = self._scene_updates(changes)
        # The activity's diff: both sides count through the shelf's one
        # whitespace rule. A title- or label-only edit — or a body that
        # counts the same — is a zero diff and writes no activity row.
        new_body = updates.get("body")
        delta = 0
        if new_body is not None:
            old_words, new_words = await self.scenes.count_words(old_body or "", new_body)
            delta = new_words - old_words
        scene = await self.scenes.save(scene, updates, novel_id)
        if delta:
            await self.daily_words.add_words(novel_id, datetime.now(UTC).date(), delta)
        await self.session.commit()
        (words,) = await self.scenes.count_words(scene.body)
        return self._scene_with_words(scene, words)

    async def delete_scene(self, scene_id: UUID) -> None:
        """Delete one scene and close the gap it leaves in the numbering.

        Always allowed (D16): an empty chapter is a real state, so the last
        scene may go and the chapter reads honestly at zero. The delete, the
        survivors' renumber and the novel's timestamp bump are one
        transaction under the book's row lock, the one every append takes.
        The renumber moves a position, never a "last written" — ``renumber``
        pins each survivor's ``updated_at`` to itself, and the novel's row
        advances (D8). The removed words count negative on today's activity
        row, re-read under the lock so a concurrent save cannot stale the
        subtraction. Raise NotFoundError for an absent or unowned scene.
        """
        scene = await self.get_scene(scene_id)
        chapter = await self.get_chapter(scene.chapter_id)
        chapter_id, novel_id = chapter.id, chapter.novel_id
        await lock_novel(self.session, user_id=self.user_id, novel_id=novel_id)
        removed_body = await self.scenes.committed_body(scene_id)
        (removed_words,) = await self.scenes.count_words(removed_body or "")
        result = await self.session.execute(
            delete(Scene).where(Scene.id == scene_id, Scene.user_id == self.user_id)
        )
        if getattr(result, "rowcount", 0) == 0:
            raise NotFoundError
        survivors = await self.scenes.list_for_chapter(chapter_id)
        await self.scenes.renumber(chapter_id, [survivor.id for survivor in survivors])
        await self.scenes.touch_novel(novel_id)
        if removed_words:
            await self.daily_words.add_words(novel_id, datetime.now(UTC).date(), -removed_words)
        await self.session.commit()

    async def reorder_scenes(self, chapter_id: UUID, ids: Sequence[UUID]) -> None:
        """Rewrite the chapter's scene order as the one whole the body carries.

        The chapter-order contract one level down: the body must be exactly
        the chapter's current ids — the same set, the same length. Both the
        comparison and the rewrite sit under the book's row lock, the one
        every append takes: a scene added or deleted beside the reorder
        either commits before the read (and the body, now short or long, is
        refused) or waits and takes its number after the rewrite. A body
        that repeats an id is refused the same way. On a mismatch nothing is
        written and ``OrderMismatchError`` carries the stored ids in their
        position order, what the client reverts to. The rewrite is
        ``renumber`` (each row's ``updated_at`` pinned to itself: an
        arrangement is not a write, D8); the novel's row advances. Commit
        once. Raise NotFoundError for an absent or unowned chapter.
        """
        chapter = await self.get_chapter(chapter_id)
        novel_id = chapter.novel_id
        await lock_novel(self.session, user_id=self.user_id, novel_id=novel_id)
        current = [scene.id for scene in await self.scenes.list_for_chapter(chapter_id)]
        # Set and length, one comparison each: the set catches an id the
        # chapter does not hold (a deleted scene, a foreign one), the length
        # a body that repeats an id. Nothing is written before both agree.
        if set(ids) != set(current) or len(ids) != len(current):
            raise OrderMismatchError(current)
        await self.scenes.renumber(chapter_id, ids)
        await self.scenes.touch_novel(novel_id)
        await self.session.commit()

    async def export_novel(
        self, novel_id: UUID, mode: Literal["path", "zip"], path: str | None
    ) -> ExportDone | tuple[str, bytes]:
        """Export one owned novel as a ZIP, or into a directory on disk.

        `zip` returns the title's slug and the deterministic ZIP bytes; `path`
        writes the archive to the target — refusing an existing non-empty
        target, the engine's answer to a thinner re-export — and returns the
        receipt. The kernel engine reads the rows and raises
        `NovelNotFoundError` for a missing or foreign novel, which becomes
        NotFoundError here; the transport's own failures are the caller's
        named fields. Both deliveries leave the export's trace:
        `last_exported_at` is written and committed only after the engine
        has read the rows and, in path mode, the directory write has
        succeeded — the ZIP commits the stamp before the bytes are
        returned — so a refused or failed export sets nothing.
        """
        try:
            slug, files = await interchange_engine.export_novel(
                self.session, self.user_id, novel_id
            )
        except interchange_engine.NovelNotFoundError:
            raise NotFoundError from None
        if mode == "zip":
            payload = zip_bytes(files)
            await self.novels.touch_exported(novel_id)
            await self.session.commit()
            return slug, payload
        if path is None or not path.strip():
            raise FieldRefusedError(("path",), "exporting to a path needs a target path")
        # A file is not a target: say so, rather than call it a non-empty
        # directory the caller could believe a retry's debris.
        if Path(path).is_file():
            raise FieldRefusedError(("path",), f"{path}: is a file")
        # Remember whether the target pre-existed, so a failed stamp/commit
        # cleans up only a directory this export created — never a
        # pre-existing or concurrently modified target (#678, Sourcery).
        target = Path(path)
        pre_existed = target.exists()
        try:
            write_directory(target, files)
        except ArchiveError:
            # write_directory's one refusal: the target exists and is non-empty.
            raise TargetNotEmptyError(path) from None
        except (OSError, ValueError) as error:
            # OSError is the filesystem's answer (an unreachable mount, a denied
            # permission); ValueError is `path` naming nothing (an empty file
            # name). Both are the request's fault and come back named.
            reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
            raise FieldRefusedError(("path",), f"{path}: {reason}") from None
        # Stamp and commit after the directory landed. If the commit fails,
        # roll back and remove only a directory this export created, running
        # cleanup even on cancellation or rollback failure.
        try:
            await self.novels.touch_exported(novel_id)
            await self.session.commit()
        except BaseException:
            with contextlib.suppress(BaseException):
                await self.session.rollback()
            if not pre_existed:
                import shutil as _shutil

                _shutil.rmtree(target, ignore_errors=True)
            raise
        tree = ArchiveTree(files)
        return ExportDone(
            # The directory actually written: a relative target is resolved so
            # the receipt names what the user can go and open.
            path=str(Path(path).resolve()),
            chapters=len(tree.chapter_names()),
            entities=len(tree.kb_names()),
        )

    async def import_novel(
        self, *, archive: bytes | None, path: str | None, novel_id: UUID | None
    ) -> interchange_engine.ImportReport:
        """Import one archive — upload bytes or a server-side directory — as a
        new novel when `novel_id` is None, merged into the owned novel otherwise.

        Exactly one source is required, named by field when the request breaks
        that; an oversized upload refuses before it is parsed; a malformed one
        refuses with the offending file named. A new-novel import writes rows
        a user must own, so without the setup-created user it refuses as
        `create_novel` does — before the engine's first insert turns the
        missing owner into a foreign-key error. The engine commits once at
        the end, so a refused or failing import writes nothing. A missing or
        foreign target novel is NotFoundError; the corpus-width guard
        (EmbeddingMismatchError) surfaces unchanged, the knowledge router's
        mapping applies to it.
        """
        if novel_id is None:
            await self._require_user()
        tree: ArchiveTree
        if path is not None and archive is not None:
            raise FieldRefusedError(("archive", "path"), "give archive or path, not both")
        if path is not None:
            source = Path(path)
            if not source.is_dir():
                raise FieldRefusedError(("path",), f"{path}: is not a directory")
            try:
                tree = open_directory(source)
            except OSError as error:
                raise FieldRefusedError(("path",), f"{path}: {error.strerror or error}") from None
            except ArchiveError as error:
                # The directory's files expand past the cap: refused by name,
                # before the read, like the ZIP transport's own refusal.
                raise ArchiveInvalidError(error.path, error.reason) from None
        elif archive is not None:
            if len(archive) > MAX_ARCHIVE_BYTES:
                raise ArchiveTooLargeError
            try:
                tree = open_zip(archive)
            except (BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError) as error:
                # BadZipFile is the malformed container; RuntimeError is an
                # encrypted entry (password required), NotImplementedError an
                # unsupported compression method; zlib.error is a damaged or
                # truncated deflate stream and EOFError one that ends before
                # its marker. All are the archive's fault, never the server's.
                raise ArchiveInvalidError(_ARCHIVE, str(error)) from None
            except ArchiveError as error:
                # The entry claiming more than the uncompressed cap: named.
                raise ArchiveInvalidError(error.path, error.reason) from None
        else:
            raise FieldRefusedError(
                ("archive", "path"), "exactly one of archive or path is required"
            )
        try:
            return await interchange_engine.import_archive(
                self.session, self.user_id, tree, novel_id
            )
        except interchange_engine.NovelNotFoundError:
            raise NotFoundError from None
        except ArchiveError as error:
            raise ArchiveInvalidError(error.path, error.reason) from None
