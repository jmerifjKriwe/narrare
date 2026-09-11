"""ANAL-008 Character Voice analysis routes — SSE endpoint (thin delegation).

This router handles the character-voice-specific endpoint. Business logic is
in ``character_voice_service.py``. The service yields structured
:class:`CharacterVoiceStreamEvent` objects, so the SSE stream emits
``"progress"`` / per-character ``"result"`` / ``"done"`` events and a
``data: [DONE]`` sentinel.

Errors that fire after headers are sent (novel/chapter lookup happens inside
the stream) are communicated in-band as an ``"error"`` event — they are
logged (not swallowed, RULE-11) and the stream still terminates cleanly with
``[DONE]`` (precedent: coreference SSE router).
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
from narrare.analysis.dependencies_character_voice import get_character_voice_service
from narrare.analysis.schemas_character_voice import (
    CharacterVoiceRequest,
    CharacterVoiceStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/character-voice/{novel_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_character_voice(
    novel_id: uuid.UUID,
    request: CharacterVoiceRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for character-voice analysis of a novel's chapters (ANAL-008).

    Profiles each speaking character's voice (deterministic metrics + LLM
    qualitative judgement), writes the result to each character's KB
    ``speech.voice_analysis``, and streams per-character results.

    **SSE Event Stream:**

    1. ``"progress"`` event (character count / status).
    2. One ``"result"`` event per profiled character (carrying that
       character's ``CharacterVoiceResult``).
    3. ``"done"`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = await get_character_voice_service(novel_id=novel_id, session=session, user_id=user_id)
    chapter_ids = [uuid.UUID(cid) for cid in request.chapter_ids] if request.chapter_ids else None

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.analyze(novel_id, chapter_ids, uuid.UUID(user_id)):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "character_voice_sse_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = CharacterVoiceStreamEvent(
                event="error",
                error="Character-voice analysis failed.",
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
