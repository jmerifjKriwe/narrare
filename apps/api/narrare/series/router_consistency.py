"""FastAPI routes for series-consistency + drift snapshot (C2 — thin router).

Two endpoints share this router:

- ``POST …/series/{series_id}/consistency/check`` — check a band's chapter
  prose against the series Canon (body carries ``novel_id``); the result is
  persisted as the band's latest drift snapshot (C2 store-on-run).
- ``GET …/series/{series_id}/consistency/{novel_id}`` — fetch the persisted
  composite drift snapshot + staleness verdict (C2 Slice 6).

RULE-06: both routes immediately delegate to
``SeriesDriftPersistenceService``. No business logic lives here. Ownership +
novel-membership are verified INSIDE the service (mirrors
``SeriesVoiceService``) because the novel id arrives in the request body /
snapshot semantics (not a plain path lookup), so the path-based
``verify_novel_in_owned_series`` dependency does not apply. Both return
``200`` — analysis reads / snapshot fetches, not resource creations (mirrors
``router_author_voice_drift``).

Errors map via the global ``NarrareError`` handler in ``_app/main.py``
(``ForbiddenError`` → 403, ``NotFoundError`` → 404, ``ConfigurationError`` →
500, ``WritingError`` → 500, ``ValidationError`` → 422).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.series.dependencies_drift_persistence import (
    get_series_drift_persistence_service,
)
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckRequest,
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse

router = APIRouter(prefix="/series", tags=["series"])


@router.post(
    "/{series_id}/consistency/check",
    response_model=SeriesConsistencyCheckResponse,
)
async def check_series_consistency(
    series_id: uuid.UUID,
    request: SeriesConsistencyCheckRequest,
    user_id: CurrentUserIdDep,
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
) -> SeriesConsistencyCheckResponse:
    """Check a band's chapter prose against the series Canon KB.

    Runs the governed ``series_consistency`` agent (1 LLM call) over the
    novel's chapter texts + the series Canon entries and returns the detected
    contradictions (possibly empty — no contradictions found is a valid
    result). The result is persisted as the band's latest drift snapshot (C2)
    before it is returned.

    Ownership + novel-membership are verified inside the service
    (anti-enumeration: a missing/not-owned series and a non-member novel both
    surface as ``403``).
    """
    return await service.check_and_store_consistency(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
    )


@router.get(
    "/{series_id}/consistency/{novel_id}",
    response_model=SeriesDriftSnapshotResponse,
)
async def get_series_drift_snapshot(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
) -> SeriesDriftSnapshotResponse:
    """Fetch the persisted drift snapshot for one band (SERIES-004 Slice 6).

    Returns the latest-wins composite snapshot (canon contradictions +
    voice drift as stored by the check runs) plus the staleness verdict:
    ``stale=true`` when the band's chapter texts changed since the last
    completed write. Nothing persisted yet → an all-null snapshot with
    ``stale=false`` (never an error).

    Note: a GET to ``…/consistency/check`` (the POST-only run path) matches
    this route with a non-UUID ``novel_id`` and surfaces as 422 — there is no
    GET route on ``check`` by design.

    Ownership + novel-membership are verified inside the service
    (anti-enumeration: a missing/not-owned series and a non-member novel both
    surface as ``403``).
    """
    return await service.get_snapshot(
        series_id=series_id,
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
    )
