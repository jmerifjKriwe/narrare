"""ANAL-009 Phase 2B Author-voice-drift analysis routes — SSE endpoint.

This router handles the author-voice-drift-specific endpoint. Business logic
is in ``author_voice_drift_service.py``. The service yields structured
:class:`AuthorVoiceDriftEvent` objects, so the SSE stream emits
``"progress"`` / ``"result"`` / ``"no_profile"`` / ``"done"`` events and a
``data: [DONE]`` sentinel.

The endpoint is **novel-scoped** (``POST /analysis/author-voice-drift/
{novel_id}``), mirroring ``router_author_voice`` + ``router_voice_drift``
(author drift is inherently longitudinal across the narrator's chapters).

Errors that fire after headers are sent (novel/chapter/profile lookup happens
inside the stream) are communicated in-band as an ``"error"`` event — they are
logged (not swallowed, RULE-11) and the stream still terminates cleanly with
``[DONE]`` (precedent: author-voice / voice-drift / coreference SSE routers).

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
from narrare.analysis.dependencies_author_voice_drift import (
    get_author_voice_drift_service,
)
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftRequest,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/author-voice-drift/{novel_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_author_voice_drift(
    novel_id: uuid.UUID,
    request: AuthorVoiceDriftRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for longitudinal author-voice drift analysis (ANAL-009 Phase 2B).

    Compares the narrator's per-chapter metrics (voice-generic + author-
    specific) against the stored :class:`AuthorVoiceProfile`'s metric group,
    computes the per-chapter match trend + adjacent-chapter jumps, runs the
    governed ``author_voice_drift`` agent (1 call), and streams the single
    narrator result. Read-only — nothing is persisted.

    **SSE Event Stream:**

    1. ``"progress"`` event (chapter count / status).
    2. One ``"result"`` event carrying the narrator's trend + jumps + overall
       score/band + agent classification, OR a ``"no_profile"`` event when the
       narrator cannot be analysed (no stored profile / missing metric blocks
       / no chapter with prose — RULE-11 graceful).
    3. ``"done"`` event (``is_final=True``).
    4. ``data: [DONE]`` termination signal.

    On failure, an ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = await get_author_voice_drift_service(
        novel_id=novel_id, session=session, user_id=user_id
    )

    # ADR-086 Decision 3: resolve the per-user model routing BEFORE the
    # StreamingResponse is constructed, so ConfigurationError surfaces as
    # a proper pre-header 400 instead of an in-band SSE error. Idempotent
    # one-line lifecycle call — RULE-06-compatible service delegation.
    await service.ensure_resolved()

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
                "author_voice_drift_sse_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = AuthorVoiceDriftEvent(
                event="error",
                error="Author-voice-drift analysis failed.",
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
