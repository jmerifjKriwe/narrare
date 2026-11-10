"""Scene-plan, timeline-event and storyboard persistence. All scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import case, func, select

from app.capabilities.planning.models import (
    ChapterStage,
    PlanningNovelSettings,
    ScenePlan,
    TimelineEvent,
)
from app.kernel.contracts.models import Chapter, Novel
from app.kernel.db.base import ScopedRepository

# The shelf's word counting, mirrored for per-chapter reads: a word is a
# whitespace-separated token of the trimmed body, an empty trim worth zero.
# The canonical definition lives in app/capabilities/writing/repository.py
# (NovelRepository.counts) — a capability never imports another (rule 1), so
# this repeats the identical whitespace class and expression, and the two
# move together. The whitespace is PostgreSQL's ``[[:space:]]`` plus the
# three near spaces the browser counts: NBSP, figure space, narrow no-break
# space.
_WS = "[" + r"\s" + chr(0x00A0) + chr(0x2007) + chr(0x202F) + "]"
_TRIM_PATTERN = f"^{_WS}+|{_WS}+$"
_SPLIT_PATTERN = _WS + "+"


def _word_count_expression() -> Any:
    """The per-row word count the shelf's grouped query sums: tokens of the
    trimmed body, zero when the trim is empty."""
    trimmed = func.regexp_replace(Chapter.body, _TRIM_PATTERN, "", "g")
    return case(
        (
            trimmed != "",
            func.coalesce(
                func.array_length(func.regexp_split_to_array(trimmed, _SPLIT_PATTERN), 1),
                0,
            ),
        ),
        else_=0,
    )


class ScenePlanRepository(ScopedRepository[ScenePlan]):
    model = ScenePlan

    async def list_for_chapter(self, chapter_id: UUID) -> Sequence[ScenePlan]:
        """The chapter's scenes in position order, scoped to the user."""
        result = await self.session.scalars(
            self.query().where(ScenePlan.chapter_id == chapter_id).order_by(ScenePlan.position)
        )
        return result.all()

    async def list_for_chapters(self, chapter_ids: Sequence[UUID]) -> Sequence[ScenePlan]:
        """Every scene of the given chapters, scoped to the user.

        The storyboard's sync pass reads the whole novel in one query,
        never one per chapter; the service groups by chapter.
        """
        if not chapter_ids:
            return []
        result = await self.session.scalars(
            self.query()
            .where(ScenePlan.chapter_id.in_(chapter_ids))
            .order_by(ScenePlan.chapter_id, ScenePlan.position)
        )
        return result.all()

    async def existing_ids(self, scene_ids: set[UUID]) -> set[UUID]:
        """The ids the user already owns, in any chapter.

        The validator's elsewhere check: an id owned elsewhere in this
        user's plans is unknown to the chapter, not a creation.
        """
        if not scene_ids:
            return set()
        result = await self.session.scalars(self.query().where(ScenePlan.id.in_(scene_ids)))
        return {scene.id for scene in result.all()}

    async def require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter | None:
        """The chapter when it is ours and the novel's.

        None when absent, foreign, or filed under another novel — the
        caller's 404 either way, so a foreign novel reads as missing.
        """
        return await self.session.scalar(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
                Chapter.user_id == self.user_id,
            )
        )

    async def create(
        self,
        chapter_id: UUID,
        changes: dict[str, Any],
    ) -> ScenePlan:
        """Flush a new scene for this user with the client's id, leaving the
        commit to the caller. The id and position arrive from the payload:
        new scenes are client-addressed, and the service has already ruled
        out the ids this user owns elsewhere."""
        scene = ScenePlan(
            user_id=self.user_id,
            chapter_id=chapter_id,
            **changes,
        )
        self.session.add(scene)
        await self.session.flush()
        return scene

    async def save(self, scene: ScenePlan, changes: dict[str, Any]) -> ScenePlan:
        """Apply an aggregate edit and flush; the commit is the caller's."""
        for field, value in changes.items():
            setattr(scene, field, value)
        await self.session.flush()
        return scene

    async def delete(self, scene: ScenePlan) -> None:
        """Mark the supplied scene for deletion; the caller commits the change."""
        await self.session.delete(scene)


class StoryboardRepository(ScopedRepository[ChapterStage]):
    """Storyboard reads and writes. The model is the stage assignment; the
    novel, its chapters and the word counts are read through the kernel's
    own contracts — writing tables are read, never written, here."""

    model = ChapterStage

    async def require_novel(self, novel_id: UUID) -> Novel | None:
        """The novel when it is ours; None when absent or foreign — the
        caller's 404 either way, so a foreign novel reads as missing."""
        return await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )

    async def list_chapters(self, novel_id: UUID) -> Sequence[Chapter]:
        """The novel's chapters in position order, scoped to the user."""
        result = await self.session.scalars(
            select(Chapter)
            .where(Chapter.novel_id == novel_id, Chapter.user_id == self.user_id)
            .order_by(Chapter.position)
        )
        return result.all()

    async def word_counts(self, novel_id: UUID) -> dict[UUID, int]:
        """Per-chapter word counts for one novel, one grouped query.

        The same tokens the shelf sums per novel, here per chapter: bodies
        never leave the database, and a chapter with no row reports zero
        through the caller's default, not through this dict.
        """
        rows = await self.session.execute(
            select(Chapter.id, _word_count_expression()).where(
                Chapter.novel_id == novel_id, Chapter.user_id == self.user_id
            )
        )
        return {chapter_id: int(words) for chapter_id, words in rows}

    async def assignments_for_chapters(
        self, chapter_ids: Sequence[UUID]
    ) -> dict[UUID, ChapterStage]:
        """The writer-set assignments of the given chapters, keyed by chapter."""
        if not chapter_ids:
            return {}
        result = await self.session.scalars(
            self.query().where(ChapterStage.chapter_id.in_(chapter_ids))
        )
        return {assignment.chapter_id: assignment for assignment in result.all()}

    async def save_assignment(self, chapter_id: UUID, stage_key: str) -> ChapterStage:
        """Upsert the chapter's assignment; the commit is the caller's."""
        assignment = await self.session.scalar(
            self.query().where(ChapterStage.chapter_id == chapter_id)
        )
        if assignment is None:
            assignment = ChapterStage(user_id=self.user_id, chapter_id=chapter_id)
            self.session.add(assignment)
        assignment.stage_key = stage_key
        await self.session.flush()
        return assignment

    async def get_settings(self, novel_id: UUID) -> PlanningNovelSettings | None:
        """The novel's storyboard setting, if the writer ever remapped."""
        return await self.session.scalar(
            select(PlanningNovelSettings).where(
                PlanningNovelSettings.novel_id == novel_id,
                PlanningNovelSettings.user_id == self.user_id,
            )
        )

    async def save_settings(self, novel_id: UUID, structure_id: str) -> PlanningNovelSettings:
        """Upsert the novel's structure choice; the commit is the caller's."""
        settings = await self.get_settings(novel_id)
        if settings is None:
            settings = PlanningNovelSettings(user_id=self.user_id, novel_id=novel_id)
            self.session.add(settings)
        settings.story_structure = structure_id
        await self.session.flush()
        return settings


class TimelineEventRepository(ScopedRepository[TimelineEvent]):
    model = TimelineEvent

    async def list_for_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]:
        """The novel's events in manual order, scoped to the user.

        Unordered rows (null position) sort last, creation order breaks the
        position tie, and the id breaks what is left — the canvas order the
        writer arranged, dateless rows at the end, fully deterministic.
        """
        result = await self.session.scalars(
            self.query()
            .where(TimelineEvent.novel_id == novel_id)
            .order_by(
                TimelineEvent.position.asc().nulls_last(),
                TimelineEvent.created_at.asc(),
                TimelineEvent.id.asc(),
            )
        )
        return result.all()

    async def get_for_novel(self, novel_id: UUID, event_id: UUID) -> TimelineEvent | None:
        """The event when it is ours and the novel's; None otherwise."""
        return await self.session.scalar(
            self.query().where(TimelineEvent.id == event_id, TimelineEvent.novel_id == novel_id)
        )

    async def require_novel(self, novel_id: UUID) -> Novel | None:
        """The novel when it is ours; None when absent or foreign — the
        caller's 404 either way, so a foreign novel reads as missing."""
        return await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )

    async def require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter | None:
        """The chapter when it is ours and the novel's; None otherwise."""
        return await self.session.scalar(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
                Chapter.user_id == self.user_id,
            )
        )

    async def create(
        self,
        novel_id: UUID,
        changes: dict[str, Any],
    ) -> TimelineEvent:
        """Flush a new event for this user and novel, leaving the commit to
        the caller."""
        event = TimelineEvent(
            user_id=self.user_id,
            novel_id=novel_id,
            **changes,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def save(self, event: TimelineEvent, changes: dict[str, Any]) -> TimelineEvent:
        """Apply an edit and flush; the commit is the caller's."""
        for field, value in changes.items():
            setattr(event, field, value)
        await self.session.flush()
        return event

    async def delete(self, event: TimelineEvent) -> None:
        """Mark the supplied event for deletion; the caller commits the change."""
        await self.session.delete(event)
