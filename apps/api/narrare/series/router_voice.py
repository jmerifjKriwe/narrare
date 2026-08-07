"""FastAPI routes for Series Voice (Spec 3 Task 3 — thin router).

Four endpoints back the series-voice lifecycle:

- ``POST   …/voice/profile``  — profile a band (novel) → store as series voice.
- ``GET    …/voice``          — fetch the series voice (200, ``author_voice`` may be null).
- ``PATCH  …/voice``          — manual voice-profile override.
- ``DELETE …/voice/override`` — clear the override (null the column).

RULE-06: every route immediately delegates to ``SeriesVoiceService``. No
business logic lives here. Ownership / anti-enumeration is enforced inside the
service (mirrors ``SeriesService``) so the service is correct even outside a
request context. The profile POST is rate-limited (one ``AuthorVoiceAgent``
LLM call — same cost as the novel-level author-voice endpoint).

Errors map via the global ``NarrareError`` handler in ``_app/main.py``
(``ForbiddenError`` → 403, ``NotFoundError`` → 404, ``ValidationError`` → 422,
``ConfigurationError`` → 503).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.series.dependencies_voice import get_series_voice_service
from narrare.series.series_voice_schemas import (
    SeriesVoiceOverrideRequest,
    SeriesVoiceProfileRequest,
    SeriesVoiceResponse,
    SeriesVoiceStateResponse,
)
from narrare.series.series_voice_service import SeriesVoiceService

router = APIRouter(prefix="/series", tags=["series"])


@router.post(
    "/{series_id}/voice/profile",
    response_model=SeriesVoiceStateResponse,
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def profile_series_voice(
    series_id: uuid.UUID,
    request: SeriesVoiceProfileRequest,
    user_id: CurrentUserIdDep,
    service: SeriesVoiceService = Depends(get_series_voice_service),
) -> SeriesVoiceStateResponse:
    """Profile a novel's voice → store as the series voice (Delta foundation).

    Upsert semantics: an existing profile is overwritten (HTTP 200, not 201 —
    trigger action on a resource that may already exist, like band-summary).
    The novel MUST belong to the series (403 otherwise — anti-enumeration).
    """
    profile = await service.profile_from_novel(series_id, request.novel_id, uuid.UUID(user_id))
    return SeriesVoiceStateResponse(
        series_id=series_id, novel_id=request.novel_id, author_voice=profile
    )


@router.get("/{series_id}/voice", response_model=SeriesVoiceResponse)
async def get_series_voice(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesVoiceService = Depends(get_series_voice_service),
) -> SeriesVoiceResponse:
    """Fetch the series voice profile (``author_voice`` is null when empty)."""
    profile = await service.get(series_id, uuid.UUID(user_id))
    return SeriesVoiceResponse(series_id=series_id, author_voice=profile)


@router.patch("/{series_id}/voice", response_model=SeriesVoiceResponse)
async def update_series_voice_override(
    series_id: uuid.UUID,
    request: SeriesVoiceOverrideRequest,
    user_id: CurrentUserIdDep,
    service: SeriesVoiceService = Depends(get_series_voice_service),
) -> SeriesVoiceResponse:
    """Set a manual voice-profile override (validated as AuthorVoiceProfile)."""
    profile = await service.update_override(series_id, uuid.UUID(user_id), request.author_voice)
    return SeriesVoiceResponse(series_id=series_id, author_voice=profile)


@router.delete(
    "/{series_id}/voice/override",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_series_voice_override(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesVoiceService = Depends(get_series_voice_service),
) -> None:
    """Clear the series voice (null ``SeriesSettings.author_voice``)."""
    await service.clear_override(series_id, uuid.UUID(user_id))
