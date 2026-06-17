"""Memory analysis route — preference analysis endpoint.

Split from router.py for RULE-04 compliance (router max 150 lines).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.memory.schemas import AnalyzeRequest, AnalyzeResponse

if TYPE_CHECKING:
    from narrare.memory.analysis_service import PreferenceAnalysisService

router = APIRouter(tags=["memory"])

# Simplified rate-limit: tracks last analysis time per user/project
_analysis_timestamps: dict[str, datetime] = {}
ANALYSIS_COOLDOWN = timedelta(hours=1)


async def _get_analysis_service(
    session: SessionDep,
) -> PreferenceAnalysisService:
    """Async factory for PreferenceAnalysisService."""
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.memory.analysis_service import PreferenceAnalysisService
    from narrare.memory.repository import FeedbackRepository, PreferenceProfileRepository

    registry = get_model_registry()
    feedback_repo = FeedbackRepository(session)
    profile_repo = PreferenceProfileRepository(session)
    composer = get_composer()
    return PreferenceAnalysisService(
        registry=registry,
        feedback_repo=feedback_repo,
        profile_repo=profile_repo,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )


@router.post("/memory/analyze", response_model=AnalyzeResponse)
async def analyze_preferences(
    request: AnalyzeRequest,
    user_id: CurrentUserIdDep,
    service: PreferenceAnalysisService = Depends(_get_analysis_service),
) -> AnalyzeResponse:
    """Run preference analysis on accumulated feedback.

    Requires at least 5 feedback events. Rate-limited to once per hour
    per user/project pair.
    """
    uid = UUID(user_id)
    key = f"{user_id}:{request.project_id}"

    # Rate-limit check
    last_run = _analysis_timestamps.get(key)
    if last_run and (datetime.now(UTC) - last_run) < ANALYSIS_COOLDOWN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Analysis already run recently. Try again later.",
        )

    try:
        result = await service.analyze(uid, request.project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    _analysis_timestamps[key] = datetime.now(UTC)
    return result
