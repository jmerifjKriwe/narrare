"""KB entity-resolution routes — analyze/suggestions/endorse/reject (spec §7).

Thin delegation only (RULE-06/12): the scope guard runs as a router-level
dependency and every handler forwards to its service — analysis reads to
the analysis service, adjudication to the endorse service. The endorse
endpoint re-validates the suggestion (409 when stale/rejected/low-band),
executes the merge, and invalidates the analysis cache; reject persists
the dismissal (204) without touching the cache.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
from narrare.kb.entity_resolution.dependencies import (
    get_endorse_service,
    get_resolution_analyzer,
    verify_novel_scope,
)
from narrare.kb.entity_resolution.endorse_service import ResolutionEndorseService
from narrare.kb.entity_resolution.schemas_resolution import (
    MergeExecutionResult,
    ResolutionAnalysisResponse,
    ResolutionAnalyzeRequest,
    ResolutionEndorseRequest,
)

router = APIRouter(tags=["kb"], dependencies=[Depends(verify_novel_scope)])


@router.post(
    "/novels/{novel_id}/kb/resolution/analyze",
    response_model=ResolutionAnalysisResponse,
)
async def analyze_resolution(
    novel_id: UUID,
    request: ResolutionAnalyzeRequest,
    user_id: CurrentUserIdDep,
    service: Annotated[
        ResolutionAnalysisService,
        Depends(get_resolution_analyzer),
    ],
) -> ResolutionAnalysisResponse:
    """Run (or fetch) the duplicate detection analysis for one novel."""
    return await service.analyze(novel_id, UUID(user_id), refresh=request.refresh)


@router.get(
    "/novels/{novel_id}/kb/resolution/suggestions",
    response_model=ResolutionAnalysisResponse,
)
async def get_resolution_suggestions(
    novel_id: UUID,
    service: Annotated[
        ResolutionAnalysisService,
        Depends(get_resolution_analyzer),
    ],
) -> ResolutionAnalysisResponse:
    """Return the cached analysis without recomputing (empty when never analyzed)."""
    return await service.get_cached(novel_id)


@router.post(
    "/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/endorse",
    response_model=MergeExecutionResult,
)
async def endorse_resolution_suggestion(
    novel_id: UUID,
    suggestion_id: str,
    user_id: CurrentUserIdDep,
    service: Annotated[ResolutionEndorseService, Depends(get_endorse_service)],
    request: ResolutionEndorseRequest | None = None,
) -> MergeExecutionResult:
    """Re-validate the suggestion, execute the merge (spec §7), 409 when stale."""
    return await service.endorse(
        novel_id,
        UUID(user_id),
        suggestion_id,
        survivor_id=request.survivor_id if request else None,
    )


@router.post(
    "/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_resolution_suggestion(
    novel_id: UUID,
    suggestion_id: str,
    user_id: CurrentUserIdDep,
    service: Annotated[ResolutionEndorseService, Depends(get_endorse_service)],
) -> None:
    """Persist the dismissal (existing dismissed-suggestions pattern); 204."""
    await service.reject(novel_id, UUID(user_id), suggestion_id)
