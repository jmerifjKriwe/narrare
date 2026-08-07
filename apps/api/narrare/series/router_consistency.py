"""FastAPI routes for series-consistency checks (Spec 4 Task 2 — thin router).

One endpoint backs the canon-contradiction check:

- ``POST …/series/{series_id}/consistency/check`` — check a band's chapter
  prose against the series Canon (body carries ``novel_id``).

RULE-06: the route immediately delegates to ``SeriesConsistencyService``. No
business logic lives here. Ownership + novel-membership are verified INSIDE the
service (mirrors ``SeriesVoiceService``) because the novel id arrives in the
request body (not the path), so the path-based ``verify_novel_in_owned_series``
dependency does not apply. Returns ``200`` — the check is a read-only analysis
action, not a resource creation (mirrors ``router_author_voice_drift``).

Errors map via the global ``NarrareError`` handler in ``_app/main.py``
(``ForbiddenError`` → 403, ``NotFoundError`` → 404, ``ConfigurationError`` →
500, ``WritingError`` → 500, ``ValidationError`` → 422).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.series.dependencies_consistency import get_series_consistency_service
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckRequest,
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_consistency_service import SeriesConsistencyService

router = APIRouter(prefix="/series", tags=["series"])


@router.post(
    "/{series_id}/consistency/check",
    response_model=SeriesConsistencyCheckResponse,
)
async def check_series_consistency(
    series_id: uuid.UUID,
    request: SeriesConsistencyCheckRequest,
    user_id: CurrentUserIdDep,
    service: SeriesConsistencyService = Depends(get_series_consistency_service),
) -> SeriesConsistencyCheckResponse:
    """Check a band's chapter prose against the series Canon KB.

    Runs the governed ``series_consistency`` agent (1 LLM call) over the
    novel's chapter texts + the series Canon entries and returns the detected
    contradictions (possibly empty — no contradictions found is a valid
    result). Read-only — nothing is persisted.

    Ownership + novel-membership are verified inside the service
    (anti-enumeration: a missing/not-owned series and a non-member novel both
    surface as ``403``).
    """
    return await service.check_novel(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
    )
