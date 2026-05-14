"""Auth routes — thin, delegates immediately to AuthService."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi_limiter.depends import RateLimiter as _RateLimiterDep
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.config import Settings, get_settings
from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.auth.cookie_helpers import clear_refresh_cookie, set_refresh_cookie
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from narrare.auth.service import AuthService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

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
    response: Response,
    service: AuthService = Depends(_get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Register a new user account."""
    tokens = await service.register(request)
    set_refresh_cookie(response, tokens.refresh_token, settings)
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(_login_rate_limiter)],
)
async def login(
    request: LoginRequest,
    response: Response,
    service: AuthService = Depends(_get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Authenticate and receive tokens."""
    tokens = await service.login(request)
    set_refresh_cookie(response, tokens.refresh_token, settings)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    narrare_refresh: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Exchange a refresh token for new tokens.

    Reads from httpOnly cookie (preferred) or request body (backward compat).
    """
    refresh_token = narrare_refresh
    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception:
            logger.debug("refresh_no_cookie_or_body")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    try:
        tokens = await service.refresh(refresh_token)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            clear_refresh_cookie(response)
        raise

    set_refresh_cookie(response, tokens.refresh_token, settings)
    return tokens


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    from uuid import UUID

    from sqlalchemy import func, select

    from narrare.settings.models import UserProvider

    repo = AuthRepository(session)
    uid = UUID(user_id)
    user = await repo.get_by_id(uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if user has any configured providers (determines setup completion)
    result = await session.execute(
        select(func.count()).select_from(UserProvider).where(UserProvider.user_id == uid)
    )
    provider_count = result.scalar() or 0

    resp = UserResponse.model_validate(user)
    resp.has_providers = provider_count > 0
    return resp
