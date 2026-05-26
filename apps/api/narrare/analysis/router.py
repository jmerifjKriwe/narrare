"""Analysis API routes — thin delegation (RULE-06).

All business logic is in beta_reader_service.py.
This router only handles HTTP request/response mapping.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.dependencies import get_beta_reader_service
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderDeepDiveResponse,
    BetaReaderRequest,
    BetaReaderResponse,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/beta-reader",
    response_model=BetaReaderResponse,
    summary="Run beta reader analysis on chapter(s)",
)
async def analyze_chapter(
    novel_id: uuid.UUID,
    request: BetaReaderRequest,
    user_id: CurrentUserIdDep,
    service: BetaReaderService = Depends(get_beta_reader_service),
) -> BetaReaderResponse:
    """Run Phase 1 beta reader analysis on chapter(s).

    Phase 1: Comprehensive feedback across all categories.
    Results are cached for 30 minutes.
    """
    return await service.analyze(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )


@router.post(
    "/beta-reader/deep-dive",
    response_model=BetaReaderDeepDiveResponse,
    summary="Run Phase 2 deep-dive on a specific category",
)
async def deep_dive_category(
    novel_id: uuid.UUID,
    request: BetaReaderDeepDiveRequest,
    user_id: CurrentUserIdDep,
    service: BetaReaderService = Depends(get_beta_reader_service),
) -> BetaReaderDeepDiveResponse:
    """Run Phase 2 deep-dive on a specific category.

    Requires a prior Phase 1 analysis (cache_key from Phase 1 response).
    """
    return await service.deep_dive(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )
