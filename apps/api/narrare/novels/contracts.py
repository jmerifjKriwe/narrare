"""Novel service contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.novels.models import Novel
    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


@runtime_checkable
class NovelRepositoryProtocol(Protocol):
    async def get(self, novel_id: uuid.UUID) -> Novel | None:
        """Load a novel by ID without ownership check (system-level access)."""
        ...

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel | None: ...
    async def list_by_user(self, user_id: uuid.UUID) -> list[Novel]: ...
    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel: ...
    async def update(self, novel: Novel, request: UpdateNovelRequest) -> Novel: ...
    async def delete(self, novel: Novel) -> None: ...

    async def update_series_membership(
        self,
        novel_id: uuid.UUID,
        *,
        series_id: uuid.UUID,
        series_position: int,
    ) -> None:
        """Assign a novel to a series at ``series_position`` (join flow).

        Sets ``series_id`` and ``series_position`` on the novel row. Used by
        ``SeriesJoinService.apply_join`` (RULE-06: membership mutation goes
        through the repository, not the session directly).
        """
        ...


@runtime_checkable
class NovelServiceProtocol(Protocol):
    async def get(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel: ...
    async def list_novels(self, user_id: uuid.UUID) -> list[Novel]: ...
    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel: ...
    async def update(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: UpdateNovelRequest
    ) -> Novel: ...
    async def delete(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None: ...
