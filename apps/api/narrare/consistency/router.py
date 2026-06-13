"""Consistency API routes — thin delegation (RULE-06).

All business logic is in checker_service.py.
This router only handles HTTP request/response mapping.

Updated for ADR-044: adds SSE streaming endpoint for staged pipeline.
RULE-13: both streaming and non-streaming endpoints available.
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
from narrare.consistency.checker_service import ConsistencyCheckerService
from narrare.consistency.deps import get_consistency_service
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse
from narrare.consistency.stage_schemas import ConsistencyStageEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/consistency", tags=["consistency"])
logger = structlog.get_logger(__name__)


@router.post(
    "/check",
    response_model=ConsistencyResponse,
    summary="Run consistency check on chapter(s)",
)
async def check_consistency(
    novel_id: uuid.UUID,
    request: ConsistencyRequest,
    user_id: CurrentUserIdDep,
    service: ConsistencyCheckerService = Depends(get_consistency_service),
) -> ConsistencyResponse:
    """Run cross-chapter and cross-entity consistency analysis (non-streaming).

    Checks character, timeline, world, and plot consistency across
    the requested chapters (or all chapters if none specified) and
    optionally against KB entity data.
    """
    return await service.check(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )


@router.post(
    "/check/stream",
    summary="Stream staged consistency check with progressive results",
)
async def stream_consistency_check(
    novel_id: uuid.UUID,
    request: ConsistencyRequest,
    user_id: CurrentUserIdDep,
    service: ConsistencyCheckerService = Depends(get_consistency_service),
) -> StreamingResponse:
    """SSE stream for staged consistency analysis (ADR-044 Slice 4).

    Returns Server-Sent Events with stage-by-stage progress:
    1. ``extracting_facts`` — Stage 1 fact extraction progress
    2. ``checking_consistency`` — Stage 2 analysis progress
    3. ``complete`` — Pipeline finished
    4. Final ``ConsistencyResponse`` JSON event
    5. ``[DONE]`` sentinel

    Errors are communicated in-band as JSON error events since SSE
    cannot change status codes after headers are sent.
    """

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.stream_check(
                novel_id=novel_id,
                user_id=uuid.UUID(user_id),
                request=request,
            ):
                if isinstance(event, ConsistencyStageEvent):
                    data = enrich_sse_data(
                        {"type": "stage", **event.model_dump(mode="json")},
                    )
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    data = enrich_sse_data(
                        {"type": "result", **event.model_dump(mode="json")},
                    )
                    yield f"data: {json.dumps(data)}\n\n"
        except Exception as exc:
            logger.error("consistency_sse_failed", error=str(exc), exc_info=True)
            yield 'data: {"type": "error", "message": "Internal error during check"}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/chapters/{chapter_id}/check",
    response_model=ConsistencyResponse,
    summary="Check a single chapter for consistency",
)
async def check_chapter(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: ConsistencyRequest,
    user_id: CurrentUserIdDep,
    service: ConsistencyCheckerService = Depends(get_consistency_service),
) -> ConsistencyResponse:
    """Run consistency check focused on a single chapter.

    Compares a single chapter against KB entity data and optionally
    other chapters in the novel. Useful for targeted checking after
    a writing session.
    """
    return await service.check_chapter(
        novel_id=novel_id,
        chapter_id=chapter_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )
