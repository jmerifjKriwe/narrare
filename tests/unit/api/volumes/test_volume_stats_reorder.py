"""Unit tests for VolumeService — stats, reorder, default volume protection."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from tests.factories import make_novel, make_volume
from tests.fakes import FakeNovelService, FakeVolumeRepository

from narrare.volumes.service import VolumeService
from narrare_core.shared.errors import ValidationError


@pytest.fixture
def fake_repo() -> FakeVolumeRepository:
    return FakeVolumeRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def service(fake_repo: FakeVolumeRepository, fake_novel_service: FakeNovelService) -> VolumeService:
    return VolumeService(repo=fake_repo, novel_service=fake_novel_service)


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
# Default volume deletion protection
# ---------------------------------------------------------------------------


class TestVolumeServiceDeleteDefaultProtection:
    """Deleting a volume with is_default=True should raise ValidationError."""

    async def test_delete_default_volume_raises_validation_error(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id, is_default=True)
        fake_repo.seed(volume)

        with pytest.raises(ValidationError) as exc:
            await service.delete(volume.id, novel_id, user_id)
        assert "default" in str(exc.value).lower()

    async def test_delete_non_default_volume_succeeds(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id, is_default=False)
        fake_repo.seed(volume)

        await service.delete(volume.id, novel_id, user_id)
        fake_repo.assert_called_once("delete")


# ---------------------------------------------------------------------------
# Volume stats computation
# ---------------------------------------------------------------------------


class TestVolumeServiceGetStats:
    """Test VolumeService.get_stats() — computes completion_percentage."""

    async def test_stats_with_target_returns_completion_percentage(
        self,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """When word_count_target is set, completion_percentage = word_count / target * 100."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id)
        fake_repo.seed(volume)

        async def _fake_stats(vid: uuid.UUID) -> dict[str, Any]:
            return {
                "word_count": 6000,
                "chapter_count": 3,
                "word_count_target": 10000,
            }

        fake_repo.get_stats = _fake_stats  # type: ignore[assignment]
        svc = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        result = await svc.get_stats(volume.id, novel_id, user_id)
        assert result["word_count"] == 6000
        assert result["chapter_count"] == 3
        assert result["word_count_target"] == 10000
        assert result["completion_percentage"] == 60.0

    async def test_stats_with_no_target_returns_none_percentage(
        self,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """When word_count_target is None, completion_percentage should be None."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id)
        fake_repo.seed(volume)

        async def _fake_stats(vid: uuid.UUID) -> dict[str, Any]:
            return {
                "word_count": 6000,
                "chapter_count": 3,
                "word_count_target": None,
            }

        fake_repo.get_stats = _fake_stats  # type: ignore[assignment]
        svc = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        result = await svc.get_stats(volume.id, novel_id, user_id)
        assert result["completion_percentage"] is None

    async def test_stats_empty_volume_returns_zeros(
        self,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Empty volume: word_count=0, chapter_count=0, percentage=None."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id)
        fake_repo.seed(volume)

        async def _fake_stats(vid: uuid.UUID) -> dict[str, Any]:
            return {
                "word_count": 0,
                "chapter_count": 0,
                "word_count_target": None,
            }

        fake_repo.get_stats = _fake_stats  # type: ignore[assignment]
        svc = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        result = await svc.get_stats(volume.id, novel_id, user_id)
        assert result["word_count"] == 0
        assert result["chapter_count"] == 0
        assert result["word_count_target"] is None
        assert result["completion_percentage"] is None


# ---------------------------------------------------------------------------
# Volume reorder validation
# ---------------------------------------------------------------------------


class TestVolumeServiceReorder:
    """Test VolumeService.reorder() — validates all volume IDs are present."""

    async def test_reorder_succeeds_when_all_ids_present(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        v1 = make_volume(novel_id=novel_id, position=0)
        v2 = make_volume(novel_id=novel_id, position=1)
        fake_repo.seed(v1, v2)

        result = await service.reorder(novel_id, user_id, [v2.id, v1.id])

        assert len(result) == 2
        assert result[0].id == v2.id
        assert result[0].position == 0
        assert result[1].id == v1.id
        assert result[1].position == 1

    async def test_reorder_raises_validation_error_when_missing_ids(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        v1 = make_volume(novel_id=novel_id, position=0)
        v2 = make_volume(novel_id=novel_id, position=1)
        fake_repo.seed(v1, v2)

        with pytest.raises(ValidationError) as exc:
            await service.reorder(novel_id, user_id, [v1.id])  # missing v2.id
        assert "missing" in str(exc.value).lower()

    async def test_reorder_raises_validation_error_when_extra_ids(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        v1 = make_volume(novel_id=novel_id, position=0)
        fake_repo.seed(v1)

        with pytest.raises(ValidationError) as exc:
            await service.reorder(novel_id, user_id, [v1.id, uuid.uuid4()])  # extra unknown ID
        assert "extra" in str(exc.value).lower()
