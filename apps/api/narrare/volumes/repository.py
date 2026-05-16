"""Volume repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare._app.base_repository import BaseRepository
from narrare.volumes.models import Volume

if TYPE_CHECKING:
    import uuid

    from narrare.volumes.schemas import UpdateVolumeRequest


class VolumeRepository(BaseRepository):
    async def get_by_id(self, volume_id: uuid.UUID, novel_id: uuid.UUID) -> Volume | None:
        result = await self._session.execute(
            select(Volume).where(Volume.id == volume_id, Volume.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Volume]:
        result = await self._session.execute(
            select(Volume).where(Volume.novel_id == novel_id).order_by(Volume.position)
        )
        return list(result.scalars())

    async def max_position(self, novel_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(Volume.position)).where(Volume.novel_id == novel_id)
        )
        return result.scalar_one_or_none() or -1

    async def create(self, novel_id: uuid.UUID, title: str, position: int) -> Volume:
        volume = Volume(novel_id=novel_id, title=title, position=position)
        self._session.add(volume)
        await self._flush_and_refresh(volume)
        return volume

    async def update(self, volume: Volume, request: UpdateVolumeRequest) -> Volume:
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(volume, field, value)
        await self._flush_and_refresh(volume)
        return volume

    async def delete(self, volume: Volume) -> None:
        await self._session.delete(volume)
        await self._flush()
