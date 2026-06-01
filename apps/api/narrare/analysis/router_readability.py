"""ANAL-003 Readability analysis routes — thin delegation (RULE-06).

This router handles readability-specific endpoints.
Business logic is in ``services/readability_service.py``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.analysis.dependencies import get_readability_service
from narrare.analysis.schemas_readability import ReadabilityRequest
from narrare.analysis.services.readability_service import ReadabilityService
from narrare_core.analysis.types import ReadabilityResult

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/readability",
    response_model=list[ReadabilityResult],
    summary="Analyze chapter(s) readability — deterministic metrics + AI sentence analysis",
)
async def analyze_readability(
    novel_id: uuid.UUID,
    request: ReadabilityRequest,
    user_id: CurrentUserIdDep,
    service: ReadabilityService = Depends(get_readability_service),
) -> list[ReadabilityResult]:
    """Analyze readability for one or more chapters.

    Phase 1 (instant): Formula-based metrics (Flesch, Kincaid, Fog).
    Phase 2 (5-15s): AI sentence analysis with rewrite suggestions.

    Results combine deterministic scores with actionable AI feedback.

    Args:
        novel_id: The novel containing the chapters.
        request: Chapter IDs + language setting.

    Returns:
        List of ``ReadabilityResult`` (one per chapter, same order as
        the request's ``chapter_ids``).
    """
    return await service.analyze(
        novel_id=novel_id,
        chapter_ids=request.chapter_ids,
        user_id=uuid.UUID(user_id),
        language=request.language,
    )
