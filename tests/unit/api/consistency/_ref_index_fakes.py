"""Shared fakes and factories for CrossFeatureRefIndex tests.

Extracted from ``test_cross_feature_ref_index.py`` to comply with RULE-04
(file-size limit). Provides seedable in-memory fakes for the four
repositories consumed by :class:`CrossFeatureRefIndexImpl`, plus factory
helpers for the related ORM models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare.chapters.models import Chapter
from narrare.consistency.ref_index import CrossFeatureRefIndexImpl
from narrare.kb.models import KBEntry
from narrare.planning.models import ChapterOutline, ScenePlan, TimelineEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeKBRepo:
    def __init__(self) -> None:
        self.entries: dict[UUID, KBEntry] = {}

    def seed(self, entry: KBEntry) -> None:
        self.entries[entry.id] = entry

    async def get_by_id(self, entry_id: UUID) -> KBEntry | None:
        return self.entries.get(entry_id)

    async def get_by_name(self, novel_id: UUID, name: str) -> KBEntry | None:
        del novel_id
        for entry in self.entries.values():
            if entry.name.lower() == name.lower():
                return entry
        return None


class FakeTimelineRepo:
    def __init__(self) -> None:
        self.events: list[TimelineEvent] = []

    def seed(self, event: TimelineEvent) -> None:
        self.events.append(event)

    async def list_by_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]:
        del novel_id
        return list(self.events)


class FakeOutlineRepo:
    def __init__(self) -> None:
        self.outlines: list[ChapterOutline] = []

    def seed(self, outline: ChapterOutline) -> None:
        self.outlines.append(outline)

    async def get_all_for_novel(self, novel_id: UUID) -> Sequence[ChapterOutline]:
        del novel_id
        return list(self.outlines)


class FakeSceneRepo:
    def __init__(self) -> None:
        self.scenes: list[ScenePlan] = []

    def seed(self, scene: ScenePlan) -> None:
        self.scenes.append(scene)

    async def list_by_novel(self, novel_id: UUID) -> Sequence[ScenePlan]:
        del novel_id
        return list(self.scenes)


class FakeChapterRepo:
    def __init__(self) -> None:
        self.chapters: list[Chapter] = []

    def seed(self, chapter: Chapter) -> None:
        self.chapters.append(chapter)

    async def list_by_novel(
        self,
        novel_id: UUID,
        volume_id: UUID | None = None,
    ) -> Sequence[Chapter]:
        del novel_id, volume_id
        return list(self.chapters)


def make_entry(*, name: str, status: str = "canon") -> KBEntry:
    return KBEntry(
        id=uuid4(),
        novel_id=uuid4(),
        entity_type="character",
        name=name,
        slug=name.lower(),
        status=status,
    )


def make_timeline_event(
    *,
    character_refs: list[dict[str, object]] | None = None,
    location_ref: dict[str, object] | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        id=uuid4(),
        novel_id=uuid4(),
        event_name="Event",
        character_refs=list(character_refs or []),
        location_ref=location_ref,
    )


def make_chapter(*, content: str, pov_character_id: str = "") -> Chapter:
    return Chapter(
        id=uuid4(),
        novel_id=uuid4(),
        content=content,
        pov_character_id=pov_character_id,
    )


def make_outline(
    *,
    planned_beats: list[dict[str, object]] | None = None,
    outline_notes: str = "",
) -> ChapterOutline:
    return ChapterOutline(
        id=uuid4(),
        chapter_id=uuid4(),
        planned_beats=list(planned_beats or []),
        outline_notes=outline_notes,
    )


def make_index(
    kb_repo: FakeKBRepo,
    timeline_repo: FakeTimelineRepo | None = None,
    chapter_repo: FakeChapterRepo | None = None,
    outline_repo: FakeOutlineRepo | None = None,
    scene_repo: FakeSceneRepo | None = None,
) -> CrossFeatureRefIndexImpl:
    return CrossFeatureRefIndexImpl(
        kb_repo=kb_repo,
        timeline_repo=timeline_repo or FakeTimelineRepo(),
        outline_repo=outline_repo or FakeOutlineRepo(),
        chapter_repo=chapter_repo or FakeChapterRepo(),
        scene_repo=scene_repo or FakeSceneRepo(),
    )
