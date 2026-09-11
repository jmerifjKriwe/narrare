"""Dialogue Coach SSE route — thin delegation to DialogueCoachService (ASSIST-004).

POST /api/v1/ai-assist/dialogue-coach/{chapter_id}

The service yields structured DialogueCoachStreamEvent objects; the SSE
stream emits progress / result / done / error events and a final
``data: [DONE]`` sentinel.

Errors that fire after headers are sent are communicated in-band as an
``error`` event — they are logged (not swallowed, RULE-11) and the stream
still terminates cleanly with ``[DONE]`` (precedent: character_voice SSE
router).

Pattern reference: ``apps/api/narrare/analysis/router_character_voice.py``.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.observability import enrich_sse_data
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.ai_assist.dependencies import get_dialogue_coach_service
from narrare.ai_assist.schemas import (
    DialogueCoachRequest,
    DialogueCoachStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.ai_assist.service import DialogueCoachService

router = APIRouter(prefix="/ai-assist", tags=["ai-assist"])
logger = structlog.get_logger(__name__)


@router.post(
    "/dialogue-coach/{chapter_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def coach_dialogue(
    chapter_id: uuid.UUID,
    request: DialogueCoachRequest,
    user_id: CurrentUserIdDep,
    service: DialogueCoachService = Depends(get_dialogue_coach_service),
) -> StreamingResponse:
    """SSE stream for dialogue coaching (ASSIST-004).

    **SSE Event Stream:**

    1. ``progress`` event ("Analysing dialogue…").
    2. ``result`` event carrying the full ``DialogueCoachResponse``.
    3. ``done`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``error`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.stream(
                chapter_id=chapter_id,
                user_id=uuid.UUID(user_id),
                request=request,
            ):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "dialogue_coach_sse_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = DialogueCoachStreamEvent(
                event="error",
                error="Dialogue Coach analysis failed.",
                is_final=True,
            )
            yield f"data: {json.dumps(enrich_sse_data(error_event.model_dump(mode='json')))}\n\n"
        yield "data: [DONE]\n\n"

    # ADR-086 Decision 3: resolve the per-user model routing BEFORE the
    # StreamingResponse is constructed, so ConfigurationError surfaces as
    # a proper pre-header 400 instead of an in-band SSE error. Idempotent
    # one-line lifecycle call — RULE-06-compatible service delegation.
    await service.ensure_resolved()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
