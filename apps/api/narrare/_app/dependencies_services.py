"""Service-layer dependency factories and type aliases.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
Contains factory functions for AI settings, templates, graph-state,
and system-default model config.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from narrare._app.config import get_settings
from narrare._app.dependencies import SessionDep  # noqa: TC001 - runtime FastAPI DI annotation

if TYPE_CHECKING:
    from narrare.generation.graph_store import PostgresGraphStateStore
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_service import UserProvidersService
    from narrare.templates.cascade_resolver import CascadeResolver
    from narrare.templates.repository import TemplateRepository
    from narrare.templates.service import TemplateApiService
    from narrare_core.llm import ResolvedModelConfig

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
# System model category — typed policy-boundary for system default config
# ---------------------------------------------------------------------------


class SystemModelCategory(enum.StrEnum):
    """Typed category selector for :func:`build_system_default_config`.

    Replaces raw ``"writing"`` / ``"analysis"`` string branching as the
    policy-boundary between default model lookups. A plain ``str`` is
    rejected at the boundary for type safety (CR-AUFG-08-08).
    """

    WRITING = "writing"
    ANALYSIS = "analysis"


# ---------------------------------------------------------------------------
# System-default model config (no user context)
# ---------------------------------------------------------------------------


def build_system_default_config(
    category: SystemModelCategory = SystemModelCategory.WRITING,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ResolvedModelConfig:
    """Build a ResolvedModelConfig from system defaults (Settings).

    For use in startup/background tasks that have no user context.
    Uses ``Settings.default_writing_model`` or ``Settings.default_analysis_model``
    and resolves the provider via ``infer_provider()``.

    Args:
        category: ``WRITING`` or ``ANALYSIS`` — selects which Settings default
            to use. A plain string is rejected for type safety.
        temperature: Generation temperature.
        max_tokens: Maximum output tokens.

    Returns:
        Fully resolved ResolvedModelConfig with valid provider_name.
    """
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._providers.registry import infer_provider

    settings = get_settings()
    model_id = (
        settings.default_writing_model
        if category == SystemModelCategory.WRITING
        else settings.default_analysis_model
    )
    provider_name = infer_provider(model_id)

    return ResolvedModelConfig(
        provider_name=provider_name,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )
