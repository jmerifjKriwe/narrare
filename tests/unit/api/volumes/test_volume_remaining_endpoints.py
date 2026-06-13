"""Unit tests for VolumeService — remaining router endpoints.

Covers router.py lines 85-86 (get_volume_stats), 97-98 (update_volume),
and 108 (delete_volume) via direct function calls with Fake dependencies.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from tests.factories import make_novel, make_volume
from tests.fakes import FakeNovelService, FakeVolumeRepository

from narrare.volumes.router import delete_volume, get_volume_stats, update_volume
from narrare.volumes.schemas import UpdateVolumeRequest, VolumeResponse, VolumeStatsResponse
from narrare.volumes.service import VolumeService


class TestGetVolumeStatsEndpoint:
    """Direct-call unit test for the get_volume_stats router endpoint."""

    async def test_get_volume_stats_returns_stats_response(self) -> None:
        """Calling get_volume_stats directly should return a VolumeStatsResponse."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        volume = make_volume(
            novel_id=novel_id,
            title="Stats Volume",
            is_default=False,
            created_at=datetime.now(UTC),
        )
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        fake_repo.seed(volume)

        result = await get_volume_stats(
            novel_id=novel_id,
            volume_id=volume.id,
            user_id=str(user_id),
            service=service,
        )

        assert isinstance(result, VolumeStatsResponse)
        assert result.word_count >= 0
        assert result.chapter_count >= 0


class TestUpdateVolumeEndpoint:
    """Direct-call unit test for the update_volume router endpoint."""

    async def test_update_volume_returns_validated_response(self) -> None:
        """Calling update_volume directly should return a VolumeResponse."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        volume = make_volume(
            novel_id=novel_id,
            title="Original Title",
            is_default=False,
            created_at=datetime.now(UTC),
        )
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        fake_repo.seed(volume)

        result = await update_volume(
            novel_id=novel_id,
            volume_id=volume.id,
            request=UpdateVolumeRequest(title="Updated Title"),
            user_id=str(user_id),
            service=service,
        )

        assert isinstance(result, VolumeResponse)
        assert result.title == "Updated Title"
        assert result.id == volume.id


class TestDeleteVolumeEndpoint:
    """Direct-call unit test for the delete_volume router endpoint."""

    async def test_delete_volume_returns_none(self) -> None:
        """Calling delete_volume directly should complete without error."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        volume = make_volume(
            novel_id=novel_id,
            title="Delete Me",
            is_default=False,
            created_at=datetime.now(UTC),
        )
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        fake_repo.seed(volume)

        result = await delete_volume(
            novel_id=novel_id,
            volume_id=volume.id,
            user_id=str(user_id),
            service=service,
        )

        assert result is None
