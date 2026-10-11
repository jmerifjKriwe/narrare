"""Unit tests for ScenePlanService — aggregate read path (PLAN-001 T4).

Uses FakeScenePlanRepository and the house FakeChapterRepository /
FakeNovelRepository — no I/O, no MagicMocks. The diff-sync save matrix
lives in ``test_scene_service_save.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from narrare.planning.scene_service import ScenePlanService
from narrare.planning.schemas_scenes import ScenePresenceSchema, SceneRefSchema
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeScenePlanRepository
from tests.unit.api.planning._scene_service_test_helpers import _scene_row, _World

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scene_repo() -> FakeScenePlanRepository:
    return FakeScenePlanRepository()


@pytest.fixture
def chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    return FakeNovelRepository()


@pytest.fixture
def service(
    scene_repo: FakeScenePlanRepository,
    chapter_repo: FakeChapterRepository,
    novel_repo: FakeNovelRepository,
) -> ScenePlanService:
    return ScenePlanService(
        scene_repo=scene_repo,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


@pytest.fixture
def world(
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
) -> _World:
    return _World(novel_repo, chapter_repo)


# ---------------------------------------------------------------------------
# get_aggregate
# ---------------------------------------------------------------------------


class TestGetAggregate:
    async def test_returns_scenes_ordered_by_position(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        scene_repo.seed(
            _scene_row(world.chapter_id, position=3, title="Third"),
            _scene_row(world.chapter_id, position=1, title="First"),
            _scene_row(world.chapter_id, position=2, title="Second"),
        )

        result = await service.get_aggregate(
            world.chapter_id, world.user_id, novel_id=world.novel_id
        )

        assert [s.title for s in result.scenes] == ["First", "Second", "Third"]
        assert [s.position for s in result.scenes] == [1, 2, 3]

    async def test_empty_aggregate_when_no_scenes(
        self,
        service: ScenePlanService,
        world: _World,
    ) -> None:
        result = await service.get_aggregate(
            world.chapter_id, world.user_id, novel_id=world.novel_id
        )

        assert result.chapter_id == world.chapter_id
        assert result.scenes == []
        assert result.version_updated_at is not None

    async def test_foreign_novel_raises_not_found(
        self,
        service: ScenePlanService,
        world: _World,
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.get_aggregate(
                world.chapter_id, world.user_id, novel_id=world.foreign_novel_id
            )

    async def test_unknown_novel_raises_not_found(
        self,
        service: ScenePlanService,
        world: _World,
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.get_aggregate(world.chapter_id, world.user_id, novel_id=uuid.uuid4())

    async def test_chapter_of_other_novel_raises_not_found(
        self,
        service: ScenePlanService,
        chapter_repo: FakeChapterRepository,
        novel_repo: FakeNovelRepository,
        world: _World,
    ) -> None:
        other_novel_id = uuid.uuid4()
        novel_repo.seed(make_novel(id=other_novel_id, user_id=world.user_id))
        other_chapter_id = uuid.uuid4()
        chapter_repo.seed(make_chapter(id=other_chapter_id, novel_id=other_novel_id, position=0))

        with pytest.raises(NotFoundError):
            await service.get_aggregate(other_chapter_id, world.user_id, novel_id=world.novel_id)

    async def test_maps_hybrid_fields_field_for_field(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        pov_id = str(uuid.uuid4())
        char_id = str(uuid.uuid4())
        created = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
        scene_repo.seed(
            _scene_row(
                world.chapter_id,
                position=1,
                title="The Ambush",
                pov_character_ref={"id": pov_id, "name": "John Smith"},
                location_ref={"id": None, "name": "The Castle"},
                present_characters=[{"id": char_id, "name": "Mara", "goal": "stop him"}],
                purpose="Reach the gate",
                conflict="Mara blocks the path",
                resolution="Talks his way past",
                beats=["John reaches the gate", "The horn sounds"],
                status="in_progress",
                created_at=created,
                updated_at=created,
            )
        )

        result = await service.get_aggregate(
            world.chapter_id, world.user_id, novel_id=world.novel_id
        )

        scene = result.scenes[0]
        assert scene.pov_character_ref == SceneRefSchema(id=uuid.UUID(pov_id), name="John Smith")
        assert scene.location_ref == SceneRefSchema(id=None, name="The Castle")
        assert scene.present_characters == [
            ScenePresenceSchema(id=uuid.UUID(char_id), name="Mara", goal="stop him")
        ]
        assert scene.purpose == "Reach the gate"
        assert scene.status == "in_progress"
        assert scene.beats == ["John reaches the gate", "The horn sounds"]
        assert scene.created_at == created
        assert scene.updated_at == created
        assert result.version_updated_at == created
