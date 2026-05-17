"""Volume contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from narrare.volumes.models import Volume
    from narrare.volumes.schemas import UpdateVolumeRequest


@runtime_checkable
class VolumeRepositoryProtocol(Protocol):
    async def get_by_id(self, volume_id: uuid.UUID, novel_id: uuid.UUID) -> Volume | None: ...
    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Volume]: ...
    async def create(
        self,
        novel_id: uuid.UUID,
        title: str,
        position: int,
        *,
        is_default: bool = False,
    ) -> Volume: ...
    async def max_position(self, novel_id: uuid.UUID) -> int: ...
    async def update(self, volume: Volume, request: UpdateVolumeRequest) -> Volume: ...
    async def delete(self, volume: Volume) -> None: ...
    async def get_default_volume(self, novel_id: uuid.UUID) -> Volume | None: ...
    async def get_stats(self, volume_id: uuid.UUID) -> dict[str, Any]: ...
    async def reorder(self, novel_id: uuid.UUID, volume_ids: list[uuid.UUID]) -> list[Volume]: ...
