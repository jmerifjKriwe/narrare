"""Adaptive Context REST endpoints — thin delegation to AdaptiveContextService.

Four endpoints (all require authentication, all project-scoped):
- GET  /api/v1/adaptive/{project_id}/context
- POST /api/v1/adaptive/{project_id}/toggle
- POST /api/v1/adaptive/{project_id}/weights
- GET  /api/v1/adaptive/{project_id}/snapshots   (ADR-070 — recent evidence)

The router delegates immediately to the service; no business logic here
(RULE-06).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.adaptive.dependencies import get_adaptive_context_service
from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSnapshotsResponse,
    AdaptiveToggleInput,
    AdaptiveWeightsInput,
)

if TYPE_CHECKING:
    from narrare.adaptive.service import AdaptiveContextService

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


@router.get(
    "/{project_id}/context",
    response_model=AdaptiveContextResponse,
    status_code=status.HTTP_200_OK,
)
async def get_adaptive_context(
    project_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: AdaptiveContextService = Depends(get_adaptive_context_service),
) -> AdaptiveContextResponse:
    """Return the current adaptive state for the dashboard."""
    return await service.get_context(project_id=project_id, user_id=uuid.UUID(user_id))


@router.post(
    "/{project_id}/toggle",
    response_model=AdaptiveSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def toggle_adaptive(
    project_id: uuid.UUID,
    body: AdaptiveToggleInput,
    user_id: CurrentUserIdDep,
    service: AdaptiveContextService = Depends(get_adaptive_context_service),
) -> AdaptiveSettingsResponse:
    """Toggle adaptivity on/off for the project."""
    return await service.set_enabled(
        project_id=project_id, user_id=uuid.UUID(user_id), enabled=body.enabled
    )


@router.post(
    "/{project_id}/weights",
    response_model=AdaptiveSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_adaptive_weights(
    project_id: uuid.UUID,
    body: AdaptiveWeightsInput,
    user_id: CurrentUserIdDep,
    service: AdaptiveContextService = Depends(get_adaptive_context_service),
) -> AdaptiveSettingsResponse:
    """Update the four adaptive weights (clamped to [0.0, 1.0])."""
    return await service.set_weights(
        project_id=project_id, user_id=uuid.UUID(user_id), weights=body
    )


@router.get(
    "/{project_id}/snapshots",
    response_model=AdaptiveSnapshotsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_adaptive_snapshots(
    project_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    limit: int = 20,
    service: AdaptiveContextService = Depends(get_adaptive_context_service),
) -> AdaptiveSnapshotsResponse:
    """Return recent adaptive snapshots for the dashboard timeline (ADR-070)."""
    return await service.get_adaptive_snapshots(
        project_id=project_id, user_id=uuid.UUID(user_id), limit=limit
    )
