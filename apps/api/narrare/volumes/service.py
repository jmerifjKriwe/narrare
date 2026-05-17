"""Volume service — business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.contracts import NovelServiceProtocol
    from narrare.volumes.contracts import VolumeRepositoryProtocol
    from narrare.volumes.models import Volume
    from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest

logger = structlog.get_logger(__name__)


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
        if volume.is_default:
            raise ValidationError("Cannot delete the default volume")
        await self._repo.delete(volume)
        logger.info("volume_deleted", volume_id=str(volume_id))

    async def get_stats(
        self, volume_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, Any]:
        """Compute aggregated stats for a volume.

        Returns dict with word_count, chapter_count, word_count_target,
        and completion_percentage.
        """
        await self.get(volume_id, novel_id, user_id)  # ownership check
        stats = await self._repo.get_stats(volume_id)
        target = stats["word_count_target"]
        completion: float | None = None
        if target and target > 0:
            completion = round((stats["word_count"] / target) * 100, 1)
        return {
            "word_count": stats["word_count"],
            "chapter_count": stats["chapter_count"],
            "word_count_target": target,
            "completion_percentage": completion,
        }

    async def reorder(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        volume_ids: list[uuid.UUID],
    ) -> list[Volume]:
        """Reorder volumes within a novel.

        Validates that all current volume IDs are present in the new order.
        """
        await self._novel_service.get(novel_id, user_id)
        current_volumes = await self._repo.list_by_novel(novel_id)
        current_ids = {str(v.id) for v in current_volumes}
        provided_ids = {str(vid) for vid in volume_ids}

        if current_ids != provided_ids:
            missing = current_ids - provided_ids
            extra = provided_ids - current_ids
            parts: list[str] = []
            if missing:
                parts.append(f"missing: {missing}")
            if extra:
                parts.append(f"extra: {extra}")
            raise ValidationError(f"Volume ID mismatch — {'; '.join(parts)}")

        volumes = await self._repo.reorder(novel_id, volume_ids)
        logger.info("volumes_reordered", novel_id=str(novel_id), count=len(volumes))
        return volumes
