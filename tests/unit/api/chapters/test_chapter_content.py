"""Unit tests for ChapterService — update_content, get, list."""

from __future__ import annotations

import uuid

import pytest

from narrare.chapters.schemas import (
    UpdateChapterContentRequest,
)
from narrare.chapters.service import ChapterService
from narrare_core.shared.errors import NotFoundError, ValidationError
from tests.factories import make_chapter, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelService


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


def _seed_ownership(
    fake_novel_service: FakeNovelService,
    novel_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a novel into the fake novel service for ownership checks."""
    novel_id = novel_id or uuid.uuid4()
    user_id = user_id or uuid.uuid4()
    novel = make_novel(id=novel_id, user_id=user_id)
    fake_novel_service.seed(novel)
    return novel_id, user_id


# ---------------------------------------------------------------------------
# update_content
# ---------------------------------------------------------------------------


class TestChapterServiceUpdateContent:
    async def test_raises_413_for_oversized_content(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        with pytest.raises(ValidationError) as exc:
            await service.update_content(
                chapter.id,
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="x" * 100_001),
            )
        assert "character limit" in str(exc.value)

    async def test_computes_word_count_when_not_provided(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        result = await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="five words are in here"),
        )
        assert result.word_count == 5

    async def test_raises_404_when_chapter_not_found(
        self, service: ChapterService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.update_content(
                uuid.uuid4(),
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="content"),
            )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestChapterServiceGet:
    async def test_get_returns_chapter_when_found(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        result = await service.get(chapter.id, novel_id, user_id)
        assert result == chapter

    async def test_get_raises_404_when_not_found(
        self, service: ChapterService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.get(uuid.uuid4(), novel_id, user_id)


# ---------------------------------------------------------------------------
# list_chapters
# ---------------------------------------------------------------------------


class TestChapterServiceList:
    async def test_list_returns_chapters_for_novel(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapters = [make_chapter(novel_id=novel_id), make_chapter(novel_id=novel_id)]
        fake_repo.seed(*chapters)

        result = await service.list_chapters(novel_id, user_id)
        assert len(result) == 2
