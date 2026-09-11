"""ANAL-009 Voice-drift analysis routes — SSE endpoint (thin delegation).

This router handles the voice-drift-specific endpoint. Business logic is in
``voice_drift_service.py``. The service yields structured
:class:`VoiceDriftEvent` objects, so the SSE stream emits ``"progress"`` /
per-character ``"character_result"`` / ``"no_profile"`` / ``"done"`` events
and a ``data: [DONE]`` sentinel.

The endpoint is **novel-scoped** (``POST /analysis/voice-drift/{novel_id}``),
mirroring ``router_character_voice`` (drift is inherently longitudinal across
all chapters), NOT chapter-scoped like ``router_voice_check`` (the checker
judges one chapter).

Errors that fire after headers are sent (novel/chapter lookup happens inside
the stream) are communicated in-band as an ``"error"`` event — they are
logged (not swallowed, RULE-11) and the stream still terminates cleanly with
``[DONE]`` (precedent: coreference / character-voice SSE routers).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.observability import enrich_sse_data
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.analysis.dependencies_voice_drift import get_voice_drift_service
from narrare.analysis.schemas_voice_drift import VoiceDriftEvent, VoiceDriftRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/voice-drift/{novel_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_voice_drift(
    novel_id: uuid.UUID,
    request: VoiceDriftRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for longitudinal character-voice drift analysis (ANAL-009).

    For each character with a stored ANAL-008 profile (``voice_metrics``) who
    speaks in ≥1 selected chapter, computes the per-chapter match trend +
    adjacent-chapter jumps, runs the governed ``voice_drift`` agent (1 call
    per character), and streams per-character results. Read-only — nothing is
    persisted.

    **SSE Event Stream:**

    1. ``"progress"`` event (character/chapter count / status).
    2. One ``"character_result"`` event per analysable character (carrying
       that character's trend + jumps + overall score/band + agent
       classification), OR a ``"no_profile"`` event per character that cannot
       be analysed (RULE-11 graceful skip).
    3. ``"done"`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = await get_voice_drift_service(novel_id=novel_id, session=session, user_id=user_id)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.run_stream(
                novel_id,
                uuid.UUID(user_id),
                request,
            ):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "voice_drift_sse_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = VoiceDriftEvent(
                event="error",
                error="Voice-drift analysis failed.",
                is_final=True,
            )
            yield f"data: {json.dumps(enrich_sse_data(error_event.model_dump(mode='json')))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
