"""Protocols for Series domain (RULE-03: contracts before implementation).

Three protocols cover CRUD + settings (repository/service) and the
Policy alpha join flow (preview/apply). Implemented by Tasks 3.3, 3.4, 3.5.

Schema types (``SeriesCreateRequest`` etc.) are imported under
``TYPE_CHECKING`` only — they live in ``schemas.py`` (Task 3.2) and are
not needed at runtime for Protocol structural checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.schemas import (
        JoinPreview,
        JoinResult,
        SeriesCreateRequest,
        SeriesResponse,
        SeriesSummary,
        SeriesUpdateRequest,
    )
    from narrare_core.series.schemas import Series, SeriesSettings


@runtime_checkable
class SeriesRepositoryProtocol(Protocol):
    """DB-query surface for Series + SeriesSettings + novels-in-series."""

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        subtitle: str | None,
        description: str | None,
        genre: str | None,
        writing_language: str | None,
        planned_novel_count: int | None,
    ) -> Series:
        """Insert a new Series (status defaults to draft) + empty settings."""
        ...

    async def get(self, series_id: uuid.UUID) -> Series | None:
        """Load a single Series by ID (no ownership check)."""
        ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[Series]:
        """List all Series owned by ``user_id``."""
        ...

    async def update(self, series_id: uuid.UUID, **patch: object) -> Series | None:
        """Patch mutable columns; returns updated Series or None if missing."""
        ...

    async def delete(self, series_id: uuid.UUID) -> bool:
        """Delete a Series; True on success, False if not found."""
        ...

    async def list_novels(self, series_id: uuid.UUID) -> list[Any]:
        """Novels in series ordered by ``series_position`` (NovelRow list).

        Element type is intentionally ``Any`` (not ``Novel``) so the protocol
        stays decoupled from the ORM model and remains compatible with the
        concrete ``list[Novel]`` return (lists are invariant).
        """
        ...

    async def reorder_novels(self, series_id: uuid.UUID, novel_ids: list[uuid.UUID]) -> None:
        """Reassign sequential ``series_position`` (1..N) to given novels."""
        ...

    async def get_settings(self, series_id: uuid.UUID) -> SeriesSettings | None:
        """Load SeriesSettings for a series (None if no row yet)."""
        ...

    async def update_settings(
        self, series_id: uuid.UUID, patch: dict[str, object]
    ) -> SeriesSettings:
        """Patch SeriesSettings columns; creates row on demand if missing."""
        ...


@runtime_checkable
class SeriesServiceProtocol(Protocol):
    """Business-logic surface for Series CRUD (delegates DB to repository)."""

    async def create_series(
        self, user_id: uuid.UUID, request: SeriesCreateRequest
    ) -> SeriesResponse: ...

    async def get_series(self, series_id: uuid.UUID) -> SeriesResponse: ...

    async def list_series(self, user_id: uuid.UUID) -> list[SeriesSummary]: ...

    async def update_series(
        self, series_id: uuid.UUID, request: SeriesUpdateRequest
    ) -> SeriesResponse: ...

    async def delete_series(self, series_id: uuid.UUID) -> None: ...


@runtime_checkable
class SeriesJoinServiceProtocol(Protocol):
    """Policy alpha: adaptive scope assignment on join (preview-then-apply)."""

    async def preview_join(self, series_id: uuid.UUID, novel_id: uuid.UUID) -> JoinPreview:
        """Compute per-entry treatments without mutating state."""
        ...

    async def apply_join(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        position: int,
    ) -> JoinResult:
        """Execute the previewed treatments atomically (commit/rollback)."""
        ...
