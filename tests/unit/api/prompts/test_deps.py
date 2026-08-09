"""Unit tests for ``narrare.prompts.deps`` — DI service factories.

The factories are thin wiring (RULE-06): each composes a Core service with
app-level dependencies and returns the API service. They are exercised
end-to-end by the integration suite; these tests pin the wiring at the unit
level so a mis-wired factory is caught without spinning up the app.

All app dependencies and Core service classes are replaced with fakes, so no
filesystem, DB, or provider is touched.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import narrare._app.config as app_config
import narrare._app.dependencies as app_deps
import narrare._app.dependencies_services as app_services
import narrare_core.agents.prompt_live_test_agent as agent_mod
import narrare_core.prompts.management as mgmt_mod
import narrare_core.prompts.preview as preview_mod
from narrare._app.settings_model import Settings
from narrare.prompts.deps import (
    get_live_test_service,
    get_preview_service,
    get_prompt_history_service,
    get_reset_service,
)
from narrare.prompts.history_service import PromptHistoryApiService
from narrare.prompts.live_test_service import PromptLiveTestApiService
from narrare.prompts.preview_service import (
    PromptPreviewApiService,
    PromptResetApiService,
)
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry


@pytest.fixture
def mocked_wiring(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace every external collaborator the factories reach for.

    Returns the sentinels so individual tests can assert wiring.

    Every mock is built with ``spec=<real class>`` (RULE-TEST-01) so attribute
    drift is caught: a mis-wired factory that reaches for a non-existent
    collaborator method fails loudly instead of silently no-op'ing.
    """
    registry = MagicMock(spec=PromptRegistry, name="PromptRegistry")
    composer = MagicMock(spec=PromptComposer, name="PromptComposer")
    model_registry = MagicMock(spec=ModelRegistry, name="ModelRegistry")
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    settings = MagicMock(spec=Settings, name="Settings")
    settings.prompt_history_retention_limit = 42

    monkeypatch.setattr(app_deps, "get_registry", lambda: registry)
    monkeypatch.setattr(app_deps, "get_composer", lambda: composer)
    monkeypatch.setattr(app_deps, "get_model_registry", lambda: model_registry)
    monkeypatch.setattr(app_services, "get_model_routing_resolver", lambda session: resolver)
    monkeypatch.setattr(app_config, "get_settings", lambda: settings)

    # Core service classes become recording fakes. ``spec`` is read from the
    # real class via the module alias (still the genuine class here — the
    # monkeypatch runs immediately afterwards).
    core_preview = MagicMock(
        spec=preview_mod.PromptPreviewService,
        name="PromptPreviewService",
        return_value=MagicMock(spec=preview_mod.PromptPreviewService, name="core_preview"),
    )
    core_mgmt = MagicMock(
        spec=mgmt_mod.PromptManagementService,
        name="PromptManagementService",
        return_value=MagicMock(spec=mgmt_mod.PromptManagementService, name="core_mgmt"),
    )
    monkeypatch.setattr(preview_mod, "PromptPreviewService", core_preview)
    monkeypatch.setattr(mgmt_mod, "PromptManagementService", core_mgmt)
    # Agent class (used by the live-test factory closure).
    agent_cls = MagicMock(spec=agent_mod.PromptLiveTestAgent, name="PromptLiveTestAgent")
    monkeypatch.setattr(agent_mod, "PromptLiveTestAgent", agent_cls)

    return {
        "registry": registry,
        "composer": composer,
        "model_registry": model_registry,
        "resolver": resolver,
        "settings": settings,
        "core_preview": core_preview,
        "core_mgmt": core_mgmt,
        "agent_cls": agent_cls,
    }


# ---------------------------------------------------------------------------
# get_preview_service
# ---------------------------------------------------------------------------


async def test_get_preview_service_wires_core_preview_with_registry_and_composer(
    mocked_wiring: dict[str, MagicMock],
) -> None:
    service = await get_preview_service()

    assert isinstance(service, PromptPreviewApiService)
    # Core preview service built from the shared registry + composer.
    mocked_wiring["core_preview"].assert_called_once_with(
        registry=mocked_wiring["registry"],
        composer=mocked_wiring["composer"],
    )


# ---------------------------------------------------------------------------
# get_reset_service
# ---------------------------------------------------------------------------


async def test_get_reset_service_wires_core_management_with_registry(
    mocked_wiring: dict[str, MagicMock],
) -> None:
    service = await get_reset_service()

    assert isinstance(service, PromptResetApiService)
    mocked_wiring["core_mgmt"].assert_called_once_with(registry=mocked_wiring["registry"])


# ---------------------------------------------------------------------------
# get_live_test_service
# ---------------------------------------------------------------------------


async def test_get_live_test_service_wires_resolver_registry_preview_and_agent_factory(
    mocked_wiring: dict[str, MagicMock],
) -> None:
    session = MagicMock(spec=AsyncSession, name="AsyncSession")
    service = await get_live_test_service(session)

    assert isinstance(service, PromptLiveTestApiService)
    # The model-routing resolver is resolved against the request session.
    assert service._resolver is mocked_wiring["resolver"]  # type: ignore[attr-defined]
    assert service._registry is mocked_wiring["model_registry"]  # type: ignore[attr-defined]
    # Core preview is built for the live-test preview step.
    mocked_wiring["core_preview"].assert_called_once_with(
        registry=mocked_wiring["registry"],
        composer=mocked_wiring["composer"],
    )
    # agent_factory produces a PromptLiveTestAgent from a model.
    model = object()
    built_agent = service._agent_factory(model=model)  # type: ignore[attr-defined]
    mocked_wiring["agent_cls"].assert_called_once_with(model=model)
    assert built_agent is mocked_wiring["agent_cls"].return_value


# ---------------------------------------------------------------------------
# get_prompt_history_service
# ---------------------------------------------------------------------------


async def test_get_prompt_history_service_applies_retention_limit_from_settings(
    mocked_wiring: dict[str, MagicMock],
) -> None:
    session = MagicMock(spec=AsyncSession, name="AsyncSession")
    service = await get_prompt_history_service(session, event_publisher=None)

    assert isinstance(service, PromptHistoryApiService)
    assert service._retention_limit == 42  # type: ignore[attr-defined]
    mocked_wiring["core_mgmt"].assert_called_once_with(registry=mocked_wiring["registry"])
