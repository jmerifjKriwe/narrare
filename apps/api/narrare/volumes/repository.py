"""Volume repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from narrare._app.base_repository import BaseRepository
from narrare.chapters.models import Chapter
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
        # Explicit None check: `value or -1` would map a legitimate max of 0
        # (falsy) to -1, so every volume would be created with position 0.
        value = result.scalar_one_or_none()
        return -1 if value is None else value

    async def create(
        self,
        novel_id: uuid.UUID,
        title: str,
        position: int,
        *,
        is_default: bool = False,
    ) -> Volume:
        volume = Volume(novel_id=novel_id, title=title, position=position, is_default=is_default)
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

    async def get_default_volume(self, novel_id: uuid.UUID) -> Volume | None:
        """Return the default volume for a novel, if any."""
        result = await self._session.execute(
            select(Volume).where(Volume.novel_id == novel_id, Volume.is_default.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_stats(self, volume_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate chapter stats for a volume.

        Returns dict with keys: word_count, chapter_count, word_count_target.
        """
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Chapter.word_count), 0).label("word_count"),
                func.count(Chapter.id).label("chapter_count"),
            ).where(Chapter.volume_id == volume_id)
        )
        row = result.one()
        # Fetch volume's word_count_target
        vol_result = await self._session.execute(
            select(Volume.word_count_target).where(Volume.id == volume_id)
        )
        target = vol_result.scalar_one_or_none()
        return {
            "word_count": int(row.word_count),
            "chapter_count": int(row.chapter_count),
            "word_count_target": target,
        }

    async def reorder(self, novel_id: uuid.UUID, volume_ids: list[uuid.UUID]) -> list[Volume]:
        """Set positions 0..n based on volume_ids order. Atomic."""
        for position, volume_id in enumerate(volume_ids):
            await self._session.execute(
                update(Volume)
                .where(Volume.id == volume_id, Volume.novel_id == novel_id)
                .values(position=position)
            )
        await self._flush()
        return await self.list_by_novel(novel_id)
