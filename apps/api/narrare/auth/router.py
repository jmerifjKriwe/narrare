"""Auth routes — thin, delegates immediately to AuthService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter as _RateLimiterDep
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.config import Settings, get_settings
from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from narrare.auth.service import AuthService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(
    session: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(repo=AuthRepository(session), settings=settings)


def _register_rate_limiter() -> _RateLimiterDep:
    """Lazy rate limiter for registration — 3 requests/minute."""
    return _RateLimiterDep(Limiter(Rate(3, Duration.MINUTE * 1)))


def _login_rate_limiter() -> _RateLimiterDep:
    """Lazy rate limiter for login — 5 requests/minute."""
    return _RateLimiterDep(Limiter(Rate(5, Duration.MINUTE * 1)))


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_register_rate_limiter)],
)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """Register a new user account."""
    return await service.register(request)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(_login_rate_limiter)],
)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """Authenticate and receive tokens."""
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """Exchange a refresh token for new tokens."""
    return await service.refresh(request.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    from uuid import UUID

    from fastapi import HTTPException, status

    repo = AuthRepository(session)
    user = await repo.get_by_id(UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)
