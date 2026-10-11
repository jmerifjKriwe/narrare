"""Unit tests for StoryboardService — storyboard assembly, outline CRUD, remap.

Uses FakeOutlineRepository, FakeChapterRepository, and FakeNovelRepository
to test all service methods without I/O.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.planning.schemas import OutlineUpdateRequest
from narrare.planning.service import StoryboardService
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter, make_chapter_outline, make_novel, make_scene_plan
from tests.fakes import (
    FakeChapterRepository,
    FakeNovelRepository,
    FakeOutlineRepository,
    FakeScenePlanRepository,
)
from tests.unit.api.planning._storyboard_test_helpers import make_static_resolution

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def outline_repo() -> FakeOutlineRepository:
    return FakeOutlineRepository()


@pytest.fixture
def chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    return FakeNovelRepository()


@pytest.fixture
def scene_repo() -> FakeScenePlanRepository:
    return FakeScenePlanRepository()


@pytest.fixture
def service(
    outline_repo: FakeOutlineRepository,
    chapter_repo: FakeChapterRepository,
    novel_repo: FakeNovelRepository,
    scene_repo: FakeScenePlanRepository,
) -> StoryboardService:
    return StoryboardService(
        outline_repo=outline_repo,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        scene_repo=scene_repo,
        model_resolution=make_static_resolution(),
    )


def _seed_novel(
    novel_repo: FakeNovelRepository,
    *,
    novel_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    story_structure: str = "three_act",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a novel into the fake novel repo."""
    novel_id = novel_id or uuid.uuid4()
    user_id = user_id or uuid.uuid4()
    novel = make_novel(id=novel_id, user_id=user_id, story_structure=story_structure)
    novel_repo.seed(novel)
    return novel_id, user_id


def _seed_chapters(
    chapter_repo: FakeChapterRepository,
    novel_id: uuid.UUID,
    count: int,
) -> list[uuid.UUID]:
    """Seed N chapters for a novel, return their IDs."""
    ids = []
    for i in range(count):
        ch = make_chapter(novel_id=novel_id, position=i, title=f"Chapter {i + 1}")
        chapter_repo.seed(ch)
        ids.append(ch.id)
    return ids


# ---------------------------------------------------------------------------
# get_storyboard
# ---------------------------------------------------------------------------


class TestGetStoryboard:
    async def test_storyboard_assembles_stages(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 3)

        result = await service.get_storyboard(novel_id, user_id)

        assert result.structure_type == "three_act"
        assert len(result.stages) == 3  # act-1, act-2, act-3
        # All chapters should be assigned (auto-created)
        total_chapters = sum(len(s.chapters) for s in result.stages)
        assert total_chapters == 3

    async def test_storyboard_auto_creates_outlines(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 2)

        await service.get_storyboard(novel_id, user_id)

        assert outline_repo.call_count("create") == 2

    async def test_storyboard_reuses_existing_outlines(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 2)
        for cid in chapter_ids:
            outline_repo.seed(make_chapter_outline(chapter_id=cid, stage_assignment="act-1"))

        await service.get_storyboard(novel_id, user_id)

        assert outline_repo.call_count("create") == 0

    async def test_storyboard_empty_novel(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)

        result = await service.get_storyboard(novel_id, user_id)

        assert result.structure_type == "three_act"
        assert len(result.stages) == 3
        for stage in result.stages:
            assert len(stage.chapters) == 0

    async def test_storyboard_raises_for_missing_novel(
        self,
        service: StoryboardService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.get_storyboard(uuid.uuid4(), uuid.uuid4())


# ---------------------------------------------------------------------------
# get_sync_status
# ---------------------------------------------------------------------------


class TestGetSyncStatus:
    async def test_sync_status_empty_chapters(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 2)

        result = await service.get_sync_status(novel_id, user_id)

        assert len(result) == 2
        for r in result:
            assert r.sync_status == "empty"


# ---------------------------------------------------------------------------
# Scene-driven sync (PLAN-001 T14 — ADR-096)
# ---------------------------------------------------------------------------


class TestSyncOverScenes:
    """Storyboard sync is computed over scene plans (the only substrate)."""

    async def test_all_complete_scenes_with_content_is_completed(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]
        chapter = await chapter_repo.get(ch_id)
        assert chapter is not None
        chapter.content = "Written content."
        # Single chapter → suggest_stage(1, 1) == 'act-3'; align the stage so
        # the scene rules (rule 4) decide, not the deviation rule.
        outline_repo.seed(make_chapter_outline(chapter_id=ch_id, stage_assignment="act-3"))
        scene_repo.seed_chapters(chapter)
        scene_repo.seed(
            make_scene_plan(chapter_id=ch_id, position=1, status="complete"),
            make_scene_plan(chapter_id=ch_id, position=2, status="complete"),
        )

        result = await service.get_sync_status(novel_id, user_id)

        assert result[0].sync_status == "completed"

    async def test_partial_scene_progress_is_on_track(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]
        chapter = await chapter_repo.get(ch_id)
        assert chapter is not None
        chapter.content = "Written content."
        # Single chapter → suggest_stage(1, 1) == 'act-3'; align the stage so
        # the scene rules (rule 4) decide, not the deviation rule.
        outline_repo.seed(make_chapter_outline(chapter_id=ch_id, stage_assignment="act-3"))
        scene_repo.seed_chapters(chapter)
        scene_repo.seed(
            make_scene_plan(chapter_id=ch_id, position=1, status="complete"),
            make_scene_plan(chapter_id=ch_id, position=2, status="in_progress"),
        )

        result = await service.get_sync_status(novel_id, user_id)

        assert result[0].sync_status == "on_track"

    async def test_storyboard_view_reports_scene_driven_status(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]
        chapter = await chapter_repo.get(ch_id)
        assert chapter is not None
        chapter.content = "Written content."
        # Single chapter → suggest_stage(1, 1) == 'act-3'; align the stage so
        # the scene rules (rule 4) decide, not the deviation rule.
        outline_repo.seed(make_chapter_outline(chapter_id=ch_id, stage_assignment="act-3"))
        scene_repo.seed_chapters(chapter)
        scene_repo.seed(make_scene_plan(chapter_id=ch_id, position=1, status="complete"))

        result = await service.get_storyboard(novel_id, user_id)

        statuses = [
            c.sync_status
            for stage in result.stages
            for c in stage.chapters
            if c.chapter_id == ch_id
        ]
        assert statuses == ["completed"]


# ---------------------------------------------------------------------------
# get_or_create_outline
# ---------------------------------------------------------------------------


class TestGetOrCreateOutline:
    async def test_returns_existing_outline(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]
        outline_repo.seed(make_chapter_outline(chapter_id=ch_id, stage_assignment="act-1"))

        result = await service.get_or_create_outline(ch_id, "three_act", user_id, novel_id=novel_id)

        assert result.chapter_id == ch_id
        assert result.stage_assignment == "act-1"
        outline_repo.assert_called_once("get_by_chapter_id")

    async def test_auto_creates_outline_when_missing(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]

        result = await service.get_or_create_outline(ch_id, "three_act", user_id, novel_id=novel_id)

        assert result.chapter_id == ch_id
        assert result.stage_assignment  # should be assigned
        outline_repo.assert_called_once("create")

    async def test_raises_for_missing_chapter(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)

        with pytest.raises(NotFoundError):
            await service.get_or_create_outline(
                uuid.uuid4(), "three_act", user_id, novel_id=novel_id
            )


# ---------------------------------------------------------------------------
# update_outline
# ---------------------------------------------------------------------------


class TestUpdateOutline:
    async def test_update_existing_outline(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]
        outline_repo.seed(make_chapter_outline(chapter_id=ch_id, stage_assignment="act-1"))

        result = await service.update_outline(
            ch_id,
            OutlineUpdateRequest(stage_assignment="act-2"),
            user_id,
            novel_id=novel_id,
        )

        assert result.chapter_id == ch_id
        outline_repo.assert_called_once("update")

    async def test_update_creates_if_missing(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        novel_id, user_id = _seed_novel(novel_repo)
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 1)
        ch_id = chapter_ids[0]

        result = await service.update_outline(
            ch_id,
            OutlineUpdateRequest(stage_assignment="act-1", outline_notes="test notes"),
            user_id,
            novel_id=novel_id,
        )

        assert result.chapter_id == ch_id
        outline_repo.assert_called_once("create")
