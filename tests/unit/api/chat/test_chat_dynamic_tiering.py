"""ChatService dynamic tiering pilot wiring (ADR-089) — default-off invariant.

Pins the backend wiring of the opt-in dynamic tier escalation pilot
(ADR-089 Decisions 5/7):

- Flag off (default): byte-identical wiring — the agent runs on the base
  CHAT model, the escalation resolution is never awaited, no dynamic-tier
  logging, and the DI factory passes no escalation resolution.
- Flag on: the escalation (ANALYSE) cascade resolves lazily at first use
  (ADR-086 — never at DI time), the escalation ``Model`` is built through
  ``ModelRegistry.get_model`` with the escalation credentials, and the
  ``SelectModel`` capability from ``build_tiered_model`` reaches the
  ``ChatAgent`` via ``capabilities=`` (base model stays the constructor
  model — upstream ``model_is_explicit`` shape).
- Degradation (RULE-11): the escalation cascade's ``ConfigurationError``
  (and a failing escalation ``get_model``) degrades loudly — one
  ``dynamic_tier_degraded`` warning, chat continues on the base model and
  NEVER hard-fails. Any other error propagates (no swallowed bugs).

Provider attribution (D7): the wiring layer logs the provider/model ids
from the ``ResolvedModelConfig``s it holds at attach time — the core
selector logs ``Model.model_name`` only.

Fixture/fake conventions mirror ``test_chat_prepare_wiring.py`` and
``test_chat_dependencies.py`` (recording registry, patched ChatAgent +
SSE bridge, ``StaticModelResolution`` seams, ADR-071 §8 env pattern for
the ``CoreSettings`` knobs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.chat.chat_service import ChatService
from narrare_core.chat.contracts import ChatRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.settings import get_core_settings
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

_BASE_KEY = "sk-user-key"
_ESCALATION_KEY = "sk-escalation-key"
_ESCALATION_BASE_URL = "https://escalation.example/v1"


def _base_resolved_model() -> ResolvedModel:
    """The base CHAT cascade result (cheap tier)."""
    return ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="zai", model_id="glm-4.7", temperature=0.7, max_tokens=4096
        ),
        api_key=_BASE_KEY,
        base_url=None,
    )


def _escalation_resolved_model() -> ResolvedModel:
    """The escalation ANALYSE cascade result (capable tier, own credentials)."""
    return ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5",
            temperature=0.7,
            max_tokens=8192,
        ),
        api_key=_ESCALATION_KEY,
        base_url=_ESCALATION_BASE_URL,
    )


class _CountingResolution:
    """Fake ModelResolution — counts ``resolve()`` calls, never caches.

    Exposes the escalation lazy seam (ADR-086): the service must consume
    the escalation cascade exactly once (first use), never at construction,
    and never when the pilot flag is off.
    """

    def __init__(
        self,
        model: ResolvedModel | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._model = model
        self._error = error
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._model is not None
        return self._model


class _TieringRegistry:
    """Fake ModelRegistry — distinct model sentinels per ``get_model`` call.

    ``prepare`` mirrors the single assembly point (Task 6d); the escalation
    build goes through the same ``get_model`` (ADR-089 Decision 7), so
    ``models``/``get_model_calls`` pin base vs escalation construction and
    the escalation credentials actually reach the gateway.
    """

    def __init__(self, *, escalation_error: Exception | None = None) -> None:
        self.models: list[MagicMock] = []
        self.get_model_calls: list[dict[str, object]] = []
        self._escalation_error = escalation_error

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> MagicMock:
        """Return a fresh sentinel model; optionally fail the escalation build."""
        _ = usage_limits
        if self._escalation_error is not None and self.models:
            raise self._escalation_error
        model = MagicMock(spec=object, name=f"model_{len(self.models)}")
        self.models.append(model)
        self.get_model_calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        return model

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Mirror the single assembly point (delegates to get_model)."""
        from narrare_core.llm._prepared_call import PreparedModelCall

        return PreparedModelCall(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


class _ChatAgentStub:
    """Minimal ChatAgent stand-in for the RULE-TEST-01 spec requirement."""


def _make_service(
    registry: _TieringRegistry,
    *,
    escalation_resolution: ModelResolution | None = None,
) -> ChatService:
    """Build a ChatService with the tiering seam injected (test shape)."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock(spec=PromptComposer)
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="Chat system.", user="Chat user.")
    )
    return ChatService(
        prompt_composer=cast("PromptComposer", composer),
        model_registry=cast("ModelRegistry", registry),
        conversation_store=cast("SQLAlchemyConversationStore", InMemoryConversationStore()),
        model_resolution=StaticModelResolution(_base_resolved_model()),
        escalation_resolution=escalation_resolution,
    )


async def _drive_ask(service: ChatService, request: ChatRequest) -> MagicMock:
    """Drive ``ask()`` with ChatAgent + SSE bridge patched.

    Returns the patched ``ChatAgent`` factory so tests assert the exact
    constructor kwargs (model / capabilities) the stream wiring passed.
    """
    agent_factory = MagicMock(
        name="ChatAgent",
        spec=_ChatAgentStub,
        return_value=MagicMock(name="agent_instance", spec=_ChatAgentStub),
    )

    async def _stream_bridge(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        _ = kwargs
        yield {"type": "done", "usage": {}}

    from typing import Any

    with (
        patch("narrare_core.chat.chat_agent.ChatAgent", agent_factory),
        patch(
            "narrare.chat._sse_stream.stream_agent_events",
            side_effect=cast("Any", _stream_bridge),
        ),
    ):
        gen = await service.ask(request, uuid4())
        async for _ in gen:
            pass
    return agent_factory


def _request() -> ChatRequest:
    """A project-less chat request (skips the project tiers cleanly)."""
    return ChatRequest(project_id=None, message="Hello!")


class TestFlagOffInvariance:
    """Default-off must be byte-identical to the pre-ADR-089 wiring."""

    @pytest.mark.usefixtures("tiering_off")
    async def test_flag_disabled_uses_base_model_unchanged(self) -> None:
        """Flag off: base model identity, zero escalation work, no tier logs."""
        registry = _TieringRegistry()
        escalation = _CountingResolution(_escalation_resolved_model())
        service = _make_service(registry, escalation_resolution=escalation)

        with capture_logs() as logs:
            agent_factory = await _drive_ask(service, _request())

        # No extra resolution work — the escalation cascade is never awaited.
        assert escalation.calls == 0
        # The agent runs on exactly the base-resolution model, no capability.
        kwargs = agent_factory.call_args.kwargs
        assert kwargs["model"] is registry.models[0]
        assert kwargs["capabilities"] is None
        # Silent by default: no dynamic-tier events on the shipped path.
        assert not [event for event in logs if event["event"].startswith("dynamic_tier_")]


class TestFlagOnWiring:
    """Flag on: lazy escalation resolution + SelectModel capability attach."""

    async def test_flag_enabled_wraps_model_with_tiered_capability(
        self,
        tiering_on: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Flag on: capability attach, gateway-built escalation model, D7 ids.

        The escalation ``Model`` is built through ``registry.get_model`` with
        the escalation credentials; ``build_tiered_model`` receives the two
        constructed models plus the policy from the live CoreSettings knobs
        (RULE-18b backend evidence); the capability reaches the ChatAgent
        while the base model stays the constructor model (upstream
        ``model_is_explicit`` shape).
        """
        # RULE-18b: non-default knob values must reach the policy verbatim.
        monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS", "10")
        monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS", "3")
        get_core_settings.cache_clear()

        registry = _TieringRegistry()
        escalation_resolved = _escalation_resolved_model()
        escalation = _CountingResolution(escalation_resolved)
        service = _make_service(registry, escalation_resolution=escalation)

        sentinel_capability = object()
        build_calls: list[tuple[object, object, object]] = []

        def _recording_build(
            base_model: object,
            escalation_model: object,
            *,
            policy: object,
        ) -> object:
            build_calls.append((base_model, escalation_model, policy))
            return sentinel_capability

        with (
            capture_logs() as logs,
            patch(
                "narrare_core.llm.dynamic_tiering.build_tiered_model",
                side_effect=_recording_build,
            ),
        ):
            agent_factory = await _drive_ask(service, _request())

        # Escalation consumed exactly once at the first-use seam.
        assert escalation.calls == 1
        # Capability factory: (base_model, escalation_model, policy=...).
        assert len(build_calls) == 1
        base_model, escalation_model, policy = build_calls[0]
        assert base_model is registry.models[0]
        assert escalation_model is registry.models[1]
        from narrare_core.llm.dynamic_tiering import TieringPolicy

        assert isinstance(policy, TieringPolicy)
        assert policy.max_prompt_chars == 10
        assert policy.min_turns == 3
        # Escalation model built through the gateway with ITS credentials.
        assert len(registry.get_model_calls) == 2
        escalation_call = registry.get_model_calls[1]
        assert escalation_call["config"] is escalation_resolved.config
        assert escalation_call["api_key"] == _ESCALATION_KEY
        assert escalation_call["base_url"] == _ESCALATION_BASE_URL
        # Capability attached; the base model stays the constructor model.
        agent_kwargs = agent_factory.call_args.kwargs
        assert agent_kwargs["model"] is registry.models[0]
        assert agent_kwargs["capabilities"] == [sentinel_capability]
        # D7: provider attribution from the configs held at attach time.
        attached = [event for event in logs if event["event"] == "dynamic_tier_attached"]
        assert len(attached) == 1
        assert attached[0]["base_provider"] == "zai"
        assert attached[0]["base_model"] == "glm-4.7"
        assert attached[0]["escalation_provider"] == "anthropic"
        assert attached[0]["escalation_model"] == "claude-sonnet-4-5"


class TestDegradation:
    """The pilot must never hard-fail chat (ADR-089 Decision 5, RULE-11)."""

    async def test_flag_enabled_degrades_gracefully_when_capable_unresolvable(
        self,
        tiering_on: None,
    ) -> None:
        """Escalation cascade raises ConfigurationError → warn + base model."""
        registry = _TieringRegistry()
        escalation = _CountingResolution(
            error=ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")
        )
        service = _make_service(registry, escalation_resolution=escalation)

        with capture_logs() as logs:
            agent_factory = await _drive_ask(service, _request())

        # The chat turn answered on the base model.
        kwargs = agent_factory.call_args.kwargs
        assert kwargs["model"] is registry.models[0]
        assert kwargs["capabilities"] is None
        # Exactly one escalation attempt; degradation is loud, not fatal.
        assert escalation.calls == 1
        degraded = [event for event in logs if event["event"] == "dynamic_tier_degraded"]
        assert len(degraded) == 1
        assert degraded[0]["log_level"] == "warning"

    async def test_flag_enabled_degrades_when_escalation_model_build_fails(
        self,
        tiering_on: None,
    ) -> None:
        """A failing escalation ``get_model`` degrades instead of raising."""
        registry = _TieringRegistry(
            escalation_error=ConfigurationError("Provider not registered.", code="NO_AI_PROVIDER")
        )
        escalation = _CountingResolution(_escalation_resolved_model())
        service = _make_service(registry, escalation_resolution=escalation)

        with capture_logs() as logs:
            agent_factory = await _drive_ask(service, _request())

        kwargs = agent_factory.call_args.kwargs
        assert kwargs["model"] is registry.models[0]
        assert kwargs["capabilities"] is None
        degraded = [event for event in logs if event["event"] == "dynamic_tier_degraded"]
        assert len(degraded) == 1

    async def test_non_configuration_error_from_escalation_propagates(
        self,
        tiering_on: None,
    ) -> None:
        """RULE-11: only the documented signal degrades — bugs propagate."""
        registry = _TieringRegistry()
        escalation = _CountingResolution(error=RuntimeError("bug"))
        service = _make_service(registry, escalation_resolution=escalation)

        with pytest.raises(RuntimeError, match="bug"):
            await _drive_ask(service, _request())
