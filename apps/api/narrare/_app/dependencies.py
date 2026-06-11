"""
Shared FastAPI dependencies.

All reusable dependencies live here.
Domain-specific dependencies live in their respective domain modules.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, cast

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
    from narrare_core.ai_invocation import ContextEnricher
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


_preference_service_instance: PreferenceProvider | None = None
_preference_service_init_tried: bool = False


def _get_preference_service_instance() -> PreferenceProvider | None:
    """Create a PreferenceService if mem0 + credentials available, else None.

    Module-level singleton (mutable state, no ``@lru_cache``).
    Uses synchronous client creation for DI compatibility.
    The PreferenceService holds a long-lived mem0 client that accepts
    per-call user/project IDs — safe for shared use.
    """
    global _preference_service_instance, _preference_service_init_tried

    if _preference_service_init_tried:
        return _preference_service_instance

    _preference_service_init_tried = True

    # 1. Check mem0 is installed
    try:
        import mem0  # type: ignore[import-untyped]  # reason: mem0 has no type stubs

        del mem0
    except ImportError:
        logger.info("preference_service_disabled_mem0_not_installed")
        return None

    # 2. Detect provider from env
    from narrare.memory.dependencies import (
        _detect_provider_from_env,  # pyright: ignore[reportPrivateUsage]
    )

    provider_config = _detect_provider_from_env()
    if provider_config is None:
        logger.info("preference_service_disabled_no_credentials")
        return None

    # 3. Create mem0 client synchronously
    from narrare._app.config import get_settings
    from narrare_core.memory._null_client import NullMemoryClient
    from narrare_core.memory.mem0_client import create_memory_client_sync
    from narrare_core.memory.preference_service import PreferenceService

    settings = get_settings()
    client = create_memory_client_sync(
        provider=provider_config.provider,
        api_key=provider_config.api_key,
        base_url=provider_config.base_url,
        memory_model=settings.memory_llm_model,
        embedding_model=settings.memory_embedding_model,
    )

    if isinstance(client, NullMemoryClient):
        logger.warning(
            "preference_service_client_creation_failed",
            provider=provider_config.provider,
        )
        return None

    _preference_service_instance = cast(
        "PreferenceProvider",
        PreferenceService(mem0_client=client),
    )
    logger.info(
        "preference_service_initialized",
        provider=provider_config.provider,
    )
    return _preference_service_instance


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
        ``evidence_sink`` is a :class:`LoggingEvidenceSink` that records
        structured logs for each invocation. Can be disabled via log level.
    """
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
        LoggingEvidenceSink,
        RuntimeVariableValidatorImpl,
    )
    from narrare_core.ai_invocation.enrichers import (
        KBSuggestedContextEnricher,
        PreferenceContextEnricherImpl,
    )

    preference_service = _get_preference_service_instance()

    # Preference enricher is always wired — graceful degradation via None
    # provider (returns context unchanged, preference_status=MISSING).
    enrichers: list[ContextEnricher] = [
        PreferenceContextEnricherImpl(preference_provider=preference_service),
    ]

    # KB-suggested enricher runs before budget resolution so the resolver
    # can decide whether token budget allows KB context inclusion.
    enrichers.append(KBSuggestedContextEnricher(kb_provider=None))

    return InvocationPipeline(
        enrichers=enrichers,
        variable_validator=RuntimeVariableValidatorImpl(),
        budget_resolver=IntentOutputBudgetResolverImpl(),
        final_validator=FinalPromptValidatorImpl(),
        evidence_sink=LoggingEvidenceSink(),
    )


if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
