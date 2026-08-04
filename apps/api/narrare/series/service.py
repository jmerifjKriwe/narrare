"""Series service — CRUD business logic with status-transition enforcement.

Implements ``SeriesServiceProtocol`` (contracts.py). Business logic only:
no DB queries (delegated to ``SeriesRepository``), no HTTP. Converts between
Pydantic request/response schemas and Core ``Series`` types.

Status transitions follow an adjacency matrix (``status_transitions.py``) —
only the allowed forward/back moves (e.g. draft→active, active→completed) are
permitted; a skip move (e.g. draft→completed) raises
``InvalidStatusTransitionError``. Setting the status to its current value is a
no-op, not a transition.

When a series transitions to ``completed`` (Spec 2 Task 5), the service
enqueues background band-summary generation for each novel via the injected
``BandSummaryEnqueuer`` callable. When ``None`` (backward compat), no
enqueuing happens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.series.band_summary_auto_trigger import (
    BandSummaryEnqueuer,
    enqueue_band_summaries,
)
from narrare.series.schemas import SeriesResponse, SeriesSettingsResponse, SeriesSummary
from narrare.series.status_transitions import (
    InvalidStatusTransitionError as InvalidStatusTransitionError,
)
from narrare.series.status_transitions import (
    build_patch,
    validate_transition,
)
from narrare_core.series.schemas import SeriesSettings
from narrare_core.shared.errors import ForbiddenError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.schemas import (
        SeriesCreateRequest,
        SeriesSettingsUpdateRequest,
        SeriesUpdateRequest,
    )
    from narrare_core.series.schemas import NovelRow, Series

logger = structlog.get_logger(__name__)


class SeriesNotFoundError(NotFoundError):
    """Raised when a Series is not found."""

    def __init__(self, series_id: uuid.UUID) -> None:
        super().__init__("Series", identifier=str(series_id))
        self.series_id = series_id


class SeriesService:
    """Business-logic surface for Series CRUD (delegates DB to repository).

    The optional ``enqueue_band_summary`` callable (Spec 2 Task 5) lets
    ``update_series`` trigger background band-summary generation when a series
    transitions to ``completed``. When ``None``, no enqueuing happens — this
    preserves backward compatibility with existing callers.
    """

    def __init__(
        self,
        repo: SeriesRepositoryProtocol,
        enqueue_band_summary: BandSummaryEnqueuer | None = None,
    ) -> None:
        self._repo = repo
        self._enqueue_band_summary = enqueue_band_summary

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

        transitioning_to_completed = (
            request.status is not None
            and request.status == "completed"
            and current.status != "completed"
        )

        if request.status is not None and request.status != current.status:
            validate_transition(current.status, request.status)

        patch = build_patch(request)
        updated = await self._repo.update(series_id, **patch) if patch else current
        if updated is None:
            raise ForbiddenError("You do not have access to this series")

        # Auto-trigger (Spec 2 Task 5): enqueue band-summary generation for
        # every novel when the series is marked completed (best-effort).
        if transitioning_to_completed and self._enqueue_band_summary is not None:
            novels = await self._repo.list_novels(series_id)
            await enqueue_band_summaries(novels, self._enqueue_band_summary, series_id=series_id)

        logger.info("series_updated", series_id=str(series_id))
        return self._to_response(updated, await self._novel_count(series_id))

    async def delete_series(self, series_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a Series + its Canon KB rows (the Canon fate; ADR-075 §D6).

        Raises:
            ForbiddenError: Series missing or not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        canon_deleted = await self._repo.delete_canon_for_series(series_id)
        deleted = await self._repo.delete(series_id)
        if not deleted:
            raise ForbiddenError("You do not have access to this series")
        logger.info("series_deleted", series_id=str(series_id), canon_deleted=canon_deleted)

    # -- novels in series + settings ------------------------------------

    async def list_novels(self, series_id: uuid.UUID, user_id: uuid.UUID) -> list[NovelRow]:
        """List a series' novels ordered by ``series_position``.

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
        """Load a series and verify the caller owns it (anti-enumeration).

        A *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never ``NotFoundError`` (404) — so
        series ids are not enumerable (C1 / IDOR fix).
        """
        series = await self._repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series

    async def _novel_count(self, series_id: uuid.UUID) -> int:
        """Count novels in a series via the repository (``SELECT COUNT(*)``)."""
        return await self._repo.count_novels(series_id)

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
