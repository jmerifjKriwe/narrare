"""ANAL-005 Coreference analysis routes — SSE endpoint (thin delegation).

This router handles the coreference-specific endpoint. Business logic is
in ``coreference_service.py``. The service yields structured
:class:`CoreferenceStreamEvent` objects, so the SSE stream emits a
``"result"`` event, a ``"done"`` event, and a ``data: [DONE]`` sentinel.

Errors that fire after headers are sent (chapter/novel lookup happens
inside the stream) are communicated in-band as a ``"error"`` event —
they are logged (not swallowed, RULE-11) and the stream still terminates
cleanly with ``[DONE]`` (precedent: consistency SSE router).
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
from narrare.analysis.dependencies_coreference import get_coreference_service
from narrare.analysis.schemas_coreference import CoreferenceStreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


@router.post(
    "/coreference/{chapter_id}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_coreference(
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for coreference analysis of a chapter (ANAL-005).

    Resolves pronoun references to character names, flags ambiguous
    pronouns, tracks character mentions, and scores referential clarity.

    **SSE Event Stream:**

    1. ``"result"`` event with the full coreference analysis
       (resolutions, character_mentions, clarity_score, summary).
    2. ``"done"`` event (``is_final=True``).
    3. ``data: [DONE]`` termination signal.

    On failure, a ``"error"`` event (``is_final=True``) precedes the
    ``[DONE]`` sentinel.
    """
    service = get_coreference_service(session)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.analyze(chapter_id, uuid.UUID(user_id)):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        except Exception as exc:
            logger.error(
                "coreference_sse_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            error_event = CoreferenceStreamEvent(
                event="error",
                error="Coreference analysis failed.",
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
