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
from narrare_core.agents.registry import AgentRegistry
from narrare_core.llm import ModelRegistry
from narrare_core.prompts import PromptComposer, PromptRegistry

if TYPE_CHECKING:
    from narrare.generation.graph_store import PostgresGraphStateStore
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_service import UserProvidersService
    from narrare.templates.cascade_resolver import CascadeResolver
    from narrare.templates.repository import TemplateRepository
    from narrare.templates.service import TemplateApiService
    from narrare_core.ai_invocation import ContextEnricher
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.memory.protocols import PreferenceProvider

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
# Agent Registry (singleton — module-level, NOT @lru_cache)
# ---------------------------------------------------------------------------

_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Provide the shared AgentRegistry singleton.

    AgentRegistry is mutable (has async state), so ``@lru_cache`` is not
    appropriate.  The module-level singleton pattern ensures a single
    instance across the application lifecycle.
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry(max_size=50, ttl_seconds=300.0)
    return _agent_registry


AgentRegistryDep = Annotated[AgentRegistry, Depends(get_agent_registry)]

# ---------------------------------------------------------------------------
# Prompt system (singletons)
# ---------------------------------------------------------------------------


@lru_cache
def _get_prompt_registry_instance() -> PromptRegistry:
    # Lazy import to keep BASE_DIR resolution unambiguous and avoid
    # circular-import concerns with the module-level import of Settings.
    from narrare._app.config import BASE_DIR

    return PromptRegistry(project_root=BASE_DIR)


def get_registry() -> PromptRegistry:
    """Provide the shared Prompt Registry instance."""
    return _get_prompt_registry_instance()


@lru_cache
def _get_preference_service_instance() -> PreferenceProvider | None:
    """Create a PreferenceService if mem0 is available, else None.

    Gracefully degrades when mem0 is not configured at the
    application level. Returns None so that PromptComposer skips
    preference auto-injection without crashing.

    When application-level mem0 configuration (provider + API key)
    is added to Settings, this factory will create a real
    PreferenceService backed by a mem0 client.
    """
    # Check whether the mem0 package is installed at all.
    try:
        import mem0  # type: ignore[import-untyped]

        del mem0  # only checking availability
    except ImportError:
        logger.info("preference_service_disabled_mem0_not_installed")
        return None

    # mem0 is installed but we lack system-level provider credentials.
    # Per-user mem0 clients are created on demand in the memory module
    # (see narrare.memory.router). Return None so the singleton
    # PromptComposer skips preference auto-injection gracefully.
    return None


@lru_cache
def _get_composer_instance() -> PromptComposer:
    return PromptComposer(
        registry=_get_prompt_registry_instance(),
        preference_service=_get_preference_service_instance(),
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


# ---------------------------------------------------------------------------
# Invocation Pipeline (singleton)
# ---------------------------------------------------------------------------


@lru_cache
def get_invocation_pipeline() -> InvocationPipeline:
    """Create InvocationPipeline with production implementations.

    Assembles the pipeline with all P0.3 components:
    - RuntimeVariableValidatorImpl (pre-composition checks)
    - IntentOutputBudgetResolverImpl (budget resolution)
    - FinalPromptValidatorImpl (post-composition checks)
    - PreferenceContextEnricherImpl (if preference service available)

    Note:
        ``evidence_sink`` is intentionally ``None`` — evidence recording
        is P0.3e scope. The pipeline still runs validation and enrichment.
    """
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
        RuntimeVariableValidatorImpl,
    )
    from narrare_core.ai_invocation.enrichers import PreferenceContextEnricherImpl

    preference_service = _get_preference_service_instance()

    enrichers: list[ContextEnricher] = []
    if preference_service is not None:
        enrichers.append(PreferenceContextEnricherImpl(preference_provider=preference_service))

    return InvocationPipeline(
        enrichers=enrichers,
        variable_validator=RuntimeVariableValidatorImpl(),
        budget_resolver=IntentOutputBudgetResolverImpl(),
        final_validator=FinalPromptValidatorImpl(),
        evidence_sink=None,  # P0.3e will add real evidence sink
    )


if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline


# ---------------------------------------------------------------------------
# System-default model config (no user context)
# ---------------------------------------------------------------------------


def build_system_default_config(
    category: str = "writing",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ResolvedModelConfig:
    """Build a ResolvedModelConfig from system defaults (Settings).

    For use in startup/background tasks that have no user context.
    Uses ``Settings.default_writing_model`` or ``Settings.default_analysis_model``
    and resolves the provider via ``infer_provider()``.

    Args:
        category: "writing" or "analysis" — selects which Settings default to use.
        temperature: Generation temperature.
        max_tokens: Maximum output tokens.

    Returns:
        Fully resolved ResolvedModelConfig with valid provider_name.
    """
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._providers.registry import infer_provider

    settings = get_settings()
    model_id = (
        settings.default_writing_model if category == "writing" else settings.default_analysis_model
    )
    provider_name = infer_provider(model_id)

    return ResolvedModelConfig(
        provider_name=provider_name,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )
