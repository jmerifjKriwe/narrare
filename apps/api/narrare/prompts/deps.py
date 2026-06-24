"""PROMPT-003 prompt UX dependency injection — service factories.

Extracted from ``router_prompt_ux.py`` for RULE-04 (router hard limit
150 lines). Mirrors the ``writing/deps.py`` pattern: thin wiring, no
business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.prompts.history_service import PromptHistoryApiService
    from narrare.prompts.live_test_service import PromptLiveTestApiService
    from narrare.prompts.preview_service import (
        PromptPreviewApiService,
        PromptResetApiService,
    )


async def get_preview_service() -> PromptPreviewApiService:
    """Wire ``PromptPreviewApiService`` with the Core provider-free preview."""
    from narrare._app.dependencies import get_composer, get_registry
    from narrare.prompts.preview_service import PromptPreviewApiService
    from narrare_core.prompts.preview import PromptPreviewService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    composer = get_composer()
    core = PromptPreviewService(composer=composer, registry=registry)
    return PromptPreviewApiService(core=core)


async def get_reset_service() -> PromptResetApiService:
    """Wire ``PromptResetApiService`` with the Core management service."""
    from narrare._app.dependencies import get_registry
    from narrare.prompts.preview_service import PromptResetApiService
    from narrare_core.prompts.management import PromptManagementService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    core = PromptManagementService(registry=registry)
    return PromptResetApiService(core=core)


async def get_live_test_service(session: AsyncSession) -> PromptLiveTestApiService:
    """Wire ``PromptLiveTestApiService`` with real resolver + registry + agent.

    Task 11 wiring: the resolver IS the provider gate (raises
    ``ConfigurationError`` when no provider is configured). The agent
    factory creates a ``PromptLiveTestAgent`` per request.
    """
    from narrare._app.dependencies import get_composer, get_model_registry, get_registry
    from narrare._app.dependencies_services import get_model_routing_resolver
    from narrare.prompts.live_test_service import PromptLiveTestApiService
    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestAgent
    from narrare_core.prompts.preview import PromptPreviewService

    model_registry = get_model_registry()
    prompt_registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    composer = get_composer()
    resolver = get_model_routing_resolver(session)
    preview = PromptPreviewService(composer=composer, registry=prompt_registry)

    def agent_factory(*, model: object) -> PromptLiveTestAgent:
        return PromptLiveTestAgent(model=model)  # type: ignore[arg-type]

    return PromptLiveTestApiService(
        resolver=resolver,
        registry=model_registry,
        preview=preview,
        agent_factory=agent_factory,
    )


async def get_prompt_history_service(session: AsyncSession) -> PromptHistoryApiService:
    """Wire ``PromptHistoryApiService`` (CR-AUFG-07-19).

    Composes the core file-based ``PromptManagementService`` (authoritative
    cascade source) with the DB-backed ``PromptHistoryRepository`` bound to
    the request session.  The active override stays a FILE; revisions are a
    secondary record.  Retention is driven by
    ``Settings.prompt_history_retention_limit`` (RULE-18 operator-config).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_registry
    from narrare.prompts.history_service import PromptHistoryApiService
    from narrare.prompts.repository import PromptHistoryRepository
    from narrare_core.prompts.management import PromptManagementService

    prompt_registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    core = PromptManagementService(registry=prompt_registry)
    repo = PromptHistoryRepository(session)
    settings = get_settings()
    return PromptHistoryApiService(
        core=core,
        repo=repo,
        retention_limit=settings.prompt_history_retention_limit,
    )
