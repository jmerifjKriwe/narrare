"""Unit tests for ChapterService.get_plan_context — summary-only plan context."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from narrare.chapters.service import ChapterService
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelService

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture
def fake_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def service(
    fake_repo: FakeChapterRepository, fake_novel_service: FakeNovelService
) -> ChapterService:
    return ChapterService(repo=fake_repo, novel_service=fake_novel_service)


def _seed_novel(fake_novel_service: FakeNovelService) -> tuple[UUID, UUID]:
    """Seed an owned novel; returns (novel_id, user_id)."""
    novel_id, user_id = uuid.uuid4(), uuid.uuid4()
    fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
    return novel_id, user_id


def _seed_three_chapters(fake_repo: FakeChapterRepository, novel_id: UUID) -> list[Any]:
    """Seed three chapters at positions 0/1/2 with content + summaries."""
    chapters = [
        make_chapter(
            novel_id=novel_id,
            title="First",
            content="First prose.",
            summary="One liner.",
            position=0,
        ),
        make_chapter(
            novel_id=novel_id,
            title="Middle",
            content="Middle prose.",
            summary="Two liner.",
            position=1,
        ),
        make_chapter(
            novel_id=novel_id,
            title="Last",
            content="Last prose.",
            summary="Three liner.",
            position=2,
        ),
    ]
    fake_repo.seed(*chapters)
    return chapters


class TestGetPlanContextNeighbors:
    async def test_middle_chapter_returns_position_adjacent_neighbors(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        chapters = _seed_three_chapters(fake_repo, novel_id)

        result = await service.get_plan_context(chapters[1].id, novel_id, user_id)

        assert result.chapter.title == "Middle"
        assert result.chapter.summary == "Two liner."
        assert result.previous is not None
        assert (result.previous.title, result.previous.summary) == ("First", "One liner.")
        assert result.next is not None
        assert (result.next.title, result.next.summary) == ("Last", "Three liner.")

    async def test_first_chapter_previous_is_none(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        chapters = _seed_three_chapters(fake_repo, novel_id)

        result = await service.get_plan_context(chapters[0].id, novel_id, user_id)

        assert result.previous is None
        assert result.next is not None
        assert result.next.title == "Middle"

    async def test_last_chapter_next_is_none(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        chapters = _seed_three_chapters(fake_repo, novel_id)

        result = await service.get_plan_context(chapters[2].id, novel_id, user_id)

        assert result.previous is not None
        assert result.previous.title == "Middle"
        assert result.next is None

    async def test_single_chapter_has_no_neighbors(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        only = make_chapter(novel_id=novel_id, title="Only", summary="S.", position=0)
        fake_repo.seed(only)

        result = await service.get_plan_context(only.id, novel_id, user_id)

        assert result.previous is None
        assert result.next is None
        assert result.chapter.title == "Only"


class TestGetPlanContextErrors:
    async def test_unknown_chapter_raises_not_found(
        self,
        service: ChapterService,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.get_plan_context(uuid.uuid4(), novel_id, user_id)

    async def test_chapter_of_other_novel_raises_not_found(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        foreign_chapter = make_chapter(novel_id=uuid.uuid4(), title="Elsewhere", position=0)
        fake_repo.seed(foreign_chapter)

        with pytest.raises(NotFoundError):
            await service.get_plan_context(foreign_chapter.id, novel_id, user_id)


class TestGetPlanContextShape:
    async def test_response_never_carries_content(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_novel(fake_novel_service)
        chapters = _seed_three_chapters(fake_repo, novel_id)

        result = await service.get_plan_context(chapters[1].id, novel_id, user_id)

        dumped = result.model_dump()
        assert set(dumped) == {"chapter", "previous", "next"}
        for part in (dumped["chapter"], dumped["previous"], dumped["next"]):
            assert set(part) == {"title", "summary"}
            assert "content" not in part
