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


class TestVolumeServiceGet:
    async def test_returns_volume_when_found(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id)
        fake_repo.seed(volume)

        result = await service.get(volume.id, novel_id, user_id)
        assert result == volume

    async def test_raises_404_when_not_found(
        self, service: VolumeService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404


class TestVolumeServiceList:
    async def test_returns_volumes_for_novel(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volumes = [make_volume(novel_id=novel_id), make_volume(novel_id=novel_id)]
        fake_repo.seed(*volumes)

        result = await service.list_volumes(novel_id, user_id)
        assert len(result) == 2


class TestVolumeServiceCreate:
    async def test_creates_volume_at_next_position(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        existing = make_volume(novel_id=novel_id, position=1)
        fake_repo.seed(existing)

        result = await service.create(novel_id, user_id, CreateVolumeRequest(title="Book 2"))

        assert result.title == "Book 2"
        assert result.position == 2

    async def test_creates_first_volume_at_position_0(
        self, service: VolumeService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        result = await service.create(novel_id, user_id, CreateVolumeRequest(title="Book 1"))

        assert result.position == 0
        assert result.title == "Book 1"


class TestVolumeServiceUpdate:
    async def test_updates_volume_title(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id, title="Old Title")
        fake_repo.seed(volume)

        result = await service.update(
            volume.id, novel_id, user_id, UpdateVolumeRequest(title="New Title")
        )
        assert result.title == "New Title"

    async def test_update_raises_404_when_not_found(
        self, service: VolumeService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(HTTPException) as exc:
            await service.update(uuid.uuid4(), novel_id, user_id, UpdateVolumeRequest())
        assert exc.value.status_code == 404


class TestVolumeServiceDelete:
    async def test_deletes_existing_volume(
        self,
        service: VolumeService,
        fake_repo: FakeVolumeRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        volume = make_volume(novel_id=novel_id)
        fake_repo.seed(volume)

        await service.delete(volume.id, novel_id, user_id)
        fake_repo.assert_called_once("delete")

    async def test_delete_raises_404_when_not_found(
        self, service: VolumeService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), novel_id, user_id)
        assert exc.value.status_code == 404
