"""FastAPI routes for novels-in-series (RULE-06: thin router).

Join preview/apply (Policy alpha), list, reorder and remove. Delegates to
``SeriesService`` (read/reorder) and ``SeriesJoinService`` (membership
mutations). Errors map via the global ``NarrareError`` handler in
``_app/main.py`` (``NotFoundError`` -> 404, ``NovelAlreadyInSeriesError`` ->
409). Series CRUD + settings live in ``router.py`` (RULE-04 split).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.novels.schemas import NovelSummaryResponse
from narrare.series.dependencies import get_series_join_service, get_series_service
from narrare.series.join_service import SeriesJoinService
from narrare.series.schemas import (
    JoinApplyRequest,
    JoinPreview,
    JoinPreviewRequest,
    JoinResult,
    ReorderNovelsRequest,
)
from narrare.series.service import SeriesService
from narrare_core.series.schemas import NovelRow

router = APIRouter(prefix="/series", tags=["series"])


@router.get("/{series_id}/novels", response_model=list[NovelSummaryResponse])
async def list_novels_in_series(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> list[NovelRow]:
    """List novels in a series, ordered by ``series_position``.

    Returns Core ``NovelRow`` value objects; ``response_model`` projects them to
    ``NovelSummaryResponse`` for the HTTP body.
    """
    return await service.list_novels(series_id, uuid.UUID(user_id))


@router.post("/{series_id}/novels", response_model=JoinPreview)
async def preview_join(
    series_id: uuid.UUID,
    body: JoinPreviewRequest,
    user_id: CurrentUserIdDep,
    join_service: SeriesJoinService = Depends(get_series_join_service),
) -> JoinPreview:
    """Preview joining a novel to a series (Policy alpha; does NOT mutate)."""
    return await join_service.preview_join(series_id, body.novel_id, uuid.UUID(user_id))


@router.post("/{series_id}/novels/{novel_id}/apply", response_model=JoinResult)
async def apply_join(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    body: JoinApplyRequest,
    user_id: CurrentUserIdDep,
    join_service: SeriesJoinService = Depends(get_series_join_service),
) -> JoinResult:
    """Apply the join — executes the previewed treatments atomically."""
    return await join_service.apply_join(series_id, novel_id, body.position, uuid.UUID(user_id))


@router.delete("/{series_id}/novels/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_novel_from_series(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    join_service: SeriesJoinService = Depends(get_series_join_service),
) -> None:
    """Remove a novel from a series (back to standalone)."""
    await join_service.remove_novel(series_id, novel_id, uuid.UUID(user_id))


@router.patch("/{series_id}/novels/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_novels(
    series_id: uuid.UUID,
    body: ReorderNovelsRequest,
    user_id: CurrentUserIdDep,
    service: SeriesService = Depends(get_series_service),
) -> None:
    """Reorder novels within a series (full ordered id list)."""
    await service.reorder_novels(series_id, uuid.UUID(user_id), body.novel_ids)
