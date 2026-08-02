"""Series service — CRUD business logic with status-transition enforcement.

Implements ``SeriesServiceProtocol`` (contracts.py). Business logic only:
no DB queries (delegated to ``SeriesRepository``), no HTTP. Converts between
Pydantic request/response schemas and Core ``Series`` types.

Status transitions follow an adjacency matrix — only the allowed
forward/back moves (e.g. draft→active, active→completed) are permitted; a
skip move (e.g. draft→completed) raises ``InvalidStatusTransitionError``.
Setting the status to its current value is a no-op, not a transition.

Patch field filtering (Task 3.3 note): the repository's ``update`` applies
arbitrary kwargs via ``setattr``. ``_build_patch`` whitelists known columns
and uses ``exclude_unset`` so only explicitly-provided fields are forwarded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.series.schemas import SeriesResponse, SeriesSettingsResponse, SeriesSummary
from narrare_core.series.schemas import SeriesSettings
from narrare_core.shared.errors import ConflictError, ForbiddenError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.schemas import (
        SeriesCreateRequest,
        SeriesSettingsUpdateRequest,
        SeriesUpdateRequest,
    )
    from narrare_core.series.schemas import NovelRow, Series, SeriesStatus

logger = structlog.get_logger(__name__)

# Only adjacent status moves are allowed. Same-status "transitions" are
# no-ops and handled before this lookup (never reach the matrix).
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"active"}),
    "active": frozenset({"completed", "draft"}),
    "completed": frozenset({"draft"}),
}

# Columns the service may patch through the repository. ``status`` is added
# back separately in ``_build_patch`` (after transition validation).
_PATCHABLE_FIELDS = frozenset(
    {"title", "subtitle", "description", "genre", "writing_language", "planned_novel_count"}
)


class SeriesNotFoundError(NotFoundError):
    """Raised when a Series is not found."""

    def __init__(self, series_id: uuid.UUID) -> None:
        super().__init__("Series", identifier=str(series_id))
        self.series_id = series_id


class InvalidStatusTransitionError(ConflictError):
    """Raised when a requested Series status transition is not allowed.

    Subclasses :class:`ConflictError` so the app's global ``NarrareError``
    handler (``_app/main.py``) maps it to HTTP 409 (state conflict), mirroring
    :class:`~narrare.series.join_service.NovelAlreadyInSeriesError`.
    """

    def __init__(self, current: SeriesStatus, target: SeriesStatus) -> None:
        super().__init__(f"Cannot transition series status from '{current}' to '{target}'")
        # Preserve the specific code (ConflictError defaults to "CONFLICT").
        self.code = "INVALID_STATUS_TRANSITION"
        self.current_status = current
        self.target_status = target


class SeriesService:
    """Business-logic surface for Series CRUD (delegates DB to repository)."""

    def __init__(self, repo: SeriesRepositoryProtocol) -> None:
        self._repo = repo

    async def create_series(
        self, user_id: uuid.UUID, request: SeriesCreateRequest
    ) -> SeriesResponse:
        """Create a new Series (status defaults to 'draft') and return it."""
        series = await self._repo.create(
            user_id=user_id,
            title=request.title,
            subtitle=request.subtitle,
            description=request.description,
            genre=request.genre,
            writing_language=request.writing_language,
            planned_novel_count=request.planned_novel_count,
        )
        # ``create`` always starts at draft; an explicit non-draft initial
        # status is applied directly (initial state, not a transition).
        if request.status is not None and request.status != series.status:
            updated = await self._repo.update(series.id, status=request.status)
            if updated is not None:
                series = updated
        novel_count = await self._novel_count(series.id)
        logger.info("series_created", series_id=str(series.id), user_id=str(user_id))
        return self._to_response(series, novel_count)

    async def get_series(self, series_id: uuid.UUID, user_id: uuid.UUID) -> SeriesResponse:
        """Get a single Series, verifying ownership.

        Raises:
            ForbiddenError: If the series is missing or not owned by ``user_id``
                (anti-enumeration — never ``NotFoundError`` / 404).
        """
        series = await self._verify_series_ownership(series_id, user_id)
        return self._to_response(series, await self._novel_count(series_id))

    async def list_series(self, user_id: uuid.UUID) -> list[SeriesSummary]:
        """List all Series for a user with computed novel counts.

        Uses a single ``GROUP BY`` aggregate (``count_novels_per_series``) so the
        list path is O(1) queries, not O(N) (I-B3 N+1 fix).
        """
        all_series = await self._repo.list_for_user(user_id)
        counts = await self._repo.count_novels_per_series(user_id)
        return [
            SeriesSummary(
                id=s.id,
                title=s.title,
                subtitle=s.subtitle,
                status=s.status,
                novel_count=counts.get(s.id, 0),
            )
            for s in all_series
        ]

    async def update_series(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SeriesUpdateRequest,
    ) -> SeriesResponse:
        """Update a Series, enforcing status-transition rules.

        Args:
            series_id: The Series to patch.
            user_id: The caller (ownership verified).
            request: PATCH body — only set fields are forwarded.

        Raises:
            ForbiddenError: Series missing or not owned by ``user_id``.
            InvalidStatusTransitionError: If ``status`` requests a non-adjacent
                move (e.g. draft→completed).
        """
        current = await self._verify_series_ownership(series_id, user_id)

        if request.status is not None and request.status != current.status:
            self._validate_transition(current.status, request.status)

        patch = self._build_patch(request)
        updated = await self._repo.update(series_id, **patch) if patch else current
        if updated is None:
            # Race: deleted between ownership check and update — treat as not
            # owned (anti-enumeration: never reveal existence via 404).
            raise ForbiddenError("You do not have access to this series")
        logger.info("series_updated", series_id=str(series_id))
        return self._to_response(updated, await self._novel_count(series_id))

    async def delete_series(self, series_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a Series + its Canon KB rows (the Canon fate; ADR-075 §D6).

        Canon rows (``novel_id IS NULL``) are bulk-deleted in-transaction before
        the series row is removed — Canon has no home without its series (C2).
        Member novels become standalones (``novels.series_id`` SET NULL via the
        FK) and their Novel-Overlay KB rows survive (``kb_entries.series_id`` SET
        NULL via the FK).

        Raises:
            ForbiddenError: Series missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        # Canon fate: remove Canon rows first (they cannot survive the series).
        canon_deleted = await self._repo.delete_canon_for_series(series_id)
        deleted = await self._repo.delete(series_id)
        if not deleted:
            # Race: vanished between ownership check and delete — anti-enumeration.
            raise ForbiddenError("You do not have access to this series")
        logger.info("series_deleted", series_id=str(series_id), canon_deleted=canon_deleted)

    # -- novels in series + settings ------------------------------------

    async def list_novels(self, series_id: uuid.UUID, user_id: uuid.UUID) -> list[NovelRow]:
        """List a series' novels ordered by ``series_position`` (Core read-model).

        Raises:
            ForbiddenError: If the series is missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        return await self._repo.list_novels(series_id)

    async def reorder_novels(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        novel_ids: list[uuid.UUID],
    ) -> None:
        """Reassign sequential 1-based positions to the series' novels.

        Raises:
            ForbiddenError: If the series is missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        await self._repo.reorder_novels(series_id, novel_ids)
        logger.info("series_novels_reordered", series_id=str(series_id))

    async def get_settings(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesSettingsResponse:
        """Get Series settings (synthesises a default if no row exists yet).

        Raises:
            ForbiddenError: If the series is missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        settings = await self._repo.get_settings(series_id)
        if settings is None:
            settings = SeriesSettings(series_id=series_id, author_voice=None)
        return SeriesSettingsResponse.model_validate(settings)

    async def update_settings(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SeriesSettingsUpdateRequest,
    ) -> SeriesSettingsResponse:
        """Patch Series settings (only explicitly-provided fields forward).

        Raises:
            ForbiddenError: If the series is missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        patch = request.model_dump(exclude_unset=True)
        settings = await self._repo.update_settings(series_id, patch)
        return SeriesSettingsResponse.model_validate(settings)

    # -- helpers --------------------------------------------------------

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
        """Load a series and verify the caller owns it.

        Mirrors ``KBCanonService._verify_series_ownership``: a *missing* series
        and a *not-owned* series both surface as ``ForbiddenError`` (HTTP 403) —
        never ``NotFoundError`` (404) — so series ids are not enumerable
        (anti-enumeration, C1 / IDOR fix). Returns the loaded Series so callers
        avoid a second fetch.
        """
        series = await self._repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series

    async def _novel_count(self, series_id: uuid.UUID) -> int:
        """Count novels in a series via the repository (``SELECT COUNT(*)``)."""
        return await self._repo.count_novels(series_id)

    @staticmethod
    def _validate_transition(current: SeriesStatus, target: SeriesStatus) -> None:
        """Raise if ``current``→``target`` is not an allowed adjacent move."""
        allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise InvalidStatusTransitionError(current, target)

    @staticmethod
    def _build_patch(request: SeriesUpdateRequest) -> dict[str, object]:
        """Filter the request to known columns, excluding unset fields.

        ``exclude_unset`` implements PATCH semantics: only fields the caller
        explicitly provided appear. The whitelist (``_PATCHABLE_FIELDS`` plus
        ``status``) keeps arbitrary keys out of the repository's ``setattr``
        loop (Task 3.3 note).
        """
        allowed = _PATCHABLE_FIELDS | {"status"}
        provided = request.model_dump(exclude_unset=True)
        return {key: value for key, value in provided.items() if key in allowed}

    @staticmethod
    def _to_response(series: Series, novel_count: int) -> SeriesResponse:
        """Build a ``SeriesResponse`` from a Core ``Series`` + count."""
        return SeriesResponse(
            id=series.id,
            user_id=series.user_id,
            title=series.title,
            subtitle=series.subtitle,
            description=series.description,
            genre=series.genre,
            writing_language=series.writing_language,
            status=series.status,
            planned_novel_count=series.planned_novel_count,
            novel_count=novel_count,
        )
