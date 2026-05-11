"""Unit tests for chapters/service.py — business logic with Fake classes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from narrare.chapters.schemas import (
    CreateChapterRequest,
    UpdateChapterContentRequest,
    UpdateChapterMetaRequest,
)
from narrare.chapters.service import ChapterService
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

        with pytest.raises(HTTPException) as exc:
            await service.update_content(
                chapter.id,
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="x" * 100_001),
            )
        assert exc.value.status_code == 413

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

        with pytest.raises(HTTPException) as exc:
            await service.update_content(
                uuid.uuid4(),
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="content"),
            )
        assert exc.value.status_code == 404


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

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404


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


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestChapterServiceCreate:
    async def test_create_with_explicit_position(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        request = CreateChapterRequest(title="New Chapter", content="hello", position=5)
        result = await service.create(novel_id, user_id, request)

        assert result.title == "New Chapter"
        assert result.position == 5
        fake_repo.assert_called_once("create")

    async def test_create_appends_at_end_when_no_position(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        existing = make_chapter(novel_id=novel_id, position=2)
        fake_repo.seed(existing)

        request = CreateChapterRequest(title="Appended", content="text")
        result = await service.create(novel_id, user_id, request)

        assert result.position == 3  # max_position(2) + 1


# ---------------------------------------------------------------------------
# update_meta
# ---------------------------------------------------------------------------


class TestChapterServiceUpdateMeta:
    async def test_update_meta_modifies_chapter(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, title="Old Title")
        fake_repo.seed(chapter)

        import uuid as _uuid

        UpdateChapterMetaRequest.model_rebuild(_types_namespace={"uuid": _uuid})

        result = await service.update_meta(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterMetaRequest(title="New Title"),
        )
        assert result.title == "New Title"


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


class TestChapterServiceReorder:
    async def test_reorder_calls_repo(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        ch1 = make_chapter(novel_id=novel_id)
        ch2 = make_chapter(novel_id=novel_id)
        fake_repo.seed(ch1, ch2)

        result = await service.reorder(novel_id, user_id, [ch1.id, ch2.id])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestChapterServiceDelete:
    async def test_delete_removes_chapter(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        await service.delete(chapter.id, novel_id, user_id)
        fake_repo.assert_called_once("delete")

    async def test_delete_raises_404_when_not_found(
        self, service: ChapterService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404
