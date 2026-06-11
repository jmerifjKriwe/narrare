"""Shared FastAPI dependencies — re-export hub.

All reusable dependencies are defined in focused sub-modules and
re-exported here for backward compatibility.  Domain-specific
dependencies live in their respective domain modules.

Sub-modules:
    dependencies_registries — ModelRegistry, AgentRegistry
    dependencies_prompts — PromptRegistry, PreferenceService, Composer
    dependencies_auth — JWT validation, current user
    dependencies_pipeline — InvocationPipeline
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.config import Settings, get_settings
from narrare._app.database import get_async_session
from narrare._app.dependencies_auth import CurrentUserIdDep, get_current_user_id
from narrare._app.dependencies_pipeline import get_invocation_pipeline
from narrare._app.dependencies_prompts import (
    ComposerDep,
    _get_composer_instance,  # pyright: ignore[reportPrivateUsage]
    _get_preference_service_instance,  # pyright: ignore[reportPrivateUsage]
    _get_prompt_registry_instance,  # pyright: ignore[reportPrivateUsage]
    get_composer,
    get_registry,
)
from narrare._app.dependencies_registries import (
    AgentRegistryDep,
    ModelRegistryDep,
    _get_model_registry_instance,  # pyright: ignore[reportPrivateUsage]
    get_agent_registry,
    get_model_registry,
)

# ---------------------------------------------------------------------------
# Settings & Session (defined here — fundamental, no circular imports)
# ---------------------------------------------------------------------------

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


__all__ = [
    "AgentRegistryDep",
    "ComposerDep",
    "CurrentUserIdDep",
    "ModelRegistryDep",
    "SessionDep",
    "SettingsDep",
    "_get_composer_instance",
    "_get_model_registry_instance",
    "_get_preference_service_instance",
    "_get_prompt_registry_instance",
    "get_agent_registry",
    "get_composer",
    "get_current_user_id",
    "get_invocation_pipeline",
    "get_model_registry",
    "get_registry",
]
