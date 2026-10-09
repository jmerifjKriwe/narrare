"""Unit tests for FakeScenePlanRepository fidelity (PLAN-001 T3).

``FakeScenePlanRepository`` implements ``ScenePlanRepositoryProtocol``
in-memory (RULE-23 — no MagicMocks). This file verifies the fake mirrors the
real repository's contract, which is critical because the T4 aggregate service
tests depend on this fake being faithful (pattern:
``test_planning_repository.py`` for ``FakeOutlineRepository``).

Real-side wiring and diff semantics are pinned in
``test_repository_scenes.py``; the foreign-id case is proven on BOTH halves —
here (fake raises, nothing stolen) and there (real repo takes the INSERT path
whose flush is the DB-side PK collision).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from tests.factories import make_chapter
from tests.fakes.fake_scene_repo import FakeScenePlanRepository
from tests.unit.api.planning._scene_repo_test_helpers import _scene


class TestFakeGet:
    async def test_returns_seeded_scene(self) -> None:
        repo = FakeScenePlanRepository()
        scene = _scene()
        repo.seed(scene)

        assert await repo.get(scene.id) is scene

    async def test_returns_none_when_missing(self) -> None:
        assert await FakeScenePlanRepository().get(uuid.uuid4()) is None


class TestFakeListOrdering:
    async def test_list_by_chapter_orders_by_position_and_filters_chapter(self) -> None:
        repo = FakeScenePlanRepository()
        cid = uuid.uuid4()
        repo.seed(
            _scene(chapter_id=cid, position=3),
            _scene(chapter_id=cid, position=1),
            _scene(chapter_id=cid, position=2),
            _scene(position=9),  # other chapter
        )

        result = await repo.list_by_chapter(cid)

        assert [scene.position for scene in result] == [1, 2, 3]

    async def test_list_by_novel_orders_by_chapter_then_scene_position(self) -> None:
        repo = FakeScenePlanRepository()
        novel_id = uuid.uuid4()
        chapter_one = make_chapter(novel_id=novel_id, position=0)
        chapter_two = make_chapter(novel_id=novel_id, position=1)
        foreign = make_chapter(novel_id=uuid.uuid4(), position=0)
        repo.seed_chapters(chapter_one, chapter_two, foreign)
        in_ch2 = _scene(chapter_id=chapter_two.id, position=1)
        ch1_second = _scene(chapter_id=chapter_one.id, position=2)
        ch1_first = _scene(chapter_id=chapter_one.id, position=1)
        in_foreign = _scene(chapter_id=foreign.id, position=1)
        orphan = _scene(position=1)  # chapter unknown → INNER JOIN mirror
        repo.seed(in_ch2, ch1_second, ch1_first, in_foreign, orphan)

        result = await repo.list_by_novel(novel_id)

        assert result == [ch1_first, ch1_second, in_ch2]


class TestFakeBulkReplace:
    async def test_replaces_existing_scene_fields_by_id(self) -> None:
        repo = FakeScenePlanRepository()
        cid = uuid.uuid4()
        existing = _scene(chapter_id=cid, position=1, title="Old")
        repo.seed(existing)
        rows = [_scene(id=existing.id, chapter_id=cid, title="New", status="complete")]

        result = await repo.bulk_replace(cid, rows)

        assert result == rows
        assert (await repo.list_by_chapter(cid))[0].title == "New"

    async def test_inserts_new_scene_retrievable_by_id(self) -> None:
        repo = FakeScenePlanRepository()
        cid = uuid.uuid4()
        fresh = _scene(chapter_id=cid)

        await repo.bulk_replace(cid, [fresh])

        assert await repo.get(fresh.id) is fresh

    async def test_deletes_scenes_absent_from_payload(self) -> None:
        repo = FakeScenePlanRepository()
        cid = uuid.uuid4()
        kept = _scene(chapter_id=cid)
        dropped = _scene(chapter_id=cid)
        repo.seed(kept, dropped)

        await repo.bulk_replace(cid, [kept])

        assert await repo.get(dropped.id) is None
        assert await repo.get(kept.id) is kept

    async def test_foreign_scene_id_raises_integrity_error_state_unchanged(self) -> None:
        # Mirrors the real repo: a foreign id is treated as INSERT → PK
        # collision at flush (IntegrityError). The fake raises up front and
        # must not steal/move the scene (silent overwrite is forbidden).
        repo = FakeScenePlanRepository()
        owner_chapter = uuid.uuid4()
        stored_scene = _scene(chapter_id=owner_chapter, position=1)
        repo.seed(stored_scene)
        other_chapter = uuid.uuid4()

        with pytest.raises(IntegrityError, match="scene_plans_pkey"):
            await repo.bulk_replace(other_chapter, [stored_scene])

        assert await repo.get(stored_scene.id) is stored_scene
        assert await repo.list_by_chapter(owner_chapter) == [stored_scene]
        assert await repo.list_by_chapter(other_chapter) == []

    async def test_renumbers_positions_in_payload_order(self) -> None:
        repo = FakeScenePlanRepository()
        cid = uuid.uuid4()
        first = _scene(chapter_id=cid, position=1)
        second = _scene(chapter_id=cid, position=2)
        repo.seed(first, second)

        await repo.bulk_replace(
            cid,
            [_scene(id=second.id, chapter_id=cid), _scene(id=first.id, chapter_id=cid)],
        )

        scenes = await repo.list_by_chapter(cid)
        assert [scene.id for scene in scenes] == [second.id, first.id]
        assert [scene.position for scene in scenes] == [1, 2]


class TestFakeCallTracking:
    async def test_call_count_and_assert_called_once(self) -> None:
        repo = FakeScenePlanRepository()

        await repo.get(uuid.uuid4())
        await repo.get(uuid.uuid4())

        assert repo.call_count("get") == 2
        with pytest.raises(AssertionError, match="Expected 1 call"):
            repo.assert_called_once("get")
