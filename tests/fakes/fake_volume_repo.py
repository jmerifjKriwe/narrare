"""Fake volume repository for unit tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from narrare.volumes.models import Volume
from tests.fakes._shared import CallRecord, _apply_setattr

if TYPE_CHECKING:
    from narrare.volumes.schemas import UpdateVolumeRequest


class FakeVolumeRepository:
    """In-memory fake for VolumeRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], Volume] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *volumes: Volume) -> None:
        for v in volumes:
            self._store[(v.id, v.novel_id)] = v

    async def get_by_id(self, volume_id: uuid.UUID, novel_id: uuid.UUID) -> Volume | None:
        self.calls.append(
            CallRecord("get_by_id", kwargs={"volume_id": volume_id, "novel_id": novel_id})
        )
        return self._store.get((volume_id, novel_id))

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Volume]:
        self.calls.append(CallRecord("list_by_novel", kwargs={"novel_id": novel_id}))
        return sorted(
            [v for v in self._store.values() if v.novel_id == novel_id],
            key=lambda v: v.position,
        )

    async def max_position(self, novel_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("max_position", kwargs={"novel_id": novel_id}))
        volumes = [v for v in self._store.values() if v.novel_id == novel_id]
        if not volumes:
            return -1
        return max(v.position for v in volumes)

    async def create(
        self,
        novel_id: uuid.UUID,
        title: str,
        position: int,
        *,
        is_default: bool = False,
    ) -> Volume:
        self.calls.append(
            CallRecord(
                "create",
                kwargs={
                    "novel_id": novel_id,
                    "title": title,
                    "position": position,
                    "is_default": is_default,
                },
            )
        )
        volume = Volume()
        _apply_setattr(
            volume,
            {
                "id": uuid.uuid4(),
                "novel_id": novel_id,
                "title": title,
                "position": position,
                "is_default": is_default,
            },
        )
        self._store[(volume.id, novel_id)] = volume
        return volume

    async def update(self, volume: Volume, request: UpdateVolumeRequest) -> Volume:
        self.calls.append(CallRecord("update"))
        updates = request.model_dump(exclude_none=True)
        _apply_setattr(volume, updates)
        return volume

    async def delete(self, volume: Volume) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop((volume.id, volume.novel_id), None)

    async def get_default_volume(self, novel_id: uuid.UUID) -> Volume | None:
        """Return the default volume for a novel, if any."""
        self.calls.append(CallRecord("get_default_volume", kwargs={"novel_id": novel_id}))
        for v in self._store.values():
            if v.novel_id == novel_id and getattr(v, "is_default", False):
                return v
        return None

    async def get_stats(self, volume_id: uuid.UUID) -> dict[str, Any]:
        """Return aggregated stats for a volume (word_count, chapter_count, word_count_target)."""
        self.calls.append(CallRecord("get_stats", kwargs={"volume_id": volume_id}))
        volume = None
        for v in self._store.values():
            if v.id == volume_id:
                volume = v
                break
        return {
            "word_count": 0,
            "chapter_count": 0,
            "word_count_target": getattr(volume, "word_count_target", None) if volume else None,
        }

    async def reorder(self, novel_id: uuid.UUID, volume_ids: list[uuid.UUID]) -> list[Volume]:
        """Set positions 0..n based on volume_ids order."""
        self.calls.append(
            CallRecord("reorder", kwargs={"novel_id": novel_id, "volume_ids": volume_ids})
        )
        for position, vid in enumerate(volume_ids):
            for key, volume in self._store.items():
                if key[0] == vid and key[1] == novel_id:
                    volume.position = position
        return await self.list_by_novel(novel_id)

    def assert_called_once(self, method: str) -> None:
        count = sum(1 for c in self.calls if c.method == method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")
