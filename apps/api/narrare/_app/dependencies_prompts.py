"""Prompt system singletons — Registry, PreferenceService, Composer.

Extracted from ``dependencies.py`` for RULE-04 modularisation.

The mem0 boundary is encapsulated here:
- ``is_mem0_available()`` from ``narrare_core.memory.availability`` replaces
  the direct ``import mem0`` that previously lived in ``_app/dependencies.py``.
- ``detect_provider_from_env()`` from ``narrare_core.memory.availability``
  replaces the private ``_detect_provider_from_env`` import from
  ``memory/dependencies.py``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, cast

import structlog
from fastapi import Depends

from narrare_core.memory.availability import (
    detect_provider_from_env,
    is_mem0_available,
)
from narrare_core.prompts import PromptComposer, PromptRegistry
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from narrare_core.memory.protocols import PreferenceProvider

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt Registry (singleton)
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


# ---------------------------------------------------------------------------
# Preference Service (singleton — mem0-backed, graceful degradation)
# ---------------------------------------------------------------------------

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

    # 1. Check mem0 is installed (encapsulated in core adapter)
    if not is_mem0_available():
        logger.info("preference_service_disabled_mem0_not_installed")
        return None

    # 2. Detect provider from env (public API from core adapter)
    provider_config = detect_provider_from_env()
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
        if get_core_settings().e2e_test:
            # E2E: NullMemoryClient is an intentional stub (see
            # mem0_client.create_memory_client_sync). Wrap it in a
            # PreferenceService so the preference path runs through its
            # NORMAL code path (search → empty results → empty profile)
            # rather than being skipped — exercising real code without any
            # OpenAI embedding calls. Mirrors how TestModel keeps the agent
            # running with a fake model instead of short-circuiting it.
            logger.info("preference_service_e2e_stub_active")
        else:
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


# ---------------------------------------------------------------------------
# Prompt Composer (singleton)
# ---------------------------------------------------------------------------


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
