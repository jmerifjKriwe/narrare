"""Unit tests for ChapterService — volume filtering and default volume assignment."""

from __future__ import annotations

import uuid

import pytest

from narrare.chapters.schemas import CreateChapterRequest
from narrare.chapters.service import ChapterService
from tests.factories import make_chapter, make_novel, make_volume
from tests.fakes import FakeChapterRepository, FakeNovelService, FakeVolumeRepository


@pytest.fixture
def fake_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def fake_volume_repo() -> FakeVolumeRepository:
    return FakeVolumeRepository()


@pytest.fixture
def service_with_volumes(
    fake_repo: FakeChapterRepository,
    fake_novel_service: FakeNovelService,
    fake_volume_repo: FakeVolumeRepository,
) -> ChapterService:
    return ChapterService(
        repo=fake_repo, novel_service=fake_novel_service, volume_repo=fake_volume_repo
    )


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
# Chapter list filtered by volume_id
# ---------------------------------------------------------------------------


class TestChapterServiceListByVolume:
    """Test ChapterService.list_chapters() with volume_id filter."""

    async def test_list_with_volume_id_passes_filter_to_repo(
        self,
        service_with_volumes: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        vol_id = uuid.uuid4()
        ch1 = make_chapter(novel_id=novel_id, volume_id=vol_id)
        ch2 = make_chapter(novel_id=novel_id, volume_id=None)
        fake_repo.seed(ch1, ch2)

        result = await service_with_volumes.list_chapters(novel_id, user_id, volume_id=vol_id)
        assert len(result) == 1
        assert result[0].volume_id == vol_id

    async def test_list_with_volume_id_none_returns_all(
        self,
        service_with_volumes: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        vol_id = uuid.uuid4()
        ch1 = make_chapter(novel_id=novel_id, volume_id=vol_id)
        ch2 = make_chapter(novel_id=novel_id, volume_id=None)
        fake_repo.seed(ch1, ch2)

        result = await service_with_volumes.list_chapters(novel_id, user_id, volume_id=None)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Chapter creation defaults to default volume
# ---------------------------------------------------------------------------


class TestChapterServiceCreateDefaultVolume:
    """Test ChapterService.create() defaults volume_id to the novel's default volume."""

    async def test_create_defaults_to_default_volume_when_volume_id_is_none(
        self,
        service_with_volumes: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
        fake_volume_repo: FakeVolumeRepository,
    ) -> None:
        """When request.volume_id is None and volume_repo has a default volume,
        the chapter should be created with the default volume's ID."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        default_vol = make_volume(novel_id=novel_id, is_default=True)
        fake_volume_repo.seed(default_vol)

        request = CreateChapterRequest(title="Auto Volume Chapter", content="text")
        result = await service_with_volumes.create(novel_id, user_id, request)

        assert result.volume_id == default_vol.id

    async def test_create_uses_explicit_volume_id_when_set(
        self,
        service_with_volumes: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
        fake_volume_repo: FakeVolumeRepository,
    ) -> None:
        """When request.volume_id is explicitly set, use that ID."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        explicit_vol_id = uuid.uuid4()

        request = CreateChapterRequest(
            title="Explicit Volume Chapter", content="text", volume_id=explicit_vol_id
        )
        result = await service_with_volumes.create(novel_id, user_id, request)

        assert result.volume_id == explicit_vol_id

    async def test_create_without_volume_repo_uses_none(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """When volume_repo is None, chapter is created with volume_id=None (backward compat)."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        service = ChapterService(repo=fake_repo, novel_service=fake_novel_service, volume_repo=None)

        request = CreateChapterRequest(title="No Volume Repo", content="text")
        result = await service.create(novel_id, user_id, request)

        assert result.volume_id is None

    async def test_create_keeps_none_when_no_default_volume(
        self,
        service_with_volumes: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
        fake_volume_repo: FakeVolumeRepository,
    ) -> None:
        """When volume_repo has no default volume, chapter gets volume_id=None."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        # Don't seed any volumes — get_default_volume returns None

        request = CreateChapterRequest(title="No Default Vol", content="text")
        result = await service_with_volumes.create(novel_id, user_id, request)

        assert result.volume_id is None
        fake_volume_repo.assert_called("get_default_volume", novel_id=novel_id)
