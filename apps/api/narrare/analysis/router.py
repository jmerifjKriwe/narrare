"""Analysis API routes — thin delegation (RULE-06).

All business logic is in service files.
This router only handles HTTP request/response mapping.

Readability routes live in ``router_readability.py`` (RULE-04: < 150 lines).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.dependencies import get_sentiment_service
from narrare.analysis.dependencies_beta_reader import get_beta_reader_service
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderDeepDiveResponse,
    BetaReaderRequest,
    BetaReaderResponse,
    SentimentRequest,
)
from narrare.analysis.services.sentiment_service import ChapterSentimentService
from narrare_core.analysis.types import SentimentOverview

router = APIRouter(prefix="/analysis", tags=["analysis"])

# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader Routes
# ---------------------------------------------------------------------------


@router.post(
    "/beta-reader",
    response_model=BetaReaderResponse,
    summary="Run beta reader analysis on chapter(s)",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
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
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
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


# ---------------------------------------------------------------------------
# ANAL-002: Sentiment Analysis Routes
# ---------------------------------------------------------------------------


@router.post(
    "/sentiment",
    response_model=list[SentimentOverview],
    summary="Analyze chapter(s) sentiment — deterministic VAD + emotion + arc",
)
async def analyze_sentiment(
    novel_id: uuid.UUID,
    request: SentimentRequest,
    user_id: CurrentUserIdDep,
    service: ChapterSentimentService = Depends(get_sentiment_service),
) -> list[SentimentOverview]:
    """Analyze sentiment for one or more chapters.

    Uses deterministic VAD (Valence-Arousal-Dominance) + emotion scoring
    plus optional narrative arc detection (ADR-021).

    Results are **deterministic** — same text always produces the same
    scores. No LLM calls are involved in the measurement step.

    Args:
        novel_id: The novel containing the chapters.
        request: Chapter IDs + analysis options (language, arc detection).

    Returns:
        List of ``SentimentOverview`` (one per chapter, same order as
        the request's ``chapter_ids``).
    """
    return await service.analyze_chapters(
        novel_id=novel_id,
        chapter_ids=request.chapter_ids,
        user_id=uuid.UUID(user_id),
        language=request.language,
        detect_arc=request.detect_arc,
    )
