"""Auth profile routes — GET /me for current user."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import UserResponse
from narrare.settings.user_providers_repository import UserProvidersRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> UserResponse:
    """Return the current authenticated user's profile."""
    uid = UUID(user_id)

    auth_repo = AuthRepository(session)
    user = await auth_repo.get_by_id(uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    providers_repo = UserProvidersRepository(session)
    provider_count = await providers_repo.count_by_user(uid)

    resp = UserResponse.model_validate(user)
    resp.has_providers = provider_count > 0
    return resp
