"""Token limits routes — CRUD for per-user and per-project overrides.

All routes under ``/settings/token-limits``. Delegates immediately
to TokenLimitsService — no business logic here (RULE-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from narrare._app.config import get_settings
from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.settings.token_limits.contracts import DEFAULT_TIER_PERCENTAGES
from narrare.settings.token_limits.repository import (
    ProjectTokenLimitsRepository,
    UserTokenLimitsRepository,
)
from narrare.settings.token_limits.schemas import (
    TokenLimitOverridesResponse,
    UpdateTokenLimitsRequest,
)

if TYPE_CHECKING:
    from narrare._app.config import Settings
    from narrare.settings.token_limits.service import TokenLimitsService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings/token-limits", tags=["token-limits"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_token_limits_service(
    session: SessionDep,
    config: Settings = Depends(get_settings),
) -> TokenLimitsService:
    """Factory for TokenLimitsService with DB-backed repositories."""
    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=config,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=TokenLimitOverridesResponse)
async def get_resolved_limits(
    user_id: CurrentUserIdDep,
    project_id: str | None = None,
    service: TokenLimitsService = Depends(_get_token_limits_service),
) -> TokenLimitOverridesResponse:
    """Get resolved token limits (merged across all layers).

    Queries are optional:
    - ``project_id``: Include project-level overrides.
    """
    limits = await service.get_resolved_limits(
        user_id=user_id,
        project_id=project_id,
    )
    return TokenLimitOverridesResponse(
        output_limit=limits.output_limit,
        token_profile=limits.token_profile,
        tier_percentages=limits.tier_percentages or dict(DEFAULT_TIER_PERCENTAGES),
        ws_timeout=limits.ws_timeout,
        retry_max_attempts=limits.retry_max_attempts,
        retry_base_delay=limits.retry_base_delay,
    )


@router.put("/user", status_code=status.HTTP_204_NO_CONTENT)
async def update_user_limits(
    request: UpdateTokenLimitsRequest,
    user_id: CurrentUserIdDep,
    service: TokenLimitsService = Depends(_get_token_limits_service),
) -> None:
    """Update user-level token limit overrides."""
    overrides = request.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    await service.update_user_limits(
        user_id=user_id,
        overrides=overrides,
    )


@router.put("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_project_limits(
    project_id: str,
    request: UpdateTokenLimitsRequest,
    user_id: CurrentUserIdDep,
    service: TokenLimitsService = Depends(_get_token_limits_service),
) -> None:
    """Update project-level token limit overrides."""
    overrides = request.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    await service.update_project_limits(
        project_id=project_id,
        overrides=overrides,
    )
