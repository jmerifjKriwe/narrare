"""Regression tests for the ADR-050 read-side CrossFeatureRefIndex."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Sequence

from narrare.chapters.models import Chapter
from narrare.consistency.ref_index import CrossFeatureRefIndexImpl
from narrare.kb.models import KBEntry
from narrare.planning.models import ChapterOutline, TimelineEvent
from narrare_core.context.integration_contracts import CrossFeatureRefIndex


class _FakeKBRepo:
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


class _FakeTimelineRepo:
    def __init__(self) -> None:
        self.events: list[TimelineEvent] = []

    def seed(self, event: TimelineEvent) -> None:
        self.events.append(event)

    async def list_by_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]:
        del novel_id
        return list(self.events)


class _FakeOutlineRepo:
    async def get_all_for_novel(self, novel_id: UUID) -> Sequence[ChapterOutline]:
        del novel_id
        return []


class _FakeChapterRepo:
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


def _entry(*, name: str, status: str = "canon") -> KBEntry:
    return KBEntry(
        id=uuid4(),
        novel_id=uuid4(),
        entity_type="character",
        name=name,
        slug=name.lower(),
        status=status,
    )


def _timeline_event(
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


def _chapter(*, content: str, pov_character_id: str = "") -> Chapter:
    return Chapter(
        id=uuid4(),
        novel_id=uuid4(),
        content=content,
        pov_character_id=pov_character_id,
    )


def _index(
    kb_repo: _FakeKBRepo,
    timeline_repo: _FakeTimelineRepo | None = None,
    chapter_repo: _FakeChapterRepo | None = None,
) -> CrossFeatureRefIndexImpl:
    return CrossFeatureRefIndexImpl(
        kb_repo=kb_repo,
        timeline_repo=timeline_repo or _FakeTimelineRepo(),
        outline_repo=_FakeOutlineRepo(),
        chapter_repo=chapter_repo or _FakeChapterRepo(),
    )


class TestProtocol:
    def test_satisfies_core_protocol(self) -> None:
        assert isinstance(_index(_FakeKBRepo()), CrossFeatureRefIndex)


class TestResolveRef:
    async def test_resolve_id_reports_active_deprecated_and_unknown(self) -> None:
        kb = _FakeKBRepo()
        active = _entry(name="John")
        deprecated = _entry(name="Old Castle", status="deprecated")
        kb.seed(active)
        kb.seed(deprecated)
        index = _index(kb)

        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value=str(active.id))
            == "active"
        )
        assert (
            await index.resolve_ref(
                novel_id=uuid4(),
                ref_kind="id",
                ref_value=str(deprecated.id),
            )
            == "deprecated"
        )
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value=str(uuid4()))
            == "unknown"
        )


class TestTimelineRefs:
    async def test_check_refs_finds_stale_timeline_name_after_missed_rename_event(self) -> None:
        kb = _FakeKBRepo()
        entry = _entry(name="Jonathan")
        kb.seed(entry)
        timeline = _FakeTimelineRepo()
        timeline.seed(_timeline_event(character_refs=[{"id": str(entry.id), "name": "John"}]))
        index = _index(kb, timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].reason == "stale_name_ref"
        assert issues[0].resolved_status == "active"

    async def test_check_refs_finds_deleted_timeline_id_after_hard_delete(self) -> None:
        timeline = _FakeTimelineRepo()
        missing_id = uuid4()
        timeline.seed(_timeline_event(character_refs=[{"id": str(missing_id), "name": "John"}]))
        index = _index(_FakeKBRepo(), timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].reason == "deleted_ref_without_tombstone"
        assert issues[0].resolved_status == "deleted"


class TestChapterFrontmatterRefs:
    async def test_check_refs_finds_deleted_frontmatter_id(self) -> None:
        chapter_repo = _FakeChapterRepo()
        entity_id = uuid4()
        chapter_repo.seed(_chapter(content=f"---\nlocation: {entity_id}\n---\nBody"))
        index = _index(_FakeKBRepo(), chapter_repo=chapter_repo)

        issues = await index.check_refs(
            novel_id=uuid4(),
            consumer_feature="chapter_frontmatter",
        )

        assert len(issues) == 1
        assert issues[0].consumer_feature == "chapter_frontmatter"
        assert issues[0].reason == "deleted_ref_without_tombstone"
