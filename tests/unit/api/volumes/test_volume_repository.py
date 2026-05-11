"""Unit tests for volumes/repository.py — DB query layer."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.volumes.models import Volume
from narrare.volumes.repository import VolumeRepository
from narrare.volumes.schemas import UpdateVolumeRequest


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
def repo(mock_session: MagicMock) -> VolumeRepository:
    return VolumeRepository(mock_session)


class TestVolumeRepositoryGetById:
    async def test_returns_volume_when_found(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        volume = _make_volume()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = volume
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(volume.id, volume.novel_id)

        assert result == volume

    async def test_returns_none_when_not_found(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid.uuid4(), uuid.uuid4())

        assert result is None


class TestVolumeRepositoryListByNovel:
    async def test_returns_volumes_ordered_by_position(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        volumes = [_make_volume(position=0), _make_volume(position=1)]
        mock_result = MagicMock()
        mock_result.scalars.return_value = volumes
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_novel(uuid.uuid4())

        assert len(result) == 2

    async def test_returns_empty_list(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_novel(uuid.uuid4())

        assert result == []


class TestVolumeRepositoryMaxPosition:
    async def test_returns_max_position(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 3
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.max_position(uuid.uuid4())

        assert result == 3

    async def test_returns_negative_one_when_no_volumes(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.max_position(uuid.uuid4())

        assert result == -1


class TestVolumeRepositoryCreate:
    async def test_creates_volume_and_flushes(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        novel_id = uuid.uuid4()
        result = await repo.create(novel_id, "Book One", 0)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.title == "Book One"
        assert result.position == 0
        assert result.novel_id == novel_id


class TestVolumeRepositoryUpdate:
    async def test_updates_provided_fields(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        volume = _make_volume(title="Old")
        mock_session.flush = AsyncMock()

        result = await repo.update(volume, UpdateVolumeRequest(title="New"))

        assert result.title == "New"
        mock_session.flush.assert_called_once()


class TestVolumeRepositoryDelete:
    async def test_deletes_volume_and_flushes(
        self, repo: VolumeRepository, mock_session: MagicMock
    ) -> None:
        volume = _make_volume()
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        await repo.delete(volume)

        mock_session.delete.assert_called_once_with(volume)
        mock_session.flush.assert_called_once()
