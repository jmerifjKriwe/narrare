"""Protocols for Series domain (RULE-03: contracts before implementation).

Two protocols cover CRUD + settings: ``SeriesRepositoryProtocol`` (DB-query
surface) and ``SeriesServiceProtocol`` (business logic). Implemented by
Tasks 3.3 and 3.4. The Policy alpha join-flow Protocol
(``SeriesJoinServiceProtocol``) lives in ``join_contracts.py`` — extracted to
respect the 200-line contracts file-size limit (RULE-04), mirroring the
``kb/scope_contracts.py`` extraction. Implemented by Task 3.5.

Schema types (``SeriesCreateRequest`` etc.) are imported under
``TYPE_CHECKING`` only — they live in ``schemas.py`` (Task 3.2) and are
not needed at runtime for Protocol structural checks.

Ownership contract (C1 / IDOR fix — mirrors ``KBCanonService._verify_series_ownership``
in ``kb/canon_service.py``): every ownership-relevant method takes ``user_id``
and verifies the caller owns the resource BEFORE any read/mutation. A *missing*
series and a *not-owned* series BOTH surface as ``ForbiddenError`` (HTTP 403) —
never ``NotFoundError`` (404) — so series ids are not enumerable
(anti-enumeration). The private ``_verify_series_ownership(series_id, user_id)``
helper is an implementation detail of the concrete service; these Protocols
carry the *semantic* contract that ownership is enforced and ``ForbiddenError``
is the documented outcome.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.schemas import (
        SeriesCreateRequest,
        SeriesResponse,
        SeriesSettingsResponse,
        SeriesSettingsUpdateRequest,
        SeriesSummary,
        SeriesUpdateRequest,
    )
    from narrare_core.series.schemas import NovelRow, Series, SeriesSettings


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

    async def delete_canon_for_series(self, series_id: uuid.UUID) -> int:
        """Bulk-delete Canon KB rows for a series (the Canon fate; ADR-075).

        ``DELETE FROM kb_entries WHERE novel_id IS NULL AND series_id=:s``.
        Canon rows have no home without their series, so a series delete removes
        them in the same transaction (C2). Returns the number of rows deleted.
        """
        ...

    async def list_novels(self, series_id: uuid.UUID) -> list[NovelRow]:
        """Novels in series ordered by ``series_position`` (Core ``NovelRow``).

        Returns Core value objects (not ORM ``Novel``) so the protocol stays
        decoupled from the ORM model and the return type is typed, not ``Any``
        (RULE-09 / I-A2 fix). The concrete repository maps ORM rows → ``NovelRow``
        (analogous to ``KBScopeRepository`` mapping into ``SeriesKBEntry``).
        """
        ...

    async def count_novels(self, series_id: uuid.UUID) -> int:
        """Count novels in a series via ``SELECT COUNT(*)`` (I-B3 N+1 fix)."""
        ...

    async def count_novels_per_series(self, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """``GROUP BY series_id`` novel counts for every series of ``user_id``.

        A single aggregate query for the whole list path (I-B3): series with no
        novels are absent from the map (callers default to 0). Used by
        ``list_series`` to avoid an N+1 (one ``count_novels`` per series).
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
    """Business-logic surface for Series CRUD (delegates DB to repository).

    Ownership contract (C1 fix — see module docstring): every ownership-relevant
    method takes ``user_id`` and verifies series ownership first, raising
    ``ForbiddenError`` (403, anti-enumeration) on a missing or not-owned series.
    """

    async def create_series(
        self, user_id: uuid.UUID, request: SeriesCreateRequest
    ) -> SeriesResponse: ...

    async def get_series(self, series_id: uuid.UUID, user_id: uuid.UUID) -> SeriesResponse:
        """Load a series. Raises ``ForbiddenError`` if missing or not owned."""
        ...

    async def list_series(self, user_id: uuid.UUID) -> list[SeriesSummary]: ...

    async def update_series(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SeriesUpdateRequest,
    ) -> SeriesResponse:
        """Patch a series (status transitions enforced).

        Raises:
            ForbiddenError: Series missing or not owned by ``user_id``.
            ConflictError: Non-adjacent status move (HTTP 409).
        """
        ...

    async def delete_series(self, series_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a series + its Canon KB rows (the Canon fate; ADR-075 §D6).

        Member novels become standalones (``novels.series_id`` SET NULL) and
        their Novel-Overlay KB rows survive as standalone-novel entries
        (``kb_entries.series_id`` is SET NULL — overlays never persist it
        post-D6). Raises ``ForbiddenError`` if the series is missing/not owned.
        """
        ...

    # -- novels in series + settings ------------------------------------

    async def list_novels(self, series_id: uuid.UUID, user_id: uuid.UUID) -> list[NovelRow]:
        """List a series' novels ordered by ``series_position`` (Core read-model).

        Raises ``ForbiddenError`` if the series is missing or not owned.
        """
        ...

    async def reorder_novels(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        novel_ids: list[uuid.UUID],
    ) -> None:
        """Reassign sequential positions; raises ``ForbiddenError`` if not owned."""
        ...

    async def get_settings(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesSettingsResponse:
        """Get settings; raises ``ForbiddenError`` if the series is not owned."""
        ...

    async def update_settings(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SeriesSettingsUpdateRequest,
    ) -> SeriesSettingsResponse:
        """Patch settings; raises ``ForbiddenError`` if the series is not owned."""
        ...
