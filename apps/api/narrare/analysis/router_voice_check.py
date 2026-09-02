"""WRITE-010 Voice-check analysis routes — SSE endpoint (thin delegation)."""

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
from narrare.analysis.dependencies_voice_check import get_voice_check_service
from narrare.analysis.schemas_voice_check import VoiceCheckStreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/voice-check/{chapter_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_voice_check(
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for checking a chapter's dialogue against voice profiles.

    **SSE Event Stream:**

    1. ``"progress"`` event with pipeline status.
    2. One ``"result"`` event per speaking character.
    3. ``"done"`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = await get_voice_check_service(session=session, user_id=user_id)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.check(chapter_id, uuid.UUID(user_id)):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "voice_check_sse_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = VoiceCheckStreamEvent(
                event="error",
                error="Voice-check analysis failed.",
                is_final=True,
            )
            data = error_event.model_dump(mode="json")
            yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
