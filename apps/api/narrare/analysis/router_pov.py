"""ANAL-004 POV analysis routes — thin delegation (RULE-06).

This router handles POV-specific endpoints.
Business logic is in ``services/pov_service.py``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.analysis.dependencies import get_pov_service
from narrare.analysis.schemas_pov import POVRequest
from narrare.analysis.services.pov_service import POVService
from narrare_core.analysis.types import POVResult

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/pov",
    response_model=POVResult,
    summary="Analyze POV consistency — scene detection + head-hopping + knowledge leakage",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def analyze_pov(
    novel_id: uuid.UUID,
    request: POVRequest,
    user_id: CurrentUserIdDep,
    service: POVService = Depends(get_pov_service),
) -> POVResult:
    """Analyze POV consistency for one or more chapters.

    Detects POV character per scene, flags head-hopping, knowledge
    leakage, emotional leakage, and physical impossibility violations.

    Args:
        novel_id: The novel containing the chapters.
        request: Chapter IDs + language.

    Returns:
        ``POVResult`` with per-scene assignments, flagged violations,
        and distribution statistics.
    """
    return await service.analyze(
        novel_id=novel_id,
        chapter_ids=request.chapter_ids,
        user_id=uuid.UUID(user_id),
        language=request.language,
    )
