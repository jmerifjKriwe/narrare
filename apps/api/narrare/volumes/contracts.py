"""Volume contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.volumes.models import Volume
    from narrare.volumes.schemas import UpdateVolumeRequest


@runtime_checkable
class VolumeRepositoryProtocol(Protocol):
    async def get_by_id(self, volume_id: uuid.UUID, novel_id: uuid.UUID) -> Volume | None: ...
    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Volume]: ...
    async def create(self, novel_id: uuid.UUID, title: str, position: int) -> Volume: ...
    async def max_position(self, novel_id: uuid.UUID) -> int: ...
    async def update(self, volume: Volume, request: UpdateVolumeRequest) -> Volume: ...
    async def delete(self, volume: Volume) -> None: ...
