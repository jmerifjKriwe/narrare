"""KB improve routes — thin delegation to KBImproveService (RULE-06)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_improve_service
from narrare.kb.improve_contracts import (
    KBImproveAnalysisResponse,
    KBImproveApplyRequest,
    KBImproveApplyResponse,
)
from narrare.kb.improve_service import KBImproveService

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/entities/{entry_id}/improve",
    response_model=KBImproveAnalysisResponse,
    summary="Analyze a KB entry and return improvement suggestions",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_entry(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBImproveService = Depends(get_kb_improve_service),
) -> KBImproveAnalysisResponse:
    """Analyze a KB entry and return improvement suggestions."""
    return await service.analyze(
        novel_id=novel_id,
        entry_id=entry_id,
    )


@router.post(
    "/novels/{novel_id}/kb/entities/{entry_id}/improve/apply",
    response_model=KBImproveApplyResponse,
    summary="Apply selected improvement suggestions to the entry",
)
async def apply_improvements(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: KBImproveApplyRequest,
    user_id: CurrentUserIdDep,
    service: KBImproveService = Depends(get_kb_improve_service),
) -> KBImproveApplyResponse:
    """Apply selected improvement suggestions to the entry."""
    return await service.apply(
        novel_id=novel_id,
        entry_id=entry_id,
        suggestion_ids=request.suggestion_ids,
    )
