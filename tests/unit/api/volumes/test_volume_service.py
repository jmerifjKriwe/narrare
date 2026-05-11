"""Unit tests for volumes/service.py — business logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from narrare.volumes.models import Volume
from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest
from narrare.volumes.service import VolumeService


def _make_volume(**kwargs: object) -> Volume:
    from sqlalchemy.orm.attributes import set_attribute

    volume = Volume()
    set_attribute(volume, "id", kwargs.get("id", uuid.uuid4()))
    set_attribute(volume, "novel_id", kwargs.get("novel_id", uuid.uuid4()))
    set_attribute(volume, "title", kwargs.get("title", "Test Volume"))
    set_attribute(volume, "position", kwargs.get("position", 0))
    return volume


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_session: MagicMock) -> VolumeService:
    svc = VolumeService(mock_session)
    # Mock the novel service ownership check
    svc._novel_service.get = AsyncMock(return_value=MagicMock())  # type: ignore[reportPrivateUsage]
    return svc


class TestVolumeServiceGet:
    async def test_returns_volume_when_found(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volume = _make_volume(novel_id=novel_id)
        service._repo.get_by_id = AsyncMock(return_value=volume)  # type: ignore[reportPrivateUsage]

        result = await service.get(volume.id, novel_id, uuid.uuid4())

        assert result == volume

    async def test_raises_404_when_not_found(self, service: VolumeService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404


class TestVolumeServiceList:
    async def test_returns_volumes_for_novel(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volumes = [_make_volume(novel_id=novel_id), _make_volume(novel_id=novel_id)]
        service._repo.list_by_novel = AsyncMock(return_value=volumes)  # type: ignore[reportPrivateUsage]

        result = await service.list_volumes(novel_id, uuid.uuid4())

        assert len(result) == 2


class TestVolumeServiceCreate:
    async def test_creates_volume_at_next_position(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volume = _make_volume(novel_id=novel_id, position=2)
        service._repo.max_position = AsyncMock(return_value=1)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=volume)  # type: ignore[reportPrivateUsage]

        result = await service.create(novel_id, uuid.uuid4(), CreateVolumeRequest(title="Book 2"))

        assert result == volume
        service._repo.create.assert_called_once_with(novel_id, "Book 2", 2)  # type: ignore[reportPrivateUsage]

    async def test_creates_first_volume_at_position_0(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volume = _make_volume(novel_id=novel_id, position=0)
        service._repo.max_position = AsyncMock(return_value=-1)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=volume)  # type: ignore[reportPrivateUsage]

        await service.create(novel_id, uuid.uuid4(), CreateVolumeRequest(title="Book 1"))

        service._repo.create.assert_called_once_with(novel_id, "Book 1", 0)  # type: ignore[reportPrivateUsage]


class TestVolumeServiceUpdate:
    async def test_updates_volume_title(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volume = _make_volume(novel_id=novel_id, title="Old Title")
        updated = _make_volume(id=volume.id, novel_id=novel_id, title="New Title")
        service._repo.get_by_id = AsyncMock(return_value=volume)  # type: ignore[reportPrivateUsage]
        service._repo.update = AsyncMock(return_value=updated)  # type: ignore[reportPrivateUsage]

        result = await service.update(
            volume.id, novel_id, uuid.uuid4(), UpdateVolumeRequest(title="New Title")
        )

        assert result.title == "New Title"

    async def test_update_raises_404_when_not_found(self, service: VolumeService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.update(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), UpdateVolumeRequest())
        assert exc.value.status_code == 404


class TestVolumeServiceDelete:
    async def test_deletes_existing_volume(self, service: VolumeService) -> None:
        novel_id = uuid.uuid4()
        volume = _make_volume(novel_id=novel_id)
        service._repo.get_by_id = AsyncMock(return_value=volume)  # type: ignore[reportPrivateUsage]
        service._repo.delete = AsyncMock()  # type: ignore[reportPrivateUsage]

        await service.delete(volume.id, novel_id, uuid.uuid4())

        service._repo.delete.assert_called_once_with(volume)  # type: ignore[reportPrivateUsage]

    async def test_delete_raises_404_when_not_found(self, service: VolumeService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404
