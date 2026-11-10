"""The storyboard: structure-aware chapter grouping with sync, plus the
scene-plan and timeline-event aggregates behind it."""

from datetime import UTC, datetime
from uuid import UUID  # noqa: TC003

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.planning.models import (
    SCENE_STATUSES,
    ChapterStage,
    ScenePlan,
    TimelineEvent,
)
from app.capabilities.planning.repository import (
    ScenePlanRepository,
    StoryboardRepository,
    TimelineEventRepository,
)
from app.capabilities.planning.schemas import (
    RemapEntry,
    RemapRead,
    SceneAggregateRead,
    SceneAggregateUpdate,
    SceneRead,
    SceneUpsert,
    StoryboardChapterRead,
    StoryboardRead,
    StoryboardStageRead,
    TimelineEventCreate,
    TimelineEventRead,
    TimelineEventUpdate,
)
from app.capabilities.planning.structures import (
    DEFAULT_STRUCTURE_ID,
    StageDef,
    UnknownStructureError,
    require_structure,
    suggest_stage,
)
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import Chapter, Novel, User


class NotFoundError(Exception):
    """The chapter is absent, foreign, or filed under another novel."""


class SceneRefusedError(ValueError):
    """A PUT the diff-sync law refuses: a doubled id, an id owned elsewhere,
    or a status outside the lifecycle."""


class TimelineRefusedError(ValueError):
    """An event write the timeline law refuses: a blank title, or a chapter
    link that is absent, foreign, or filed under another novel."""


class StoryboardRefusedError(ValueError):
    """A storyboard write the refetch-compare law refuses: a chapter id the
    novel does not hold, a stage key outside the current structure, or a
    structure id outside the registry — each names its reason, and a refused
    write leaves the aggregate exactly as the refetch found it."""


class PlanningService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.scenes = ScenePlanRepository(session, user_id)
        self.events = TimelineEventRepository(session, user_id)
        self.storyboard = StoryboardRepository(session, user_id)

    async def _require_user(self) -> None:
        """Writes belong to a user that setup created; without one there is
        nothing to own the row, and the foreign key would say so at the worst
        possible time. The guard says it in the response instead."""
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError

    async def _require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter:
        """The chapter when it is ours and the novel's; NotFoundError for an
        absent or unowned chapter, a foreign novel, or a chapter filed under
        another novel — all three read as missing, never as an oracle."""
        chapter = await self.scenes.require_chapter(novel_id, chapter_id)
        if chapter is None:
            raise NotFoundError
        return chapter

    def _read(self, chapter: Chapter, scenes: list[ScenePlan]) -> SceneAggregateRead:
        """The aggregate shape: the chapter's scenes in position order, with
        the chapter's own stamp as the version the dock compares against."""
        return SceneAggregateRead(
            chapter_id=chapter.id,
            scenes=[SceneRead.model_validate(scene) for scene in scenes],
            version_updated_at=chapter.updated_at,
        )

    async def get_aggregate(self, novel_id: UUID, chapter_id: UUID) -> SceneAggregateRead:
        """Read the chapter's scenes in position order. No auto-create: a
        chapter without plans answers with an empty list. Raise NotFoundError
        for an absent or unowned chapter."""
        chapter = await self._require_chapter(novel_id, chapter_id)
        return self._read(chapter, list(await self.scenes.list_for_chapter(chapter.id)))

    async def save_aggregate(
        self, novel_id: UUID, chapter_id: UUID, payload: SceneAggregateUpdate
    ) -> SceneAggregateRead:
        """Diff the whole aggregate by stable scene id and commit once.

        A known id updates; an id no row owns is an addition — the client
        mints the UUID and the PUT inserts it, with no claim step first. An
        id one of the user's other chapters owns is a 422, and a doubled id
        in one payload is a 422 before any write, so a refused PUT leaves
        the aggregate exactly as the refetch found it. An absent id deletes,
        and positions renumber 1..N by payload order. The PUT
        replaces the chapter's whole scene list, so two concurrent saves
        resolve last-writer-wins on positions and fields; there is no
        field-level merge and no optimistic-concurrency version check in
        this slice. Raise
        NotFoundError for an absent or unowned chapter.
        """
        await self._require_user()
        chapter = await self._require_chapter(novel_id, chapter_id)
        current = {scene.id: scene for scene in await self.scenes.list_for_chapter(chapter.id)}
        held = await self._refuse_before_write(payload.scenes, set(current))
        created = [upsert.id for upsert in payload.scenes if upsert.id not in current]
        try:
            for position, upsert in enumerate(payload.scenes, start=1):
                if upsert.id in current:
                    await self.scenes.save(current[upsert.id], self._changes(upsert, position))
                else:
                    await self.scenes.create(chapter.id, self._changes(upsert, position))
            for stale_id in set(current) - held:
                await self.scenes.delete(current[stale_id])
            # The chapter carries the version: an aggregate write counts as
            # touching the chapter, so the stamp the dock compares moves with
            # every PUT — a scenes-only write would leave it honestly stale.
            chapter.updated_at = datetime.now(UTC)
            await self.session.commit()
        except IntegrityError:
            # A client id that reached the INSERT but belongs to another
            # user's plans: the primary key says so, and the answer is the
            # same 422 the elsewhere check gives for this user's own rows —
            # naming the created ids the way that check names its id.
            await self.session.rollback()
            detail = (
                "unknown scene id"
                if not created
                else (
                    f"unknown scene id: {', '.join(sorted(str(scene_id) for scene_id in created))}"
                )
            )
            raise SceneRefusedError(detail) from None
        return self._read(chapter, list(await self.scenes.list_for_chapter(chapter.id)))

    async def _refuse_before_write(self, upserts: list[SceneUpsert], known: set[UUID]) -> set[UUID]:
        """The diff-sync law's refusals, all before any write.

        A doubled id, a status outside the lifecycle, or an id the user owns
        in another chapter — each names its reason, and a refused PUT writes
        nothing at all. Returns the payload's ids for the delete pass.
        """
        seen: set[UUID] = set()
        for upsert in upserts:
            if upsert.id in seen:
                raise SceneRefusedError(f"duplicate scene id: {upsert.id}")
            seen.add(upsert.id)
            if upsert.status not in SCENE_STATUSES:
                raise SceneRefusedError(f"unknown status: {upsert.status}")
        owned_elsewhere = await self.scenes.existing_ids(seen - known)
        for scene_id in sorted(seen & owned_elsewhere, key=str):
            raise SceneRefusedError(f"unknown scene id: {scene_id}")
        return seen

    @staticmethod
    def _changes(upsert: SceneUpsert, position: int) -> dict[str, object]:
        """The payload's writable fields: positions renumber 1..N by payload
        order, and the timestamps stay the server's — the schema carries no
        field for them, so a forged value never arrives here."""
        return {
            "id": upsert.id,
            "title": upsert.title,
            "purpose": upsert.purpose,
            "conflict": upsert.conflict,
            "resolution": upsert.resolution,
            "beats": list(upsert.beats),
            "status": upsert.status,
            "position": position,
        }

    async def _require_novel(self, novel_id: UUID) -> Novel:
        """The novel when it is ours; NotFoundError for an absent or unowned
        novel — a foreign novel reads as missing, never as an oracle."""
        novel = await self.events.require_novel(novel_id)
        if novel is None:
            raise NotFoundError
        return novel

    async def _require_event(self, novel_id: UUID, event_id: UUID) -> TimelineEvent:
        """The event when it is ours and the novel's; NotFoundError for an
        absent id, a foreign novel, or an event filed under another novel."""
        await self._require_novel(novel_id)
        event = await self.events.get_for_novel(novel_id, event_id)
        if event is None:
            raise NotFoundError
        return event

    async def _chapter_or_refuse(self, novel_id: UUID, chapter_id: UUID | None) -> None:
        """Rule out a chapter link the novel does not hold before any write."""
        if chapter_id is None:
            return
        if await self.events.require_chapter(novel_id, chapter_id) is None:
            raise TimelineRefusedError(f"unknown chapter id: {chapter_id}")

    @staticmethod
    def _titled_or_refuse(title: str | None) -> str:
        """The stored title: trimmed, and never blank — spaces are not a name,
        the chapters' rule. The schema's min_length refuses the empty string;
        this refuses the whitespace-only one."""
        if title is None:
            raise TimelineRefusedError("title must not be blank")
        trimmed = title.strip()
        if not trimmed:
            raise TimelineRefusedError("title must not be blank")
        return trimmed

    async def create_timeline_event(
        self, novel_id: UUID, payload: TimelineEventCreate
    ) -> TimelineEventRead:
        """Commit one event on the novel's timeline and return it.

        Raise NotFoundError for an absent or unowned novel,
        SetupRequiredError without the setup-created user, or
        TimelineRefusedError for a blank title or a chapter link the novel
        does not hold.
        """
        await self._require_user()
        await self._require_novel(novel_id)
        await self._chapter_or_refuse(novel_id, payload.chapter_id)
        event = await self.events.create(
            novel_id,
            {
                "title": self._titled_or_refuse(payload.title),
                "description": payload.description,
                "chapter_id": payload.chapter_id,
                "position": payload.position,
                "date_label": payload.date_label.strip(),
                "character_names": list(payload.character_names),
            },
        )
        await self.session.commit()
        return TimelineEventRead.model_validate(event)

    async def list_timeline_events(self, novel_id: UUID) -> list[TimelineEventRead]:
        """The novel's events in manual order, unordered rows last.

        Raise NotFoundError for an absent or unowned novel. Reads need no
        owner: without one the novel is missing, not refused.
        """
        await self._require_novel(novel_id)
        return [
            TimelineEventRead.model_validate(event)
            for event in await self.events.list_for_novel(novel_id)
        ]

    async def get_timeline_event(self, novel_id: UUID, event_id: UUID) -> TimelineEventRead:
        """Return one owned event of the novel; raise NotFoundError when the
        event, the novel, or the ownership is missing."""
        return TimelineEventRead.model_validate(await self._require_event(novel_id, event_id))

    async def update_timeline_event(
        self, novel_id: UUID, event_id: UUID, payload: TimelineEventUpdate
    ) -> TimelineEventRead:
        """Commit the carried fields and return the event.

        Only the fields the body carries change; a carried ``null`` clears
        ``chapter_id`` or ``position`` — every other field is non-nullable,
        so a null there never reaches this method (the schema answers 422).
        Raise NotFoundError for an absent or unowned event or novel, or
        TimelineRefusedError for a blank title or a chapter link the novel
        does not hold.
        """
        await self._require_user()
        event = await self._require_event(novel_id, event_id)
        carried = payload.model_dump(exclude_unset=True)
        if "title" in carried:
            carried["title"] = self._titled_or_refuse(carried["title"])
        if "date_label" in carried:
            carried["date_label"] = carried["date_label"].strip()
        if "character_names" in carried:
            carried["character_names"] = list(carried["character_names"])
        await self._chapter_or_refuse(novel_id, carried.get("chapter_id"))
        event = await self.events.save(event, carried)
        await self.session.commit()
        return TimelineEventRead.model_validate(event)

    async def delete_timeline_event(self, novel_id: UUID, event_id: UUID) -> None:
        """Delete one owned event of the novel; raise NotFoundError for an
        absent or unowned event or novel."""
        await self._require_user()
        await self.events.delete(await self._require_event(novel_id, event_id))
        await self.session.commit()

    async def _require_storyboard_novel(self, novel_id: UUID) -> Novel:
        """The novel when it is ours; NotFoundError for an absent or unowned
        novel — a foreign novel reads as missing, never as an oracle."""
        novel = await self.storyboard.require_novel(novel_id)
        if novel is None:
            raise NotFoundError
        return novel

    async def _storyboard_structure(self, novel_id: UUID) -> tuple[str, tuple[StageDef, ...]]:
        """The novel's structure id and stages: the stored choice, or the
        default when the writer never remapped. A suggestion is computed,
        never persisted, so this read writes nothing."""
        settings = await self.storyboard.get_settings(novel_id)
        structure_id = settings.story_structure if settings is not None else DEFAULT_STRUCTURE_ID
        return structure_id, require_structure(structure_id)

    @staticmethod
    def _suggested_key(stages: tuple[StageDef, ...], position: int, last_position: int) -> str:
        """The position-ratio suggestion: the first stage whose range
        contains position over the chapter-count denominator — one for a
        single-chapter novel, whose denominator would otherwise be zero."""
        return suggest_stage(stages, position / max(1, last_position)).key

    @staticmethod
    def _effective_stage_key(
        stages: tuple[StageDef, ...],
        assigned: ChapterStage | None,
        suggested: str,
    ) -> str:
        """The stage the canvas shows: the stored assignment when it names
        a stage of the current structure, otherwise the suggestion — a
        stored key from another structure degrades instead of raising."""
        if assigned is not None and assigned.stage_key in {stage.key for stage in stages}:
            return assigned.stage_key
        return suggested

    @staticmethod
    def _sync_status(
        scenes: list[ScenePlan], words: int, assigned: str | None, suggested: str
    ) -> str:
        """The chapter's sync, first match wins: no scenes and no words is
        empty; scenes without words are planned; a hand-set stage off the
        suggestion is deviated; complete scenes plus words are completed;
        everything aligned but in progress is on track."""
        if not scenes and words == 0:
            return "empty"
        if scenes and words == 0:
            return "planned"
        if assigned is not None and assigned != suggested:
            return "deviated"
        if scenes and all(scene.status == "complete" for scene in scenes) and words > 0:
            return "completed"
        return "on_track"

    def _chapter_entry(
        self,
        chapter: Chapter,
        stage_key: str,
        source: str,
        words: int,
        scenes: list[ScenePlan],
        suggested: str,
        assigned: str | None,
    ) -> StoryboardChapterRead:
        """One chapter's storyboard row: the effective stage, where the stage
        came from, and the sync the rule above computes."""
        return StoryboardChapterRead(
            chapter_id=chapter.id,
            title=chapter.title,
            position=chapter.position,
            word_count=words,
            sync_status=self._sync_status(scenes, words, assigned, suggested),
            assignment_source=source,
            stage_key=stage_key,
        )

    async def _chapter_entries(
        self,
        chapters: list[Chapter],
        stages: tuple[StageDef, ...],
        assignments: dict[UUID, ChapterStage],
        words: dict[UUID, int],
        scenes: dict[UUID, list[ScenePlan]],
    ) -> list[StoryboardChapterRead]:
        """Every chapter's row under one structure: assigned stages win, the
        suggestion fills the rest — including a stored assignment naming a
        stage outside the current structure, which degrades to the
        suggestion instead of raising."""
        denominator = max(1, len(chapters) - 1)
        entries: list[StoryboardChapterRead] = []
        for chapter in chapters:
            suggested = self._suggested_key(stages, chapter.position, denominator)
            assigned = assignments.get(chapter.id)
            effective = self._effective_stage_key(stages, assigned, suggested)
            if assigned is not None and effective == assigned.stage_key:
                entries.append(
                    self._chapter_entry(
                        chapter,
                        assigned.stage_key,
                        "assigned",
                        words.get(chapter.id, 0),
                        scenes.get(chapter.id, []),
                        suggested,
                        assigned.stage_key,
                    )
                )
            else:
                entries.append(
                    self._chapter_entry(
                        chapter,
                        suggested,
                        "suggested",
                        words.get(chapter.id, 0),
                        scenes.get(chapter.id, []),
                        suggested,
                        None,
                    )
                )
        return entries

    async def get_storyboard(self, novel_id: UUID) -> StoryboardRead:
        """Assemble the novel's storyboard: the structure and its staged chapters.

        Reads only — assignments and the structure choice are stored rows,
        suggestions are computed. Raise NotFoundError for an absent or
        unowned novel.
        """
        await self._require_storyboard_novel(novel_id)
        structure_id, stages = await self._storyboard_structure(novel_id)
        chapters = list(await self.storyboard.list_chapters(novel_id))
        assignments = await self.storyboard.assignments_for_chapters(
            [chapter.id for chapter in chapters]
        )
        words = await self.storyboard.word_counts(novel_id)
        plans = await self.scenes.list_for_chapters([chapter.id for chapter in chapters])
        by_chapter: dict[UUID, list[ScenePlan]] = {}
        for plan in plans:
            by_chapter.setdefault(plan.chapter_id, []).append(plan)
        entries = await self._chapter_entries(chapters, stages, assignments, words, by_chapter)
        by_stage: dict[str, list[StoryboardChapterRead]] = {stage.key: [] for stage in stages}
        for entry in entries:
            by_stage[entry.stage_key].append(entry)
        return StoryboardRead(
            novel_id=novel_id,
            structure_id=structure_id,
            stages=[
                StoryboardStageRead(
                    key=stage.key,
                    title_key=stage.title_key,
                    **{"from": stage.from_ratio, "to": stage.to_ratio},
                    chapters=by_stage[stage.key],
                )
                for stage in stages
            ],
        )

    async def set_chapter_stage(
        self, novel_id: UUID, chapter_id: UUID, stage_key: str
    ) -> StoryboardChapterRead:
        """Move one chapter to a stage of the novel's current structure.

        Raise NotFoundError for an absent or unowned novel, or
        StoryboardRefusedError for a chapter id the novel does not hold or
        a stage key outside the current structure — a refused PUT writes
        nothing at all.
        """
        await self._require_user()
        await self._require_storyboard_novel(novel_id)
        chapters = list(await self.storyboard.list_chapters(novel_id))
        chapter = next((row for row in chapters if row.id == chapter_id), None)
        if chapter is None:
            raise StoryboardRefusedError(f"unknown chapter id: {chapter_id}")
        _, stages = await self._storyboard_structure(novel_id)
        if stage_key not in {stage.key for stage in stages}:
            raise StoryboardRefusedError(f"unknown stage: {stage_key}")
        await self.storyboard.save_assignment(chapter_id, stage_key)
        await self.session.commit()
        denominator = max(1, len(chapters) - 1)
        suggested = self._suggested_key(stages, chapter.position, denominator)
        words = await self.storyboard.word_counts(novel_id)
        plans = list(await self.scenes.list_for_chapter(chapter.id))
        return self._chapter_entry(
            chapter,
            stage_key,
            "assigned",
            words.get(chapter.id, 0),
            plans,
            suggested,
            stage_key,
        )

    async def remap_storyboard(self, novel_id: UUID, structure_id: str, confirm: bool) -> RemapRead:
        """Preview or apply the structure change.

        The mapping carries every chapter from its current effective stage
        to the target structure's suggestion. A preview writes nothing; a
        confirm writes the assignments plus the novel setting in one
        transaction — exactly the previewed mapping. Raise NotFoundError
        for an absent or unowned novel, SetupRequiredError for a confirm
        without the setup-created user, or StoryboardRefusedError for a
        structure id outside the registry.
        """
        try:
            target = require_structure(structure_id)
        except UnknownStructureError as error:
            raise StoryboardRefusedError(str(error)) from None
        if confirm:
            await self._require_user()
        await self._require_storyboard_novel(novel_id)
        _, current = await self._storyboard_structure(novel_id)
        chapters = list(await self.storyboard.list_chapters(novel_id))
        assignments = await self.storyboard.assignments_for_chapters(
            [chapter.id for chapter in chapters]
        )
        denominator = max(1, len(chapters) - 1)
        mapping = [
            RemapEntry(
                chapter_id=chapter.id,
                from_stage=self._effective_stage_key(
                    current,
                    assignments.get(chapter.id),
                    self._suggested_key(current, chapter.position, denominator),
                ),
                to_stage=self._suggested_key(target, chapter.position, denominator),
            )
            for chapter in chapters
        ]
        if confirm:
            await self.storyboard.save_settings(novel_id, structure_id)
            for entry in mapping:
                await self.storyboard.save_assignment(entry.chapter_id, entry.to_stage)
            await self.session.commit()
        return RemapRead(
            novel_id=novel_id,
            structure_id=structure_id,
            confirmed=confirm,
            mapping=mapping,
        )
