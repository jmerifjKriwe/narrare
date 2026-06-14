"""Unit tests for VolumeService — router endpoint coverage.

Covers router.py lines 41-42 (list_volumes) and 74-75 (get_volume)
via direct function calls with Fake dependencies.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from tests.factories import make_novel, make_volume
from tests.fakes import FakeNovelService, FakeVolumeRepository

from narrare.volumes.router import create_volume, get_volume, list_volumes
from narrare.volumes.schemas import CreateVolumeRequest, VolumeResponse
from narrare.volumes.service import VolumeService


class TestGetVolumeEndpoint:
    """Direct-call unit test for the get_volume router endpoint."""

    async def test_get_volume_returns_validated_response(self) -> None:
        """Calling get_volume directly should return a VolumeResponse."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        volume = make_volume(
            novel_id=novel_id,
            title="Test Volume",
            is_default=False,
            created_at=datetime.now(UTC),
        )
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        fake_repo.seed(volume)

        result = await get_volume(
            novel_id=novel_id,
            volume_id=volume.id,
            user_id=str(user_id),
            service=service,
        )

        assert isinstance(result, VolumeResponse)
        assert result.id == volume.id
        assert result.title == "Test Volume"
        assert result.novel_id == novel_id


class TestListVolumesEndpoint:
    """Direct-call unit test for the list_volumes router endpoint."""

    async def test_list_volumes_returns_response_list(self) -> None:
        """Calling list_volumes directly should return a list of VolumeResponse."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        v1 = make_volume(
            novel_id=novel_id,
            title="Volume 1",
            is_default=True,
            created_at=datetime.now(UTC),
        )
        v2 = make_volume(
            novel_id=novel_id,
            title="Volume 2",
            is_default=False,
            created_at=datetime.now(UTC),
        )
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        fake_repo.seed(v1, v2)

        result = await list_volumes(
            novel_id=novel_id,
            user_id=str(user_id),
            service=service,
        )

        assert len(result) == 2
        assert all(isinstance(r, VolumeResponse) for r in result)
        titles = {r.title for r in result}
        assert titles == {"Volume 1", "Volume 2"}


class TestCreateVolumeEndpoint:
    """Direct-call unit test for the create_volume router endpoint."""

    async def test_create_volume_returns_validated_response(self) -> None:
        """Calling create_volume directly should return a VolumeResponse."""
        fake_repo = FakeVolumeRepository()
        fake_novel_service = FakeNovelService()
        service = VolumeService(repo=fake_repo, novel_service=fake_novel_service)

        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()
        fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))

        result = await create_volume(
            novel_id=novel_id,
            request=CreateVolumeRequest(title="New Volume"),
            user_id=str(user_id),
            service=service,
        )

        assert isinstance(result, VolumeResponse)
        assert result.title == "New Volume"
        assert result.novel_id == novel_id
