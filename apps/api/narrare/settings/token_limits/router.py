"""Token limits routes — CRUD for per-user and per-project overrides.

All routes under ``/settings/token-limits``. Delegates immediately to
TokenLimitsService / TokenLimitsMetadataService — no business logic here
(RULE-06). DI factories and response-shaping helpers live in
:mod:`narrare.settings.token_limits.dependencies` (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from narrare.settings.token_limits.contracts import DEFAULT_TIER_PERCENTAGES
from narrare.settings.token_limits.dependencies import (
    CurrentUserIdDep,
    get_token_limits_metadata_service,
    get_token_limits_service,
    resolve_model_metadata,
)
from narrare.settings.token_limits.schemas import (
    TokenLimitOverridesResponse,
    UpdateTokenLimitsRequest,
    build_catalog,
)

if TYPE_CHECKING:
    from narrare.settings.token_limits.metadata_service import (
        TokenLimitsMetadataService,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings/token-limits", tags=["token-limits"])


@router.get("/", response_model=TokenLimitOverridesResponse)
async def get_resolved_limits(
    user_id: CurrentUserIdDep,
    project_id: str | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    intent: str | None = None,
    service: TokenLimitsService = Depends(get_token_limits_service),
    metadata_service: TokenLimitsMetadataService = Depends(get_token_limits_metadata_service),
) -> TokenLimitOverridesResponse:
    """Get resolved token limits (merged across all layers).

    Optional query parameters:
    - ``project_id``: Include project-level overrides.
    - ``provider`` + ``model_id``: Attach model calibration metadata.
    - ``intent`` (with provider/model): Attach suitability metadata.
    """
    limits = await service.get_resolved_limits(
        user_id=user_id,
        project_id=project_id,
    )
    calibration, suitability = resolve_model_metadata(
        metadata_service,
        provider=provider,
        model_id=model_id,
        intent=intent,
        requested_output_tokens=limits.effective_output_limit,
    )
    return TokenLimitOverridesResponse(
        output_limit=limits.output_limit,
        token_profile=limits.token_profile,
        effective_output_limit=limits.effective_output_limit,
        tier_percentages=limits.tier_percentages or dict(DEFAULT_TIER_PERCENTAGES),
        ws_timeout=limits.ws_timeout,
        metadata=build_catalog(),
        calibration=calibration,
        suitability=suitability,
    )


@router.put("/user", status_code=status.HTTP_204_NO_CONTENT)
async def update_user_limits(
    request: UpdateTokenLimitsRequest,
    user_id: CurrentUserIdDep,
    service: TokenLimitsService = Depends(get_token_limits_service),
) -> None:
    """Update user-level token limit overrides."""
    overrides = request.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    await service.update_user_limits(user_id=user_id, overrides=overrides)


@router.put("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_project_limits(
    project_id: str,
    request: UpdateTokenLimitsRequest,
    user_id: CurrentUserIdDep,
    service: TokenLimitsService = Depends(get_token_limits_service),
) -> None:
    """Update project-level token limit overrides."""
    overrides = request.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    await service.update_project_limits(project_id=project_id, overrides=overrides)
