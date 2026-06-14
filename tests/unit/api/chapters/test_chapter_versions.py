"""Unit tests for ChapterService — list_versions, restore_version."""

from __future__ import annotations

import uuid

import pytest

from narrare.chapters.service import ChapterService
from narrare_core.shared.errors import NotFoundError
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
# list_versions
# ---------------------------------------------------------------------------


class TestChapterServiceListVersions:
    async def test_list_versions_returns_empty_when_no_versions(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        result = await service.list_versions(chapter.id, novel_id, user_id)

        assert result == []

    async def test_list_versions_returns_versions_newest_first(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        await fake_repo.save_version(chapter, 1, source="autosave")
        await fake_repo.save_version(chapter, 2, source="manual")

        result = await service.list_versions(chapter.id, novel_id, user_id)

        assert len(result) == 2
        # Newest first
        assert result[0].version_number == 2
        assert result[1].version_number == 1


# ---------------------------------------------------------------------------
# restore_version
# ---------------------------------------------------------------------------


class TestChapterServiceRestoreVersion:
    async def test_restore_version_restores_content(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, content="original content", word_count=2)
        fake_repo.seed(chapter)

        # Save version 1 capturing "original content"
        version = await fake_repo.save_version(chapter, 1, source="autosave")
        # Change chapter content (simulating later edits)
        await fake_repo.update_content(chapter, "new content", 2)

        result = await service.restore_version(chapter.id, version.id, novel_id, user_id)

        # Content restored from version
        assert result.content == "original content"
        fake_repo.assert_called("update_content")

    async def test_restore_version_raises_404_when_version_not_found(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        with pytest.raises(NotFoundError):
            await service.restore_version(chapter.id, uuid.uuid4(), novel_id, user_id)

    async def test_restore_version_raises_404_when_chapter_not_found(
        self,
        service: ChapterService,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.restore_version(uuid.uuid4(), uuid.uuid4(), novel_id, user_id)
