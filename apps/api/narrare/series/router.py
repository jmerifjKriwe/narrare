"""FastAPI routes for Series CRUD + settings (RULE-06: thin router).

Routes delegate immediately to ``SeriesService``. Domain errors are mapped to
HTTP by the global ``NarrareError`` handler in ``_app/main.py``
(``SeriesNotFoundError`` -> 404, ``InvalidStatusTransitionError`` -> 409), so
the routes stay free of try/except, mirroring the novels router.

Novels-in-series (join preview/apply, list, reorder, remove) live in
``router_novels.py`` (RULE-04 split).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.series.dependencies import get_series_service
from narrare.series.schemas import (
    SeriesCreateRequest,
    SeriesResponse,
    SeriesSettingsResponse,
    SeriesSettingsUpdateRequest,
    SeriesSummary,
    SeriesUpdateRequest,
)
from narrare.series.service import SeriesService

router = APIRouter(prefix="/series", tags=["series"])


@router.post("", response_model=SeriesResponse, status_code=status.HTTP_201_CREATED)
async def create_series(
    request: SeriesCreateRequest,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    """Create a new series (status defaults to 'draft')."""
    return await service.create_series(uuid.UUID(user_id), request)


@router.get("", response_model=list[SeriesSummary])
async def list_series(
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> list[SeriesSummary]:
    """List all series for the current user."""
    return await service.list_series(uuid.UUID(user_id))


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    """Get a single series by ID."""
    return await service.get_series(series_id, uuid.UUID(user_id))


@router.patch("/{series_id}", response_model=SeriesResponse)
async def update_series(
    series_id: uuid.UUID,
    request: SeriesUpdateRequest,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    """Update series metadata (status transitions enforced, 409 on violation)."""
    return await service.update_series(series_id, uuid.UUID(user_id), request)


@router.delete("/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> None:
    """Delete a series."""
    await service.delete_series(series_id, uuid.UUID(user_id))


@router.get("/{series_id}/settings", response_model=SeriesSettingsResponse)
async def get_settings(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> SeriesSettingsResponse:
    """Get series settings."""
    return await service.get_settings(series_id, uuid.UUID(user_id))


@router.patch("/{series_id}/settings", response_model=SeriesSettingsResponse)
async def update_settings(
    series_id: uuid.UUID,
    request: SeriesSettingsUpdateRequest,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> SeriesSettingsResponse:
    """Update series settings."""
    return await service.update_settings(series_id, uuid.UUID(user_id), request)
