"""Unit tests for ScenePlanService — diff-sync save matrix (PLAN-001 T4, §5.3).

The foreign-scene-id test runs against the raising fake path
(``FakeScenePlanRepository`` raises ``IntegrityError`` on cross-chapter
ids, mirroring the real PK collision) — never a silent overwrite.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.planning.scene_service import ScenePlanService
from narrare_core.shared.errors import NotFoundError, ValidationError
from tests.factories import make_chapter, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeScenePlanRepository
from tests.unit.api.planning._scene_service_test_helpers import (
    _payload_scene,
    _save_request,
    _scene_row,
    _World,
)

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
# Insert / update / delete / renumber
# ---------------------------------------------------------------------------


class TestSaveInsertUpdateDelete:
    async def test_insert_with_client_uuid_persists_and_returns_fresh(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        new_id = uuid.uuid4()

        result = await service.save_aggregate(
            world.chapter_id,
            _save_request(_payload_scene(new_id, title="Fresh")),
            world.user_id,
            novel_id=world.novel_id,
        )

        assert [s.id for s in result.scenes] == [new_id]
        assert result.scenes[0].title == "Fresh"
        assert result.scenes[0].position == 1

    async def test_update_replaces_editable_fields(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        existing = _scene_row(world.chapter_id, position=1, title="Old")
        scene_repo.seed(existing)

        await service.save_aggregate(
            world.chapter_id,
            _save_request(
                _payload_scene(
                    existing.id,
                    title="New",
                    purpose="Updated purpose",
                    status="complete",
                    beats=["b1"],
                )
            ),
            world.user_id,
            novel_id=world.novel_id,
        )

        result = await service.get_aggregate(
            world.chapter_id, world.user_id, novel_id=world.novel_id
        )
        assert len(result.scenes) == 1
        scene = result.scenes[0]
        assert scene.title == "New"
        assert scene.purpose == "Updated purpose"
        assert scene.status == "complete"
        assert scene.beats == ["b1"]

    async def test_absent_id_is_deleted(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        kept = _scene_row(world.chapter_id, position=1, title="Kept")
        dropped = _scene_row(world.chapter_id, position=2, title="Dropped")
        scene_repo.seed(kept, dropped)

        result = await service.save_aggregate(
            world.chapter_id,
            _save_request(_payload_scene(kept.id, title="Kept")),
            world.user_id,
            novel_id=world.novel_id,
        )

        assert [s.id for s in result.scenes] == [kept.id]

    async def test_empty_payload_deletes_all(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        scene_repo.seed(
            _scene_row(world.chapter_id, position=1),
            _scene_row(world.chapter_id, position=2),
        )

        result = await service.save_aggregate(
            world.chapter_id, _save_request(), world.user_id, novel_id=world.novel_id
        )

        assert result.scenes == []

    async def test_renumbers_positions_in_payload_order(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        first = _scene_row(world.chapter_id, position=1, title="A")
        second = _scene_row(world.chapter_id, position=2, title="B")
        scene_repo.seed(first, second)
        # Reversed payload order: B must become position 1, A position 2.
        fresh_b = _payload_scene(second.id, title="B")
        fresh_a = _payload_scene(first.id, title="A")

        result = await service.save_aggregate(
            world.chapter_id,
            _save_request(fresh_b, fresh_a),
            world.user_id,
            novel_id=world.novel_id,
        )

        assert [(s.title, s.position) for s in result.scenes] == [("B", 1), ("A", 2)]

    async def test_mixed_insert_update_delete_renumber(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        keep = _scene_row(world.chapter_id, position=1, title="Keep")
        drop = _scene_row(world.chapter_id, position=2, title="Drop")
        scene_repo.seed(keep, drop)
        new_id = uuid.uuid4()

        result = await service.save_aggregate(
            world.chapter_id,
            _save_request(
                _payload_scene(new_id, title="New"),
                _payload_scene(keep.id, title="Keep"),
            ),
            world.user_id,
            novel_id=world.novel_id,
        )

        assert [(s.title, s.position) for s in result.scenes] == [("New", 1), ("Keep", 2)]


# ---------------------------------------------------------------------------
# Validation — duplicate ids, foreign ids, ownership guards
# ---------------------------------------------------------------------------


class TestSaveValidation:
    async def test_duplicate_payload_id_raises_validation_error(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        world: _World,
    ) -> None:
        scene = _scene_row(world.chapter_id, position=1)
        scene_repo.seed(scene)
        duplicate = _payload_scene(scene.id)

        with pytest.raises(ValidationError, match="duplicate scene id"):
            await service.save_aggregate(
                world.chapter_id,
                _save_request(duplicate, duplicate),
                world.user_id,
                novel_id=world.novel_id,
            )
        # No partial mutation: the stored row is untouched.
        assert scene_repo.call_count("bulk_replace") == 0

    async def test_foreign_scene_id_raises_validation_error(
        self,
        service: ScenePlanService,
        scene_repo: FakeScenePlanRepository,
        chapter_repo: FakeChapterRepository,
        world: _World,
    ) -> None:
        # Foreign chapter inside the same novel — its scene id probed in this
        # chapter's payload is a payload-integrity error (422), not 404.
        foreign_chapter_id = uuid.uuid4()
        chapter_repo.seed(make_chapter(id=foreign_chapter_id, novel_id=world.novel_id, position=1))
        foreign = _scene_row(foreign_chapter_id, position=1, title="Foreign")
        scene_repo.seed(foreign)
        local = _scene_row(world.chapter_id, position=1, title="Local")
        scene_repo.seed(local)

        with pytest.raises(ValidationError, match="unknown scene id"):
            await service.save_aggregate(
                world.chapter_id,
                _save_request(_payload_scene(foreign.id), _payload_scene(local.id)),
                world.user_id,
                novel_id=world.novel_id,
            )
        # The failed save must not have touched stored state.
        stored = await scene_repo.list_by_chapter(world.chapter_id)
        assert [s.id for s in stored] == [local.id]

    async def test_save_with_foreign_novel_raises_not_found(
        self,
        service: ScenePlanService,
        world: _World,
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.save_aggregate(
                world.chapter_id,
                _save_request(_payload_scene(uuid.uuid4())),
                world.user_id,
                novel_id=world.foreign_novel_id,
            )

    async def test_save_with_chapter_of_other_novel_raises_not_found(
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
            await service.save_aggregate(
                other_chapter_id,
                _save_request(_payload_scene(uuid.uuid4())),
                world.user_id,
                novel_id=world.novel_id,
            )
