"""Timeline analysis routes — AI analysis, extraction, and consistency endpoints.

Thin routers that delegate immediately to services (RULE-06).
Split from router_timeline.py to stay under the 150-line limit (RULE-04).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._timeline_analysis_factory import get_timeline_analysis_service
from narrare.planning._timeline_consistency_factory import get_timeline_consistency_service
from narrare.planning._timeline_extraction_factory import get_timeline_extraction_service
from narrare.planning.schemas import TimelineResponse
from narrare.planning.timeline_schemas import (
    CharacterAgeReport,
    ConfirmExtractionRequest,
    ExtractionRequest,
    TemporalConsistencyResponse,
    TimelineEventCRUDResponse,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

router = APIRouter(prefix="/timeline", tags=["timeline"])


# AI analysis endpoint — moved from router.py for backward compat
@router.get("/{novel_id}", response_model=TimelineResponse)
async def get_timeline_analysis(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineResponse:
    """Generate a chronological timeline analysis for a novel."""
    service = await get_timeline_analysis_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    return await service.generate_timeline(novel_id, uuid.UUID(user_id))


# Phase 2 endpoints — extraction and consistency (PLAN-004)


@router.post("/{novel_id}/extract")
async def extract_temporal_expressions(
    novel_id: uuid.UUID,
    request: ExtractionRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """Extract temporal expressions from chapters via SSE streaming.

    Returns a Server-Sent Events stream where each event is a JSON
    object representing an extracted temporal expression. The stream
    ends with a ``[DONE]`` event. Errors during streaming are
    communicated in-band as JSON error events (SSE does not support
    mid-stream status code changes).
    """
    extraction_service = await get_timeline_extraction_service(
        session=session, user_id=user_id, novel_id=novel_id
    )

    async def event_stream() -> AsyncGenerator[str]:
        try:
            async for event in extraction_service.stream_extraction(
                novel_id, uuid.UUID(user_id), request.chapter_ids or None
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except NotFoundError:
            # Yield error in-band since SSE headers already sent as 200
            yield 'data: {"error": "Novel not found", "code": "NOT_FOUND"}\n\n'
        except ConfigurationError as e:
            yield f'data: {{"error": "{e!s}", "code": "CONFIG_ERROR"}}\n\n'
        except Exception:
            yield 'data: {"error": "Internal error during extraction", "code": "INTERNAL"}\n\n'
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
    "/{novel_id}/extract/confirm",
    response_model=TimelineEventCRUDResponse,
    status_code=201,
)
async def confirm_extracted_event(
    novel_id: uuid.UUID,
    request: ConfirmExtractionRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TimelineEventCRUDResponse:
    """Confirm an extracted expression and persist it as a timeline event."""
    service = await get_timeline_analysis_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    result = await service.confirm_extracted_event(
        novel_id, uuid.UUID(user_id), request.to_extracted_expression()
    )
    return TimelineEventCRUDResponse.model_validate(result)


@router.get("/{novel_id}/consistency", response_model=TemporalConsistencyResponse)
async def check_temporal_consistency(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> TemporalConsistencyResponse:
    """Check temporal consistency of timeline events."""
    service = await get_timeline_consistency_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    return await service.check_consistency(novel_id, uuid.UUID(user_id))


# Phase 3 endpoint — character ages (PLAN-004)


@router.get("/{novel_id}/character-ages", response_model=CharacterAgeReport)
async def get_character_ages(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> CharacterAgeReport:
    """Get character age report based on KB metadata and timeline events."""
    service = await get_timeline_consistency_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    return await service.get_character_ages(novel_id, uuid.UUID(user_id))
