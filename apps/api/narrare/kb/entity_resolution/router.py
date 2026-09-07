"""KB entity-resolution routes — analyze + suggestions (ADR-085 P3, spec §7).

Thin delegation only (RULE-06/12): the scope guard runs as a router-level
dependency, and both handlers forward to the analysis service. The
endorse/reject surface lands in Task 10 (spec §9 P4).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
from narrare.kb.entity_resolution.dependencies import (
    get_resolution_analyzer,
    verify_novel_scope,
)
from narrare.kb.entity_resolution.schemas_resolution import (
    ResolutionAnalysisResponse,
    ResolutionAnalyzeRequest,
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
