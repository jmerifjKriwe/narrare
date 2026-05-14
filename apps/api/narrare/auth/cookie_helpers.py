"""httpOnly cookie helpers for refresh token persistence.

Handles setting and clearing the httpOnly cookie that carries the refresh
token across page reloads.  Cookie logic lives here (HTTP concern) rather
than in the service layer (business logic).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import Response

    from narrare._app.config import Settings

logger = structlog.get_logger(__name__)

REFRESH_COOKIE_NAME = "narrare_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    """Set httpOnly cookie with the refresh token.

    Cookie attributes:
        - httpOnly: not accessible via JavaScript
        - secure: True in production (HTTPS only)
        - sameSite: lax (prevents CSRF while allowing top-level navigations)
        - path: /api/v1/auth (only sent to auth endpoints)
        - max_age: matches refresh_token_expire_days in seconds
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    logger.debug("refresh_cookie_set")


def clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie on auth failure."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )
    logger.debug("refresh_cookie_cleared")
