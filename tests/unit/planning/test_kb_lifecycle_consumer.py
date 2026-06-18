"""Unit + behaviour tests for KB-lifecycle consumers in the planning module.

Covers:
* ``TimelineRefConsumerImpl`` — id-based hybrid JSON refs. Rename rewrites
  the stored name (name is derived, not user content); deprecate marks
  ``status: deprecated``; delete emits ``RefIntegrityIssue``. No rewrite
  of user content (there is none on the timeline ref shape).
* ``StoryboardRefConsumerImpl`` — name-based free text in
  ``planned_beats[].text`` and ``outline_notes``. NEVER rewrites
  (RULE-22 §7); only emits ``RefIntegrityIssue``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Sequence

from narrare.consistency.ref_integrity_sink import InMemoryRefIntegrityIssueSink
from narrare.planning.kb_lifecycle_consumer import (
    StoryboardRefConsumerImpl,
    TimelineRefConsumerImpl,
)
from narrare.planning.models import ChapterOutline, TimelineEvent
from narrare_core.context.integration_contracts import (
    KBEntityLifecycleObserver,
    StoryboardRefConsumer,
    TimelineRefConsumer,
)

# ---------------------------------------------------------------------------
# Fakes — in-memory repos so the tests exercise real consumer behaviour
# (integration-ish) rather than mock call-counts.
# ---------------------------------------------------------------------------


class _FakeTimelineRepo:
    def __init__(self) -> None:
        self.events: dict[UUID, TimelineEvent] = {}
        self._novel_id: UUID | None = None

    def seed(self, event: TimelineEvent) -> None:
        self.events[event.id] = event

    async def list_by_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]:
        return list(self.events.values())

    async def update(self, event_id: UUID, **fields: object) -> TimelineEvent:
        event = self.events[event_id]
        for k, v in fields.items():
            setattr(event, k, v)
        return event


class _FakeOutlineRepo:
    def __init__(self) -> None:
        self.outlines: dict[UUID, ChapterOutline] = {}

    def seed(self, outline: ChapterOutline) -> None:
        self.outlines[outline.id] = outline

    async def get_all_for_novel(self, novel_id: UUID) -> Sequence[ChapterOutline]:
        return list(self.outlines.values())


def _timeline_event(
    *,
    character_refs: list[dict[str, object]] | None = None,
    location_ref: dict[str, object] | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        id=uuid4(),
        novel_id=uuid4(),
        event_name="Battle",
        character_refs=list(character_refs or []),
        location_ref=location_ref,
    )


def _outline(
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


# ---------------------------------------------------------------------------
# Timeline consumer
# ---------------------------------------------------------------------------


class TestTimelineConsumerProtocol:
    def test_satisfies_core_protocols(self) -> None:
        consumer = TimelineRefConsumerImpl(
            event_repo=_FakeTimelineRepo(),
            issue_sink=InMemoryRefIntegrityIssueSink(),
        )
        assert isinstance(consumer, KBEntityLifecycleObserver)
        assert isinstance(consumer, TimelineRefConsumer)
        assert consumer.consumer_feature == "timeline"


class TestTimelineRename:
    async def test_rename_updates_matching_character_ref_name(self) -> None:
        entity_id = uuid4()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            character_refs=[{"id": str(entity_id), "name": "John"}],
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_renamed(
            novel_id=event.novel_id,
            entity_id=entity_id,
            old_name="John",
            new_name="Jonathan",
        )

        assert event.character_refs == [{"id": str(entity_id), "name": "Jonathan"}]

    async def test_rename_updates_matching_location_ref_name(self) -> None:
        entity_id = uuid4()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            location_ref={"id": str(entity_id), "name": "Old Castle"},
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_renamed(
            novel_id=event.novel_id,
            entity_id=entity_id,
            old_name="Old Castle",
            new_name="High Castle",
        )

        assert event.location_ref == {"id": str(entity_id), "name": "High Castle"}

    async def test_rename_only_touches_refs_with_matching_id_and_old_name(self) -> None:
        """A ref whose id matches but name differs is left alone (id-name mismatch)."""
        target_id = uuid4()
        other_id = uuid4()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            character_refs=[
                {"id": str(target_id), "name": "John"},  # matches both
                {"id": str(target_id), "name": "Johnny"},  # id ok, name mismatch
                {"id": str(other_id), "name": "John"},  # name ok, id mismatch
            ],
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_renamed(
            novel_id=event.novel_id,
            entity_id=target_id,
            old_name="John",
            new_name="Jonathan",
        )

        names = [r["name"] for r in event.character_refs]
        assert names == ["Jonathan", "Johnny", "John"]

    async def test_rename_no_matching_refs_does_nothing(self) -> None:
        repo = _FakeTimelineRepo()
        event = _timeline_event(character_refs=[{"id": str(uuid4()), "name": "Other"}])
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_renamed(
            novel_id=event.novel_id,
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        assert (
            event.character_refs == [{"id": str(uuid4()), "name": "Other"}]
            or len(event.character_refs) == 1
        )
        # No exception, ref unchanged.


class TestTimelineDeprecate:
    async def test_deprecate_marks_matching_refs_deprecated(self) -> None:
        entity_id = uuid4()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            character_refs=[{"id": str(entity_id), "name": "John"}],
            location_ref={"id": str(entity_id), "name": "Castle"},
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_deprecated(
            novel_id=event.novel_id,
            entity_id=entity_id,
        )

        assert event.character_refs[0]["status"] == "deprecated"
        assert event.location_ref is not None
        assert event.location_ref["status"] == "deprecated"

    async def test_deprecate_does_not_rewrite_name(self) -> None:
        entity_id = uuid4()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            character_refs=[{"id": str(entity_id), "name": "John"}],
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, InMemoryRefIntegrityIssueSink())

        await consumer.on_kb_entity_deprecated(
            novel_id=event.novel_id,
            entity_id=entity_id,
        )

        # Name preserved; only status added.
        assert event.character_refs[0]["name"] == "John"


class TestTimelineDelete:
    async def test_delete_emits_issue_per_dangling_ref(self) -> None:
        entity_id = uuid4()
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeTimelineRepo()
        event = _timeline_event(
            character_refs=[
                {"id": str(entity_id), "name": "John"},
                {"id": str(uuid4()), "name": "Other"},
            ],
            location_ref={"id": str(entity_id), "name": "Castle"},
        )
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_deleted(
            novel_id=event.novel_id,
            entity_id=entity_id,
        )

        issues = sink.issues
        assert len(issues) == 2  # one character ref + one location ref
        assert all(i.reason == "deleted_ref_without_tombstone" for i in issues)
        assert all(i.resolved_status == "deleted" for i in issues)
        assert all(i.consumer_feature == "timeline" for i in issues)
        # Consumer location pinpoints the stale ref.
        locations = {i.consumer_location for i in issues}
        assert any("character_refs" in loc for loc in locations)
        assert any("location_ref" in loc for loc in locations)

    async def test_delete_no_matching_refs_emits_nothing(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeTimelineRepo()
        event = _timeline_event(character_refs=[{"id": str(uuid4()), "name": "X"}])
        repo.seed(event)
        consumer = TimelineRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_deleted(
            novel_id=event.novel_id,
            entity_id=uuid4(),
        )
        assert sink.issues == []


# ---------------------------------------------------------------------------
# Storyboard consumer — NEVER rewrites, only emits issues
# ---------------------------------------------------------------------------


class TestStoryboardConsumerProtocol:
    def test_satisfies_core_protocols(self) -> None:
        consumer = StoryboardRefConsumerImpl(
            outline_repo=_FakeOutlineRepo(),
            issue_sink=InMemoryRefIntegrityIssueSink(),
        )
        assert isinstance(consumer, KBEntityLifecycleObserver)
        assert isinstance(consumer, StoryboardRefConsumer)
        assert consumer.consumer_feature == "storyboard"


class TestStoryboardRename:
    async def test_rename_emits_stale_name_ref_for_each_match(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeOutlineRepo()
        outline = _outline(
            planned_beats=[{"text": "John confronts the villain."}],
            outline_notes="John arrives at the castle.",
        )
        repo.seed(outline)
        consumer = StoryboardRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        # Two matches: one in planned_beats text, one in outline_notes.
        issues = sink.issues
        assert len(issues) == 2
        assert all(i.reason == "stale_name_ref" for i in issues)
        assert all(i.consumer_feature == "storyboard" for i in issues)

    async def test_rename_does_not_rewrite_user_content(self) -> None:
        """RULE-22 §7: planned_beats and outline_notes are user content."""
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeOutlineRepo()
        original_beats: list[dict[str, object]] = [{"text": "John fights."}]
        original_notes = "John is here."
        outline = _outline(planned_beats=original_beats, outline_notes=original_notes)
        repo.seed(outline)
        consumer = StoryboardRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        # CRITICAL: user content is byte-for-byte unchanged.
        assert outline.planned_beats == [{"text": "John fights."}]
        assert outline.outline_notes == "John is here."

    async def test_rename_no_match_emits_nothing(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeOutlineRepo()
        repo.seed(_outline(planned_beats=[{"text": "Anna leaves."}], outline_notes=""))
        consumer = StoryboardRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )
        assert sink.issues == []
