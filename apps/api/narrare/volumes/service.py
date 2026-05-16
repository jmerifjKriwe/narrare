"""Volume service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.contracts import NovelServiceProtocol
    from narrare.volumes.contracts import VolumeRepositoryProtocol
    from narrare.volumes.models import Volume
    from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest


class VolumeService:
    def __init__(
        self,
        repo: VolumeRepositoryProtocol,
        novel_service: NovelServiceProtocol,
    ) -> None:
        self._repo = repo
        self._novel_service = novel_service

    async def get(self, volume_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID) -> Volume:
        await self._novel_service.get(novel_id, user_id)
        volume = await self._repo.get_by_id(volume_id, novel_id)
        if not volume:
            raise NotFoundError("Volume", identifier=str(volume_id))
        return volume

    async def list_volumes(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> list[Volume]:
        await self._novel_service.get(novel_id, user_id)
        return await self._repo.list_by_novel(novel_id)

    async def create(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: CreateVolumeRequest
    ) -> Volume:
        await self._novel_service.get(novel_id, user_id)
        position = (await self._repo.max_position(novel_id)) + 1
        return await self._repo.create(novel_id, request.title, position)

    async def update(
        self,
        volume_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateVolumeRequest,
    ) -> Volume:
        volume = await self.get(volume_id, novel_id, user_id)
        return await self._repo.update(volume, request)

    async def delete(self, volume_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        volume = await self.get(volume_id, novel_id, user_id)
        await self._repo.delete(volume)
