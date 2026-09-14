"""ANAL-007 Author Voice analysis routes — SSE endpoint (thin delegation).

This router handles the author-voice-specific endpoint. Business logic is in
``author_voice_service.py``. The service yields structured
:class:`AuthorVoiceStreamEvent` objects, so the SSE stream emits
``"progress"`` / ``"result"`` / ``"done"`` events and a
``data: [DONE]`` sentinel.

Errors that fire after headers are sent (novel/chapter lookup happens inside
the stream) are communicated in-band as an ``"error"`` event — they are
logged (not swallowed, RULE-11) and the stream still terminates cleanly with
``[DONE]`` (precedent: character-voice + coreference SSE routers).

RULE-20 streaming compliance: the route returns a ``StreamingResponse`` with
an ``AsyncIterator[str]`` body; no blocking I/O in the handler.
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
from narrare.analysis.dependencies_author_voice import get_author_voice_service
from narrare.analysis.schemas_author_voice import (
    AuthorVoiceRequest,
    AuthorVoiceStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/author-voice/{novel_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_author_voice(
    novel_id: uuid.UUID,
    request: AuthorVoiceRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for author-voice analysis of a novel's chapters (ANAL-007).

    Profiles the narrator's voice (deterministic metrics + LLM qualitative
    judgement over the full prose), writes the resulting
    :class:`AuthorVoiceProfile` to ``ProjectSettings.author_voice``, and
    streams the assembled profile.

    **SSE Event Stream:**

    1. ``"progress"`` event (chapter count / status; soft warning when below
       the 3-chapter minimum).
    2. One ``"result"`` event carrying the assembled
       :class:`AuthorVoiceProfile` (single profile per novel — author voice
       is the narrator's voice, not per-character).
    3. ``"done"`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = await get_author_voice_service(novel_id=novel_id, session=session, user_id=user_id)
    chapter_ids = [uuid.UUID(cid) for cid in request.chapter_ids] if request.chapter_ids else None

    # ADR-086 Decision 3: resolve the per-user model routing BEFORE the
    # StreamingResponse is constructed, so ConfigurationError surfaces as
    # a proper pre-header 400 instead of an in-band SSE error. Idempotent
    # one-line lifecycle call — RULE-06-compatible service delegation.
    await service.ensure_resolved()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.analyze(novel_id, chapter_ids, uuid.UUID(user_id)):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "author_voice_sse_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = AuthorVoiceStreamEvent(
                event="error",
                error="Author-voice analysis failed.",
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
