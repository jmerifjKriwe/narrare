"""Auth profile routes — GET /me for current user."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from narrare._app.config import Settings, get_settings
from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import UserResponse
from narrare.auth.service import AuthService
from narrare.settings.user_providers_repository import UserProvidersRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(
    session: SessionDep,
    settings: Settings = Depends(get_settings),
) -> AuthService:
    """Provide AuthService with auth + user-providers repositories."""
    return AuthService(
        repo=AuthRepository(session),
        settings=settings,
        providers_repo=UserProvidersRepository(session),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserIdDep,
    service: AuthService = Depends(_get_auth_service),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    return await service.get_current_user_profile(uuid.UUID(user_id))
