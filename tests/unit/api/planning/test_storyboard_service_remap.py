"""Unit tests for StoryboardService — remap operations (preview + confirm).

Uses FakeOutlineRepository, FakeChapterRepository, and FakeNovelRepository
to test remap methods without I/O.
"""

from __future__ import annotations

import pytest

from narrare.planning.service import StoryboardService
from tests.factories import make_chapter_outline
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeOutlineRepository
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
def service(
    outline_repo: FakeOutlineRepository,
    chapter_repo: FakeChapterRepository,
    novel_repo: FakeNovelRepository,
) -> StoryboardService:
    return StoryboardService(
        outline_repo=outline_repo,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_resolution=make_static_resolution(),
    )


# ---------------------------------------------------------------------------
# preview_remap
# ---------------------------------------------------------------------------


class TestPreviewRemap:
    async def test_preview_does_not_modify(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        from tests.unit.api.planning.test_storyboard_service import (
            _seed_chapters,
            _seed_novel,
        )

        novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 3)
        for cid in chapter_ids:
            outline_repo.seed(make_chapter_outline(chapter_id=cid, stage_assignment="act-1"))

        result = await service.preview_remap(novel_id, "five_act", user_id)

        assert result.new_structure == "five_act"
        assert result.confirmed is False
        assert len(result.remapped) == 3
        assert outline_repo.call_count("update") == 0

    async def test_preview_raises_for_invalid_structure(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
    ) -> None:
        from tests.unit.api.planning.test_storyboard_service import _seed_novel

        novel_id, user_id = _seed_novel(novel_repo)

        with pytest.raises(ValueError, match="Unknown structure type"):
            await service.preview_remap(novel_id, "nonexistent", user_id)


# ---------------------------------------------------------------------------
# confirm_remap
# ---------------------------------------------------------------------------


class TestConfirmRemap:
    async def test_confirm_updates_outlines_and_novel(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        from tests.unit.api.planning.test_storyboard_service import (
            _seed_chapters,
            _seed_novel,
        )

        novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 3)
        for cid in chapter_ids:
            outline_repo.seed(make_chapter_outline(chapter_id=cid, stage_assignment="act-1"))

        result = await service.confirm_remap(novel_id, "five_act", user_id)

        assert result.confirmed is True
        assert result.new_structure == "five_act"
        assert outline_repo.call_count("update") == 3
