"""
Shared FastAPI dependencies.

All reusable dependencies live here.
Domain-specific dependencies live in their respective domain modules.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.config import Settings, get_settings
from narrare._app.database import get_async_session
from narrare_core.llm import LLMGateway
from narrare_core.prompts import MetaPromptLoader, PromptComposer, PromptRegistry

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

# ---------------------------------------------------------------------------
# LLM Gateway (singleton)
# ---------------------------------------------------------------------------


@lru_cache
def _get_gateway_instance() -> LLMGateway:
    return LLMGateway()


def get_gateway() -> LLMGateway:
    """Provide the shared LLM Gateway instance."""
    return _get_gateway_instance()


GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]

# ---------------------------------------------------------------------------
# Prompt system (singletons)
# ---------------------------------------------------------------------------


@lru_cache
def _get_registry_instance() -> PromptRegistry:
    return PromptRegistry()


@lru_cache
def _get_meta_loader_instance() -> MetaPromptLoader:
    return MetaPromptLoader()


@lru_cache
def _get_composer_instance() -> PromptComposer:
    return PromptComposer(
        registry=_get_registry_instance(),
        meta_loader=_get_meta_loader_instance(),
    )


def get_composer() -> PromptComposer:
    """Provide the shared Prompt Composer instance."""
    return _get_composer_instance()


ComposerDep = Annotated[PromptComposer, Depends(get_composer)]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    settings: SettingsDep,
) -> str:
    """
    Extract and validate JWT, return user_id.

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
