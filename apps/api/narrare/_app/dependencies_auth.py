"""Auth dependencies — JWT validation and current user extraction.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from narrare._app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Extract and validate JWT, return user_id.

    Raises HTTP 401 if token is missing or invalid.
    """
    # Import here to avoid circular imports
    from narrare.auth.security import verify_access_token

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(credentials.credentials, settings.secret_key)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload["sub"]


CurrentUserIdDep = Annotated[str, Depends(get_current_user_id)]
