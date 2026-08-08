"""FastAPI routes for band summaries (Spec 2 Task 4 — thin router).

Four endpoints back the band-summary lifecycle for a novel in a series:

- ``POST   …/band-summary``           — trigger (re)generate.
- ``GET    …/band-summary``           — fetch existing (404 if none).
- ``PATCH  …/band-summary``           — set the user override.
- ``DELETE …/band-summary/override``  — clear the override.

RULE-06: every route immediately delegates to ``BandSummaryService``. No
business logic lives here. Ownership / anti-enumeration is enforced by the
``verify_novel_in_owned_series`` dependency (caller owns the series AND the
novel is in it) so the service — keyed by ``novel_id`` only and reusable from
the in-process auto-trigger (Task 5) — never repeats the check.

Errors map via the global ``NarrareError`` handler in ``_app/main.py``
(``NotFoundError`` → 404, ``ForbiddenError`` → 403, ``ValidationError`` → 422).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.series.band_summary_service import BandSummaryService
from narrare.series.dependencies import (
    get_band_summary_service,
    verify_novel_in_owned_series,
)
from narrare.series.schemas import (
    BandSummaryOverrideRequest,
    BandSummaryResponse,
)

router = APIRouter(prefix="/series", tags=["series"])


@router.post(
    "/{series_id}/novels/{novel_id}/band-summary",
    response_model=BandSummaryResponse,
)
async def generate_band_summary(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    _: None = Depends(verify_novel_in_owned_series),
    service: BandSummaryService = Depends(get_band_summary_service),
) -> BandSummaryResponse:
    """Trigger (re)generation of the band summary for ``novel_id``.

    Upsert semantics: an existing row is updated, a missing row is created.
    Returns ``200`` (not ``201``) because the endpoint is a "trigger" action
    on a resource that may already exist, not a strict create.
    """
    band_summary = await service.generate(novel_id)
    return BandSummaryResponse.model_validate(band_summary)


@router.get(
    "/{series_id}/novels/{novel_id}/band-summary",
    response_model=BandSummaryResponse,
)
async def get_band_summary(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    _: None = Depends(verify_novel_in_owned_series),
    service: BandSummaryService = Depends(get_band_summary_service),
) -> BandSummaryResponse:
    """Fetch the existing band summary (no generation; 404 if none).

    Deliberately not lazy — a GET should not trigger an LLM call. Use POST to
    (re)generate.
    """
    band_summary = await service.get(novel_id)
    return BandSummaryResponse.model_validate(band_summary)


@router.patch(
    "/{series_id}/novels/{novel_id}/band-summary",
    response_model=BandSummaryResponse,
)
async def set_band_summary_override(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    body: BandSummaryOverrideRequest,
    user_id: CurrentUserIdDep,
    _: None = Depends(verify_novel_in_owned_series),
    service: BandSummaryService = Depends(get_band_summary_service),
) -> BandSummaryResponse:
    """Set the user override (takes precedence over generated text at assembly)."""
    band_summary = await service.update_override(novel_id, body.override)
    return BandSummaryResponse.model_validate(band_summary)


@router.delete(
    "/{series_id}/novels/{novel_id}/band-summary/override",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_band_summary_override(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    _: None = Depends(verify_novel_in_owned_series),
    service: BandSummaryService = Depends(get_band_summary_service),
) -> None:
    """Clear the user override (generated text is unaffected)."""
    await service.update_override(novel_id, None)
