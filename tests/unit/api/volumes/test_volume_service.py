"""Unit tests for volumes/service.py — business logic with Fake classes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from tests.factories import make_novel, make_volume
from tests.fakes import FakeNovelService, FakeVolumeRepository

from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest
from narrare.volumes.service import VolumeService


@pytest.fixture
def fake_repo() -> FakeVolumeRepository:
    return FakeVolumeRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def service(fake_repo: FakeVolumeRepository, fake_novel_service: FakeNovelService) -> VolumeService:
    svc = VolumeService.__new__(VolumeService)
    svc._repo = fake_repo
    svc._novel_service = fake_novel_service
    return svc


def _seed_ownership(
    service: VolumeService,
    novel_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a novel into the fake novel service for ownership checks."""
    novel_id = novel_id or uuid.uuid4()
    user_id = user_id or uuid.uuid4()
    novel = make_novel(id=novel_id, user_id=user_id)
    service._novel_service.seed(novel)  # type: ignore[attr-defined]
    return novel_id, user_id


class TestVolumeServiceGet:
    async def test_returns_volume_when_found(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)
        volume = make_volume(novel_id=novel_id)
        service._repo.seed(volume)  # type: ignore[attr-defined]

        result = await service.get(volume.id, novel_id, user_id)
        assert result == volume

    async def test_raises_404_when_not_found(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404


class TestVolumeServiceList:
    async def test_returns_volumes_for_novel(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)
        volumes = [make_volume(novel_id=novel_id), make_volume(novel_id=novel_id)]
        service._repo.seed(*volumes)  # type: ignore[attr-defined]

        result = await service.list_volumes(novel_id, user_id)
        assert len(result) == 2


class TestVolumeServiceCreate:
    async def test_creates_volume_at_next_position(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)
        existing = make_volume(novel_id=novel_id, position=1)
        service._repo.seed(existing)  # type: ignore[attr-defined]

        result = await service.create(novel_id, user_id, CreateVolumeRequest(title="Book 2"))

        assert result.title == "Book 2"
        assert result.position == 2

    async def test_creates_first_volume_at_position_0(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)

        result = await service.create(novel_id, user_id, CreateVolumeRequest(title="Book 1"))

        assert result.position == 0
        assert result.title == "Book 1"


class TestVolumeServiceUpdate:
    async def test_updates_volume_title(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)
        volume = make_volume(novel_id=novel_id, title="Old Title")
        service._repo.seed(volume)  # type: ignore[attr-defined]

        result = await service.update(
            volume.id, novel_id, user_id, UpdateVolumeRequest(title="New Title")
        )
        assert result.title == "New Title"

    async def test_update_raises_404_when_not_found(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)

        with pytest.raises(HTTPException) as exc:
            await service.update(uuid.uuid4(), novel_id, user_id, UpdateVolumeRequest())
        assert exc.value.status_code == 404


class TestVolumeServiceDelete:
    async def test_deletes_existing_volume(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)
        volume = make_volume(novel_id=novel_id)
        service._repo.seed(volume)  # type: ignore[attr-defined]

        await service.delete(volume.id, novel_id, user_id)
        service._repo.assert_called_once("delete")  # type: ignore[attr-defined]

    async def test_delete_raises_404_when_not_found(self, service: VolumeService) -> None:
        novel_id, user_id = _seed_ownership(service)

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404
