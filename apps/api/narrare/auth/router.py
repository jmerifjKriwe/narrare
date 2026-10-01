"""Auth routes — thin, delegates immediately to AuthService."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pyrate_limiter import Duration, Rate

from narrare._app.config import Settings, get_settings
from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.rate_limiter_dep import RateLimiter as _RateLimiterDep
from narrare._app.rate_limiter_dep import SelfPruningLimiter
from narrare.auth.cookie_helpers import clear_refresh_cookie, set_refresh_cookie
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, WsTicketResponse
from narrare.auth.service import AuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(
    session: SessionDep,
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(repo=AuthRepository(session), settings=settings)


_REGISTER_LIMITER = _RateLimiterDep(SelfPruningLimiter(Rate(3, Duration.MINUTE * 1)))
"""Module-level rate limiter for registration — 3 requests/minute.

Must be a module-level singleton (not a factory function) so the same
``Limiter`` instance is shared across all requests.  A factory function
would create a new ``Limiter`` per request and rate limits would never
accumulate — see ``narrare._app.rate_limits`` docstring for details.
"""

_LOGIN_LIMITER = _RateLimiterDep(SelfPruningLimiter(Rate(5, Duration.MINUTE * 1)))
"""Module-level rate limiter for login — 5 requests/minute.

Same singleton requirement as ``_REGISTER_LIMITER``.
"""


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_REGISTER_LIMITER)],
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
    dependencies=[Depends(_LOGIN_LIMITER)],
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    narrare_refresh: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_auth_service),
) -> None:
    """Logout: clear the refresh token cookie.

    No authentication required — clears the cookie even if the access
    token is already expired or missing.
    """
    await service.logout()
    clear_refresh_cookie(response)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def issue_ws_ticket(
    user_id: CurrentUserIdDep,
    service: AuthService = Depends(_get_auth_service),
) -> WsTicketResponse:
    """Issue a single-use, 60 s WebSocket handshake ticket (ADR-084).

    Bearer-gated (no ambient credential → no CSRF surface, hence no
    dedicated limiter — same stance as /auth/refresh). The writing WS
    handshake consumes the ticket as the ``token`` query param and derives
    the session identity from it.
    """
    return service.issue_ws_ticket(uuid.UUID(user_id))
