"""User-routing migration tests — credentials reach the resolution point (Task 1b).

Companion of ``test_deps_user_routing_1b.py`` (split off for the RULE-04
test-file hard limit). Proves that the api_key/base_url resolved by the
per-user cascade reach the ACTUAL resolution calls inside the services
(the setup-bug shape fixed like Task 1a):

- ``KBAssistService._get_model`` (KB_INTERVIEW — assist canonical default)
- ``WorldbuildingAnalyzer._get_model`` (KB_WORLDBUILD)
- ``KBConsistencyAnalyzer`` via ``ModelRegistry.run`` (KB_CONSISTENCY)

Same conventions as the sibling files: fake resolver, cast-pattern
registry fakes (mirrors ``test_deps_user_routing.py``, Task 1a).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.models import KBEntry
    from narrare_core.llm.gateway import ModelRegistry

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 1a conventions)
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _StopResolution(Exception):
    """Sentinel raised after run/get_model recorded its call (short-circuits)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model``/``run`` calls for asserts."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.run_calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: object = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return SimpleNamespace(sentinel_model=True)

    async def run(
        self,
        intent: LLMIntent,
        prompt: str,
        config: ResolvedModelConfig,
        *,
        system_prompt: str | None = None,
        output_type: type[object] | None = None,
        deps: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        self.run_calls.append(
            {"intent": intent, "config": config, "api_key": api_key, "base_url": base_url}
        )
        if self._stop is not None:
            raise self._stop
        return SimpleNamespace(issues=[])


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.get_model / .run
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL resolution call (setup bug)."""

    async def test_assist_service_threads_credentials_into_get_model(self) -> None:
        from narrare.kb.assist_service import KBAssistService

        config = _user_config()
        registry = _RecordingRegistry()
        service = KBAssistService(
            registry=cast("ModelRegistry", registry),
            config=config,
            kb_context_provider=MagicMock(spec=True, name="KBContextProvider"),
            prompt_composer=MagicMock(spec=True, name="PromptComposer"),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        model = await service._get_model()

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
        assert getattr(model, "sentinel_model", False) is True

    async def test_worldbuilding_analyzer_threads_credentials_into_get_model(self) -> None:
        from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer

        config = _user_config()
        registry = _RecordingRegistry()
        analyzer = WorldbuildingAnalyzer(
            kb_repo=MagicMock(spec=True, name="KBRepository"),
            rel_repo=MagicMock(spec=True, name="RelationshipRepository"),
            cache=MagicMock(spec=True, name="WorldbuildingCache"),
            registry=cast("ModelRegistry", registry),
            config=config,
            composer=MagicMock(spec=True, name="PromptComposer"),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        model = await analyzer._get_model()

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
        assert getattr(model, "sentinel_model", False) is True

    async def test_consistency_analyzer_threads_credentials_into_run(self) -> None:
        from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        composer = MagicMock(spec=["build"], name="PromptComposer")
        composer.build = AsyncMock(
            return_value=SimpleNamespace(system="system prompt", user="user prompt")
        )
        analyzer = KBConsistencyAnalyzer(
            kb_repo=MagicMock(spec=True, name="KBRepository"),
            registry=cast("ModelRegistry", registry),
            config=config,
            composer=composer,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        entity = SimpleNamespace(
            id=uuid4(),
            name="Entry",
            entity_type="character",
            metadata_={},
            body="Body text.",
            tags=[],
        )

        with pytest.raises(_StopResolution):
            await analyzer._analyze_entry(cast("KBEntry", entity))

        assert len(registry.run_calls) == 1
        run_call = registry.run_calls[0]
        assert run_call["intent"] is LLMIntent.KB_CONSISTENCY
        assert run_call["config"] is config
        assert run_call["api_key"] == _USER_KEY
        assert run_call["base_url"] == _USER_BASE_URL
