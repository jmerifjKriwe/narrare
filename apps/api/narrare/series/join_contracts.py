"""Series join-flow service contract — Protocol definition (RULE-03).

Extracted from ``contracts.py`` to respect the 200-line contracts file-size
limit (RULE-04), mirroring the ``kb/scope_contracts.py`` extraction. Holds the
*service* Protocol for the Policy alpha join flow (preview/apply/remove); the
repository and CRUD-service Protocols (``SeriesRepositoryProtocol`` /
``SeriesServiceProtocol``) stay in ``contracts.py``. Implemented by Task 3.5.

Schema types (``JoinPreview`` / ``JoinResult``) are imported under
``TYPE_CHECKING`` only — they live in ``schemas.py`` and are not needed at
runtime for Protocol structural checks.

Ownership contract (C1 / IDOR fix — mirrors ``KBCanonService._verify_series_ownership``
in ``kb/canon_service.py``): every method verifies BOTH that the caller owns the
*series* AND the *novel* before any state change — a missing or not-owned
series/novel surfaces as ``ForbiddenError`` (HTTP 403, anti-enumeration — never
``NotFoundError`` / 404). Series ownership uses the injected ``series_repo``;
novel ownership uses ``novel_repo.get_by_id(novel_id, user_id)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.schemas import JoinPreview, JoinResult
    from narrare_core.series.schemas import Series


@runtime_checkable
class SeriesJoinRepositoryProtocol(Protocol):
    """Focused series-repo surface consumed by the join flow (Interface Segregation).

    The join flow uses only two series-repo operations: ``get`` (to verify
    series ownership — anti-enumeration 403) and ``detach_overlay_series_id``
    (to detach a leaving novel's overlay KB rows, T7/D6). Kept as a focused
    Protocol (not the full ``SeriesRepositoryProtocol``) so the join service
    depends only on what it uses, and lives here — not in ``contracts.py`` — so
    ``contracts.py`` stays under its 200-line hard limit (RULE-04). The concrete
    ``SeriesRepository`` satisfies this structurally.
    """

    async def get(self, series_id: uuid.UUID) -> Series | None:
        """Load a single Series by ID (no ownership check)."""
        ...

    async def detach_overlay_series_id(self, novel_id: uuid.UUID, series_id: uuid.UUID) -> int:
        """Clear ``series_id`` on the leaving novel's overlay KB rows (T7/D6).

        ``UPDATE kb_entries SET series_id=NULL WHERE novel_id=:n AND series_id=:s``.
        Usually a no-op post-D6 (overlays never persist ``series_id``); defence-
        in-depth for legacy rows. Returns the number of rows updated.
        """
        ...


@runtime_checkable
class SeriesJoinServiceProtocol(Protocol):
    """Policy alpha: adaptive scope assignment on join (preview-then-apply).

    Ownership contract (C1 fix): every method verifies BOTH that the caller owns
    the *series* AND the *novel* before any state change — a missing or not-owned
    series/novel surfaces as ``ForbiddenError`` (403, anti-enumeration). Series
    ownership uses the injected ``series_repo`` (no longer dead weight); novel
    ownership uses ``novel_repo.get_by_id(novel_id, user_id)``.
    """

    async def preview_join(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JoinPreview:
        """Compute per-entry treatments without mutating state.

        Raises:
            ForbiddenError: Series or novel missing / not owned by ``user_id``.
            ConflictError: Novel already in another series (HTTP 409).
        """
        ...

    async def apply_join(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        position: int,
        user_id: uuid.UUID,
    ) -> JoinResult:
        """Execute the previewed treatments atomically (commit/rollback).

        Raises:
            ForbiddenError: Series or novel missing / not owned by ``user_id``.
            ConflictError: Novel already in another series (HTTP 409).
        """
        ...

    async def remove_novel(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Remove a novel from a series (inverse of :meth:`apply_join`).

        Clears novel membership (→ standalone) and detaches the novel's KB
        ``series_id`` (per ADR-075 §D6 overlays never persist ``series_id``, so
        the detach is a no-op on KB rows — the novel row's ``series_id`` SET-NULL
        is the operative change). Raises ``ForbiddenError`` if the series or
        novel is missing / not owned.
        """
        ...
