"""
Shared FastAPI dependencies.

All reusable dependencies live here.
Domain-specific dependencies live in their respective domain modules.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.config import Settings, get_settings
from narrare._app.database import get_async_session
from narrare_core.llm import ModelRegistry
from narrare_core.prompts import MetaPromptLoader, PromptComposer, PromptRegistry

if TYPE_CHECKING:
    from narrare.generation.graph_store import PostgresGraphStateStore
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_service import UserProvidersService
    from narrare.templates.cascade_resolver import CascadeResolver
    from narrare.templates.repository import TemplateRepository
    from narrare.templates.service import TemplateApiService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

# ---------------------------------------------------------------------------
# LLM Model Registry (singleton)
# ---------------------------------------------------------------------------


@lru_cache
def _get_model_registry_instance() -> ModelRegistry:
    return ModelRegistry()


def get_model_registry() -> ModelRegistry:
    """Provide the shared LLM Model Registry instance."""
    return _get_model_registry_instance()


ModelRegistryDep = Annotated[ModelRegistry, Depends(get_model_registry)]

# ---------------------------------------------------------------------------
# Prompt system (singletons)
# ---------------------------------------------------------------------------


@lru_cache
def _get_prompt_registry_instance() -> PromptRegistry:
    return PromptRegistry()


def get_registry() -> PromptRegistry:
    """Provide the shared Prompt Registry instance."""
    return _get_prompt_registry_instance()


@lru_cache
def _get_meta_loader_instance() -> MetaPromptLoader:
    return MetaPromptLoader()


@lru_cache
def _get_composer_instance() -> PromptComposer:
    return PromptComposer(
        registry=_get_prompt_registry_instance(),
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

# ---------------------------------------------------------------------------
# AI Settings services (Task 10.5, Task 11.1)
# ---------------------------------------------------------------------------


def get_user_providers_service(session: SessionDep) -> UserProvidersService:
    """Factory for UserProvidersService."""
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare.settings.user_providers_service import UserProvidersService

    return UserProvidersService(
        providers_repo=UserProvidersRepository(session),
        ai_settings_repo=UserAiSettingsRepository(session),
    )


def get_user_ai_settings_service(session: SessionDep) -> UserAiSettingsService:
    """Factory for UserAiSettingsService."""
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_repository import UserProvidersRepository

    return UserAiSettingsService(
        ai_settings_repo=UserAiSettingsRepository(session),
        providers_repo=UserProvidersRepository(session),
    )


def get_project_ai_settings_service(session: SessionDep) -> ProjectAiSettingsService:
    """Factory for ProjectAiSettingsService."""
    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

    return ProjectAiSettingsService(
        project_ai_repo=ProjectAiSettingsRepository(session),
        user_ai_repo=UserAiSettingsRepository(session),
    )


def get_model_routing_resolver(session: SessionDep) -> ModelRoutingResolverImpl:
    """Factory for ModelRoutingResolverImpl (Task 11.1).

    Creates a resolver with all required repositories injected.
    """
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository

    return ModelRoutingResolverImpl(
        user_providers_repo=UserProvidersRepository(session),
        user_ai_settings_repo=UserAiSettingsRepository(session),
        project_ai_settings_repo=ProjectAiSettingsRepository(session),
    )


# ---------------------------------------------------------------------------
# Template services
# ---------------------------------------------------------------------------


def get_template_repository(session: SessionDep) -> TemplateRepository:
    """Factory for TemplateRepository."""
    from narrare.templates.repository import TemplateRepository

    return TemplateRepository(session)


def get_template_api_service(session: SessionDep) -> TemplateApiService:
    """Factory for TemplateApiService."""
    from narrare.templates.repository import TemplateRepository
    from narrare.templates.service import TemplateApiService

    repo = TemplateRepository(session)
    return TemplateApiService(repository=repo)


def get_cascade_resolver(session: SessionDep) -> CascadeResolver:
    """Factory for CascadeResolver with DB-backed repository."""
    from narrare.templates.cascade_resolver import CascadeResolver
    from narrare.templates.repository import TemplateRepository

    repo = TemplateRepository(session)
    return CascadeResolver(repository=repo)


# ---------------------------------------------------------------------------
# Graph State Store
# ---------------------------------------------------------------------------


from narrare.generation.graph_store import PostgresGraphStateStore  # noqa: E402


def get_graph_state_store(session: SessionDep) -> PostgresGraphStateStore:
    """Provide a PostgresGraphStateStore for the request.

    Wraps the async DB session so the store can persist and load
    WritingGraph checkpoints.
    """
    return PostgresGraphStateStore(session)


GraphStateStoreDep = Annotated[PostgresGraphStateStore, Depends(get_graph_state_store)]
