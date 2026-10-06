"""Auth dependencies — JWT validation and current user extraction.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from narrare._app.config import Settings, get_settings
from narrare_core.llm.usage_events import usage_user_id

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

    # STATS-002 attribution (ADR-093 D3): bind the resolved user so emitted
    # LLM usage events carry user attribution. JWT ``sub`` is a string claim
    # (production: user UUID); a non-UUID value cannot be attributed → None,
    # mirroring the attribution middleware's malformed ⇒ None rule.
    try:
        usage_user_id.set(UUID(payload["sub"]))
    except ValueError:
        usage_user_id.set(None)

    return payload["sub"]


CurrentUserIdDep = Annotated[str, Depends(get_current_user_id)]
