"""Unit tests for StoryboardService — AI-powered remap (WRITE-012).

Tests the AIRemapService integration in StoryboardService, ensuring:
- AI remap is used when enough chapters have summaries
- Position-ratio heuristic is the fallback when summaries are insufficient
- Coverage threshold logic works correctly
"""

from __future__ import annotations

import uuid

import pytest

from narrare.planning._remap_helpers import ai_suggest_stage, should_use_ai_remap
from narrare.planning.service import StoryboardService
from narrare_core.planning.remap import AIRemapService
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.factories import make_chapter, make_chapter_outline, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeOutlineRepository


def make_ai_remap_service() -> AIRemapService:
    """AIRemapService with a real (governed) composer — FO-9 contract."""
    return AIRemapService(composer=PromptComposer(PromptRegistry()))


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
def ai_remap_service() -> AIRemapService:
    return make_ai_remap_service()


@pytest.fixture
def service(
    outline_repo: FakeOutlineRepository,
    chapter_repo: FakeChapterRepository,
    novel_repo: FakeNovelRepository,
    ai_remap_service: AIRemapService,
) -> StoryboardService:
    return StoryboardService(
        outline_repo=outline_repo,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        ai_remap_service=ai_remap_service,
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
    *,
    with_summaries: bool = False,
) -> list[uuid.UUID]:
    """Seed N chapters for a novel, optionally with summaries."""
    ids: list[uuid.UUID] = []
    for i in range(count):
        ch = make_chapter(
            novel_id=novel_id,
            position=i,
            title=f"Chapter {i + 1}",
            summary=f"Summary of chapter {i + 1}." if with_summaries else "",
            content="Some content here." if with_summaries else "",
        )
        chapter_repo.seed(ch)
        ids.append(ch.id)
    return ids


# ---------------------------------------------------------------------------
# AI Remap coverage checks
# ---------------------------------------------------------------------------


class TestShouldUseAIRemap:
    """Tests for should_use_ai_remap() helper."""

    async def test_uses_ai_when_summary_coverage_met(
        self,
        chapter_repo: FakeChapterRepository,
        novel_repo: FakeNovelRepository,
    ) -> None:
        """AI remap is used when >50% of chapters have summaries."""
        novel_id, _user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 3, with_summaries=True)

        chapters = await chapter_repo.list_by_novel(novel_id)
        result = await should_use_ai_remap(make_ai_remap_service(), chapters)

        assert result is True

    async def test_falls_back_when_summary_coverage_below_threshold(
        self,
        chapter_repo: FakeChapterRepository,
        novel_repo: FakeNovelRepository,
    ) -> None:
        """Position heuristic is used when <50% of chapters have summaries."""
        novel_id, _user_id = _seed_novel(novel_repo)
        ids = _seed_chapters(chapter_repo, novel_id, 4)
        # Give only 1 out of 4 chapters a summary (25% < 50%)
        ch = await chapter_repo.get(ids[0])
        if ch is not None:
            ch.summary = "Only this chapter has a summary."

        chapters = await chapter_repo.list_by_novel(novel_id)
        result = await should_use_ai_remap(make_ai_remap_service(), chapters)

        assert result is False

    async def test_falls_back_when_no_ai_service(
        self,
        chapter_repo: FakeChapterRepository,
        novel_repo: FakeNovelRepository,
    ) -> None:
        """Without AIRemapService, always use position heuristic."""
        novel_id, _user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 3, with_summaries=True)

        chapters = await chapter_repo.list_by_novel(novel_id)
        result = await should_use_ai_remap(None, chapters)

        assert result is False


# ---------------------------------------------------------------------------
# AI Remap preview
# ---------------------------------------------------------------------------


class TestPreviewRemapWithAI:
    """Tests for preview_remap with AIRemapService."""

    async def test_preview_uses_position_heuristic_when_no_summaries(
        self,
        service: StoryboardService,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        outline_repo: FakeOutlineRepository,
    ) -> None:
        """Without summaries, preview falls back to position-based stages."""
        novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
        chapter_ids = _seed_chapters(chapter_repo, novel_id, 3)
        for cid in chapter_ids:
            outline_repo.seed(make_chapter_outline(chapter_id=cid, stage_assignment="act-1"))

        result = await service.preview_remap(novel_id, "five_act", user_id)

        assert result.new_structure == "five_act"
        assert result.confirmed is False
        assert len(result.remapped) == 3
        # All should be position-suggested (no summaries)
        five_act_stages = {"exposition", "rising-action", "climax", "falling-action", "resolution"}
        for item in result.remapped:
            assert item.new_stage in five_act_stages


# ---------------------------------------------------------------------------
# Helper verification
# ---------------------------------------------------------------------------


class TestAISuggestStage:
    """Tests for ai_suggest_stage() helper."""

    async def test_falls_back_to_adapter_when_analysis_returns_empty(self) -> None:
        """When AI analysis returns empty string, use position heuristic."""
        from narrare_core.planning.adapters import registry as adapter_registry

        adapter = adapter_registry.get("three_act")
        stage = await ai_suggest_stage(
            ai_remap_service=make_ai_remap_service(),
            summary="A test summary.",
            structure_type="three_act",
            position=1,
            total=3,
            adapter=adapter,
        )

        # Falls back to adapter since no agent is provided
        assert stage == adapter.suggest_stage(1, 3)

    async def test_falls_back_when_no_ai_service(self) -> None:
        """When no AIRemapService, always use position heuristic."""
        from narrare_core.planning.adapters import registry as adapter_registry

        adapter = adapter_registry.get("three_act")
        stage = await ai_suggest_stage(
            ai_remap_service=None,
            summary="A test summary.",
            structure_type="three_act",
            position=2,
            total=3,
            adapter=adapter,
        )

        assert stage == adapter.suggest_stage(2, 3)
