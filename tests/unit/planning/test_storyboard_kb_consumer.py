"""Behaviour tests for the Storyboard KB-lifecycle consumer (planning module).

``StoryboardRefConsumerImpl`` — name-based free text in scene plans (all
text fields, spec §7) and ``outline_notes``. NEVER rewrites (RULE-22 §7);
only emits ``RefIntegrityIssue``. Split out of ``test_kb_lifecycle_consumer``
for the 400-line test-file limit (RULE-04) when the scene scan landed
(PLAN-001 T14).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from narrare.consistency.ref_integrity_sink import InMemoryRefIntegrityIssueSink
from narrare.planning.kb_lifecycle_consumer import StoryboardRefConsumerImpl
from narrare.planning.models import ChapterOutline, ScenePlan
from narrare_core.context.integration_contracts import (
    KBEntityLifecycleObserver,
    StoryboardRefConsumer,
)


class _FakeOutlineRepo:
    def __init__(self) -> None:
        self.outlines: dict[UUID, ChapterOutline] = {}

    def seed(self, outline: ChapterOutline) -> None:
        self.outlines[outline.id] = outline

    async def get_all_for_novel(self, novel_id: UUID) -> list[ChapterOutline]:
        return list(self.outlines.values())


class _FakeSceneRepo:
    def __init__(self) -> None:
        self.scenes: list[ScenePlan] = []

    def seed(self, *scenes: ScenePlan) -> None:
        self.scenes.extend(scenes)

    async def list_by_novel(self, novel_id: UUID) -> list[ScenePlan]:
        return list(self.scenes)


def _outline(*, outline_notes: str = "") -> ChapterOutline:
    return ChapterOutline(
        id=uuid4(),
        chapter_id=uuid4(),
        outline_notes=outline_notes,
    )


def _scene(
    *,
    title: str = "Opening",
    purpose: str = "",
    conflict: str = "",
    resolution: str = "",
    beats: list[str] | None = None,
    present_characters: list[dict[str, object]] | None = None,
    pov_character_ref: dict[str, object] | None = None,
    location_ref: dict[str, object] | None = None,
) -> ScenePlan:
    return ScenePlan(
        id=uuid4(),
        chapter_id=uuid4(),
        position=1,
        title=title,
        purpose=purpose,
        conflict=conflict,
        resolution=resolution,
        beats=list(beats or []),
        present_characters=list(present_characters or []),
        pov_character_ref=pov_character_ref,
        location_ref=location_ref,
    )


# ---------------------------------------------------------------------------
# Storyboard consumer — NEVER rewrites, only emits issues
# ---------------------------------------------------------------------------


def _make_storyboard_consumer(
    outline_repo: _FakeOutlineRepo,
    scene_repo: _FakeSceneRepo,
    sink: InMemoryRefIntegrityIssueSink,
) -> StoryboardRefConsumerImpl:
    return StoryboardRefConsumerImpl(
        outline_repo=outline_repo,
        scene_repo=scene_repo,
        issue_sink=sink,
    )


class TestStoryboardConsumerProtocol:
    def test_satisfies_core_protocols(self) -> None:
        consumer = _make_storyboard_consumer(
            _FakeOutlineRepo(), _FakeSceneRepo(), InMemoryRefIntegrityIssueSink()
        )
        assert isinstance(consumer, KBEntityLifecycleObserver)
        assert isinstance(consumer, StoryboardRefConsumer)
        assert consumer.consumer_feature == "storyboard"


class TestStoryboardRename:
    async def test_rename_emits_stale_name_ref_for_scene_and_notes_match(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        outline_repo = _FakeOutlineRepo()
        scene_repo = _FakeSceneRepo()
        outline = _outline(outline_notes="John arrives at the castle.")
        scene = _scene(purpose="John confronts the villain.")
        outline_repo.seed(outline)
        scene_repo.seed(scene)
        consumer = _make_storyboard_consumer(outline_repo, scene_repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        # Two matches: one in a scene field, one in outline_notes.
        issues = sink.issues
        assert len(issues) == 2
        assert all(i.reason == "stale_name_ref" for i in issues)
        assert all(i.consumer_feature == "storyboard" for i in issues)
        locations = {i.consumer_location for i in issues}
        assert locations == {
            f"scene_plans[{scene.id}].purpose",
            f"chapter_outlines[{outline.id}].outline_notes",
        }

    async def test_rename_scans_all_scene_text_fields(self) -> None:
        """Spec §7 field set: title/purpose/conflict/resolution/beats[]/
        present_characters[].name+goal/pov+location ref names."""
        sink = InMemoryRefIntegrityIssueSink()
        scene_repo = _FakeSceneRepo()
        scene_repo.seed(
            _scene(
                title="John at the gates",
                conflict="John vs the guard",
                resolution="John prevails",
                beats=["John storms the yard"],
                present_characters=[
                    {"name": "John", "goal": "escape"},
                    {"name": "Guard", "goal": "stop John"},
                ],
                pov_character_ref={"id": str(uuid4()), "name": "John"},
                location_ref={"id": str(uuid4()), "name": "John's keep"},
            )
        )
        consumer = _make_storyboard_consumer(_FakeOutlineRepo(), scene_repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        locations = {i.consumer_location for i in sink.issues}
        assert any(".title" in loc for loc in locations)
        assert any(".conflict" in loc for loc in locations)
        assert any(".resolution" in loc for loc in locations)
        assert any(".beats[0]" in loc for loc in locations)
        assert any(".present_characters[0].name" in loc for loc in locations)
        assert any(".present_characters[1].goal" in loc for loc in locations)
        assert any(".pov_character_ref.name" in loc for loc in locations)
        assert any(".location_ref.name" in loc for loc in locations)

    async def test_rename_does_not_rewrite_user_content(self) -> None:
        """RULE-22 §7: scene plans and outline_notes are user content."""
        sink = InMemoryRefIntegrityIssueSink()
        outline_repo = _FakeOutlineRepo()
        scene_repo = _FakeSceneRepo()
        outline = _outline(outline_notes="John is here.")
        scene = _scene(purpose="John fights.", beats=["John wins"])
        outline_repo.seed(outline)
        scene_repo.seed(scene)
        consumer = _make_storyboard_consumer(outline_repo, scene_repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )
        # CRITICAL: user content is byte-for-byte unchanged — the consumer
        # is read-only (issues only). Matches: notes + purpose + beats[0].
        assert outline.outline_notes == "John is here."
        assert scene.purpose == "John fights."
        assert scene.beats == ["John wins"]
        assert len(sink.issues) == 3

    async def test_rename_no_match_emits_nothing(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        outline_repo = _FakeOutlineRepo()
        scene_repo = _FakeSceneRepo()
        outline_repo.seed(_outline(outline_notes=""))
        scene_repo.seed(_scene(purpose="Anna leaves."))
        consumer = _make_storyboard_consumer(outline_repo, scene_repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=uuid4(),
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )
        assert sink.issues == []
