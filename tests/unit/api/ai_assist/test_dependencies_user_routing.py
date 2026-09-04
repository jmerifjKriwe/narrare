"""User-routing migration tests for the ai_assist dependency factory (Task 4).

Regression-first proof that ``ai_assist/dependencies.get_dialogue_coach_service``
resolves the dialogue-coach model via the per-user ``ModelRoutingResolver``
cascade (instead of the legacy ``build_system_default_config``) with the
correct intent + user_id, and that the resolved config + credentials land
on the service that owns the actual ``get_model`` call:

- DialogueCoach model — ``LLMIntent.DIALOGUE_COACH`` (ADR-069 Decision 5,
  feature ``ai_assist_dialogue_coach``)

The dialogue-coach router is chapter-scoped (``chapter_id`` path parameter);
the novel (project) is only known after the chapter load inside the
service, so the cascade runs WITHOUT the project tier — the factory passes
``None``. Credential flow into the real resolution point
(``_agent_runner.run_dialogue_coach_agent``) is proven in
``TestCredentialsReachResolutionPoint`` (setup-bug shape). Sibling of
``tests/unit/api/consistency/test_deps_user_routing.py`` (Task 3) — same
conventions: fake resolver, recording registry, cast-pattern fakes.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 3 conventions)
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


def _resolved() -> ResolvedModel:
    """A ResolvedModel as the wired-up user's cascade would return."""
    return ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver returning one resolved model."""
    resolved = _resolved()
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


class _StopResolution(Exception):
    """Sentinel raised after get_model recorded its call (short-circuits)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for asserts."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return object()

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6d bridge: resolution flows through prepare → get_model.

        Delegates to the SAME recording ``get_model`` call so the
        credential assertions (``registry.calls`` shape) hold for the
        migrated (prepare) path under test.
        """
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


# ===========================================================================
# Structural — factory is async, user-scoped, legacy-pattern-free
# ===========================================================================

_FACTORY = ("narrare.ai_assist.dependencies", "get_dialogue_coach_service")


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    def test_factory_is_async_with_user_routing_params(self) -> None:
        import importlib

        factory = getattr(importlib.import_module(_FACTORY[0]), _FACTORY[1])

        assert inspect.iscoroutinefunction(factory)
        params = list(inspect.signature(factory).parameters)
        assert "user_id" in params
        assert "session" in params

    def test_factory_does_not_use_system_default_config(self) -> None:
        import importlib

        source = inspect.getsource(importlib.import_module(_FACTORY[0]))
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source


# ===========================================================================
# Factory execution — resolver resolves DIALOGUE_COACH + threads results
# ===========================================================================


class TestDialogueCoachDepsUserRouting:
    """get_dialogue_coach_service resolves DIALOGUE_COACH for THIS user."""

    async def test_resolves_intent_and_threads_results_into_wiring(self) -> None:
        from narrare.ai_assist.dependencies import get_dialogue_coach_service
        from narrare.ai_assist.service import DialogueCoachService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.ai_assist.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
            patch(
                "narrare.adaptive.dependencies.get_adaptive_context_provider",
                return_value=MagicMock(spec=True, name="AdaptiveContextProvider"),
            ),
        ):
            service = await get_dialogue_coach_service(
                session=session,
                user_id=user_id,
            )

        # The REAL intent (feature ai_assist_dialogue_coach), for THIS user,
        # WITHOUT the project tier (no novel path param on the router — the
        # novel is only known after the chapter load inside the service).
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.DIALOGUE_COACH, UUID(user_id), None)
        ]

        assert isinstance(service, DialogueCoachService)
        config = service._config
        assert isinstance(config, ResolvedModelConfig)
        assert config is resolved.config
        assert config.model_id == "glm-4.7"
        assert config.provider_name == "zai"

        # Resolved user credentials land on the service (threaded onwards to
        # the agent-runner get_model resolution point).
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.get_model
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL resolution call (setup bug)."""

    def _composed_prompt(self) -> ComposedPrompt:
        from narrare_core.prompts.composer import ComposedPrompt

        return ComposedPrompt(system="System prompt.", user="User prompt.")

    async def test_agent_runner_threads_credentials_into_get_model(self) -> None:
        from narrare.ai_assist._agent_runner import run_dialogue_coach_agent

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())

        with pytest.raises(_StopResolution):
            await run_dialogue_coach_agent(
                selection_text="Anna said: hello.",
                mode="analyze",
                characters=["Anna"],
                project_title="Test Novel",
                genre="Fantasy",
                language="en",
                voice_profiles_text="",
                chapter_id=uuid4(),
                model_registry=cast("ModelRegistry", registry),
                model_config=config,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
                composed_prompt=self._composed_prompt(),
            )

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
