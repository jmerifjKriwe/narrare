"""Timeline analysis routes — AI analysis, extraction, and consistency endpoints.

Thin routers that delegate immediately to services (RULE-06).
Split from router_timeline.py to stay under the 150-line limit (RULE-04).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._timeline_analysis_factory import get_timeline_analysis_service
from narrare.planning._timeline_consistency_factory import get_timeline_consistency_service
from narrare.planning.schemas import TimelineResponse
from narrare.planning.timeline_schemas import (
    CharacterAgeReport,
    ExtractedEventResponse,
    ExtractionRequest,
    TemporalConsistencyResponse,
)

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


@router.post("/{novel_id}/extract", response_model=list[ExtractedEventResponse])
async def extract_temporal_expressions(
    novel_id: uuid.UUID,
    request: ExtractionRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> list[ExtractedEventResponse]:
    """Extract temporal expressions from chapter content."""
    service = await get_timeline_analysis_service(
        session=session, user_id=user_id, novel_id=novel_id
    )
    result = await service.extract_temporal_expressions(
        novel_id, uuid.UUID(user_id), request.chapter_ids or None
    )
    return [
        ExtractedEventResponse(
            id=str(i),
            expression=e.expression,
            event_name=e.event_name,
            timestamp_raw=e.timestamp_raw,
            chapter_reference=e.chapter_reference,
            character_names=e.character_names,
            location_name=e.location_name,
            confidence=e.confidence,
            context=e.context,
        )
        for i, e in enumerate(result)
    ]


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
