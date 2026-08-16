"""FastAPI route for series-scope voice drift (Spec 4 Task 3 — thin router).

One endpoint backs the cross-novel voice-drift check:

- ``POST …/series/{series_id}/voice-drift/check`` — analyse a band's narrator
  drift against the series voice baseline (body carries the ``novel_id`` + the
  optional ``chapter_ids`` filter).

RULE-06: the route immediately delegates to
``SeriesDriftPersistenceService`` (C2 store-on-run). No business logic lives
here. Ownership + novel-membership are verified INSIDE the service (mirrors
``SeriesVoiceService``). Returns ``200`` — the check is an analysis action
whose result is persisted as the band's latest drift snapshot (C2) before it
is returned (mirrors the consistency router + the novel-level drift
aggregate).

The RESPONSE schema is REUSED verbatim from the novel-level analysis module
(:class:`AuthorVoiceDriftResponse`, RULE-22); only the request shape is
series-specific (:class:`SeriesVoiceDriftCheckRequest`).

Errors map via the global ``NarrareError`` handler in ``_app/main.py``
(``ForbiddenError`` → 403, ``NotFoundError`` → 404, ``ConfigurationError`` →
500).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResponse
from narrare.series.dependencies_drift_persistence import (
    get_series_drift_persistence_service,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare.series.series_voice_drift_schemas import SeriesVoiceDriftCheckRequest

router = APIRouter(prefix="/series", tags=["series"])


@router.post(
    "/{series_id}/voice-drift/check",
    response_model=AuthorVoiceDriftResponse,
)
async def check_series_voice_drift(
    series_id: uuid.UUID,
    request: SeriesVoiceDriftCheckRequest,
    user_id: CurrentUserIdDep,
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
) -> AuthorVoiceDriftResponse:
    """Check a band's narrator drift against the series voice baseline.

    Loads the series voice profile (``SeriesSettings.author_voice``), computes
    the per-chapter narrator trend + jumps against the SERIES metric group,
    runs the governed ``author_voice_drift`` agent (1 LLM call), and returns
    the aggregate drift result (or a graceful ``no_profile`` when the series
    voice cannot be analysed). The result is persisted as the band's latest
    drift snapshot (C2) before it is returned.

    Ownership + novel-membership are verified inside the service
    (anti-enumeration: a missing/not-owned series and a non-member novel both
    surface as ``403``).
    """
    # Reuse the novel-level AuthorVoiceDriftRequest shape for the chapter
    # filter (the service accepts it), carrying only chapter_ids.
    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest

    return await service.check_and_store_voice_drift(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
        request=AuthorVoiceDriftRequest(chapter_ids=request.chapter_ids),
    )
