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

from narrare.novels.schemas import NovelSummaryResponse
from narrare.series.schemas import SeriesResponse, SeriesSettingsResponse, SeriesSummary
from narrare_core.series.schemas import SeriesSettings
from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.schemas import (
        SeriesCreateRequest,
        SeriesSettingsUpdateRequest,
        SeriesUpdateRequest,
    )
    from narrare_core.series.schemas import Series, SeriesStatus

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

    async def get_series(self, series_id: uuid.UUID) -> SeriesResponse:
        """Get a single Series, raising SeriesNotFoundError if missing.

        Args:
            series_id: The Series to load.

        Raises:
            SeriesNotFoundError: If no Series exists with this id.
        """
        series = await self._repo.get(series_id)
        if series is None:
            raise SeriesNotFoundError(series_id)
        return self._to_response(series, await self._novel_count(series_id))

    async def list_series(self, user_id: uuid.UUID) -> list[SeriesSummary]:
        """List all Series for a user with computed novel counts."""
        all_series = await self._repo.list_for_user(user_id)
        summaries: list[SeriesSummary] = []
        for s in all_series:
            count = await self._novel_count(s.id)
            summaries.append(
                SeriesSummary(
                    id=s.id,
                    title=s.title,
                    subtitle=s.subtitle,
                    status=s.status,
                    novel_count=count,
                )
            )
        return summaries

    async def update_series(
        self, series_id: uuid.UUID, request: SeriesUpdateRequest
    ) -> SeriesResponse:
        """Update a Series, enforcing status-transition rules.

        Args:
            series_id: The Series to patch.
            request: PATCH body — only set fields are forwarded.

        Raises:
            SeriesNotFoundError: If the Series does not exist.
            InvalidStatusTransitionError: If ``status`` requests a non-adjacent
                move (e.g. draft→completed).
        """
        current = await self._repo.get(series_id)
        if current is None:
            raise SeriesNotFoundError(series_id)

        if request.status is not None and request.status != current.status:
            self._validate_transition(current.status, request.status)

        patch = self._build_patch(request)
        updated = await self._repo.update(series_id, **patch) if patch else current
        if updated is None:
            # Race: deleted between get and update.
            raise SeriesNotFoundError(series_id)
        logger.info("series_updated", series_id=str(series_id))
        return self._to_response(updated, await self._novel_count(series_id))

    async def delete_series(self, series_id: uuid.UUID) -> None:
        """Delete a Series, raising SeriesNotFoundError if missing.

        Args:
            series_id: The Series to delete.

        Raises:
            SeriesNotFoundError: If the Series does not exist.
        """
        deleted = await self._repo.delete(series_id)
        if not deleted:
            raise SeriesNotFoundError(series_id)
        logger.info("series_deleted", series_id=str(series_id))

    # -- novels in series + settings ------------------------------------

    async def list_novels(self, series_id: uuid.UUID) -> list[NovelSummaryResponse]:
        """List the novels in a series, ordered by ``series_position``.

        Raises:
            SeriesNotFoundError: If the Series does not exist.
        """
        await self._require_series(series_id)
        novels = await self._repo.list_novels(series_id)
        return [NovelSummaryResponse.model_validate(novel) for novel in novels]

    async def reorder_novels(self, series_id: uuid.UUID, novel_ids: list[uuid.UUID]) -> None:
        """Reassign sequential 1-based positions to the series' novels.

        Raises:
            SeriesNotFoundError: If the Series does not exist.
        """
        await self._require_series(series_id)
        await self._repo.reorder_novels(series_id, novel_ids)
        logger.info("series_novels_reordered", series_id=str(series_id))

    async def get_settings(self, series_id: uuid.UUID) -> SeriesSettingsResponse:
        """Get Series settings (synthesises a default if no row exists yet).

        Raises:
            SeriesNotFoundError: If the Series does not exist.
        """
        await self._require_series(series_id)
        settings = await self._repo.get_settings(series_id)
        if settings is None:
            settings = SeriesSettings(series_id=series_id, author_voice=None)
        return SeriesSettingsResponse.model_validate(settings)

    async def update_settings(
        self, series_id: uuid.UUID, request: SeriesSettingsUpdateRequest
    ) -> SeriesSettingsResponse:
        """Patch Series settings (only explicitly-provided fields forward).

        Raises:
            SeriesNotFoundError: If the Series does not exist.
        """
        await self._require_series(series_id)
        patch = request.model_dump(exclude_unset=True)
        settings = await self._repo.update_settings(series_id, patch)
        return SeriesSettingsResponse.model_validate(settings)

    # -- helpers --------------------------------------------------------

    async def _require_series(self, series_id: uuid.UUID) -> None:
        """Raise ``SeriesNotFoundError`` if the series does not exist."""
        if await self._repo.get(series_id) is None:
            raise SeriesNotFoundError(series_id)

    async def _novel_count(self, series_id: uuid.UUID) -> int:
        """Count novels in a series via the repository."""
        return len(await self._repo.list_novels(series_id))

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
