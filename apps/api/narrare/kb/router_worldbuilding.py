"""Worldbuilding analysis routes — thin delegation to WorldbuildingService (RULE-06).

Provides two endpoints:

- ``POST /novels/{novel_id}/kb/worldbuilding/analyze`` — run analysis
- ``POST /novels/{novel_id}/kb/worldbuilding/apply`` — apply selected connections

The apply endpoint requires the client to send the full analysis response
alongside the finding indices so the service can look up entity IDs and
relationship types.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_worldbuilding_service
from narrare.kb.worldbuilding_contracts import (
    WorldbuildingAnalysisRequest,
    WorldbuildingAnalysisResponse,
    WorldbuildingApplyRequest,
    WorldbuildingApplyResponse,
)
from narrare.kb.worldbuilding_service import WorldbuildingService

router = APIRouter(tags=["kb"])


class WorldbuildingApplyRequestBody(BaseModel):
    """Router-level request body for applying connections.

    Combines the finding indices with the full analysis response
    needed by the service to look up entity IDs and relationship types.
    """

    finding_indices: list[int]
    analysis: WorldbuildingAnalysisResponse


@router.post(
    "/novels/{novel_id}/kb/worldbuilding/analyze",
    response_model=WorldbuildingAnalysisResponse,
    summary="Analyze the project's worldbuilding health",
)
async def analyze_worldbuilding(
    novel_id: uuid.UUID,
    request: WorldbuildingAnalysisRequest,
    user_id: CurrentUserIdDep,
    service: Annotated[WorldbuildingService, Depends(get_worldbuilding_service)],
) -> WorldbuildingAnalysisResponse:
    """Analyze the project's worldbuilding health.

    Runs gap detection, connection suggestion, and/or consistency
    checking based on request options. Results are cached (10min TTL).
    """
    return await service.analyze(
        novel_id=novel_id,
        request=request,
        user_id=uuid.UUID(user_id),
    )


@router.post(
    "/novels/{novel_id}/kb/worldbuilding/apply",
    response_model=WorldbuildingApplyResponse,
    summary="Apply selected connection suggestions as relationships",
)
async def apply_worldbuilding_connections(
    novel_id: uuid.UUID,
    body: WorldbuildingApplyRequestBody,
    user_id: CurrentUserIdDep,
    service: Annotated[WorldbuildingService, Depends(get_worldbuilding_service)],
) -> WorldbuildingApplyResponse:
    """Apply selected connection suggestions as KB relationships.

    The client sends the finding indices and the full analysis response
    (previously obtained from ``/analyze``) so the service can look up
    entity IDs and relationship types.
    """
    return await service.apply_connections(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        request=WorldbuildingApplyRequest(finding_indices=body.finding_indices),
        analysis=body.analysis,
    )
