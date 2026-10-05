"""Capability-path provider/model attribution (STATS-002 Task 3c).

``NarrareAgent.__init__`` derives ``(provider_name, model_id)`` from the
pydantic-ai ``model`` object (unwrapping wrapper models) and carries them
on the observability capability template. ``for_run`` resolves per-run
attribution as deps-extracted ``model_config`` > template value >
``"unknown"`` — independently for each field — so agents without
WritingDeps-family deps no longer attribute ``"unknown"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.instrumented import InstrumentedModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.zai import ZaiProvider

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.capabilities.observability import (
    NarrareObservability,
    derive_model_attribution,
)
from narrare_core.llm.usage_events import UsageEvent, set_usage_event_sink

if TYPE_CHECKING:
    import pytest


class RecordingSink:
    """Records UsageEvents (pattern from Task 3b's tests, not imported)."""

    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class _FakeRunContext:
    """Minimal RunContext stand-in for for_run-level tests."""

    def __init__(self, deps: object = None) -> None:
        self.deps = deps


class _FakeUsage:
    def __init__(self) -> None:
        self.input_tokens = 5
        self.output_tokens = 2
        self.total_tokens = 7
        self.details: dict[str, int] = {}


class _FakeUsageCtx:
    def __init__(self) -> None:
        self.usage = _FakeUsage()
        self.deps = None


class _ModelConfigStub:
    """WritingDeps-family ``ResolvedModelConfig`` stand-in."""

    def __init__(self, provider_name: str = "", model_id: str = "") -> None:
        self.provider_name = provider_name
        self.model_id = model_id


class _DepsWithModelConfig:
    def __init__(self, model_config: _ModelConfigStub) -> None:
        self.model_config = model_config


class _PlainDeps:
    """Non-WritingDeps deps without any model_config attribute."""


class _PydanticDeps(BaseModel):
    """Deps whose ``model_config`` is pydantic's own ConfigDict (not ours)."""


class ProbeAgent(NarrareAgent[None, str]):
    """Attribution probe — derived slug ``"probe"``."""


class PydanticDepsAgent(NarrareAgent[_PydanticDeps, str]):
    """Probe carrying pydantic-BaseModel deps (model_config is ConfigDict)."""


def _stub_estimate_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub estimate_cost_usd at the capability's import location (no rates I/O)."""
    monkeypatch.setattr(
        "narrare_core.agents.capabilities.observability.estimate_cost_usd",
        lambda *args, **kwargs: 0.01,
    )


async def _run_with_sink(
    agent: NarrareAgent[Any, str],
    monkeypatch: pytest.MonkeyPatch,
    *,
    deps: Any = None,
) -> list[UsageEvent]:
    """Run an agent against a RecordingSink and return the emitted events."""
    _stub_estimate_cost(monkeypatch)
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        await agent.run("probe prompt", deps=deps)
    finally:
        set_usage_event_sink(None)
    return sink.events


class TestDeriveModelAttribution:
    """derive_model_attribution reads identity off the pydantic-ai model."""

    def test_real_model_yields_provider_and_name(self) -> None:
        model = OpenAIChatModel("gpt-5.2", provider=OpenAIProvider(api_key="k"))
        assert derive_model_attribution(model) == ("openai", "gpt-5.2")

    def test_zai_provider_name_matches_registry_namespace(self) -> None:
        model = OpenAIChatModel("glm-4.7", provider=ZaiProvider(api_key="k"))
        assert derive_model_attribution(model) == ("zai", "glm-4.7")

    def test_test_model_yields_its_own_name(self) -> None:
        assert derive_model_attribution(TestModel()) == ("test", "test")
        assert derive_model_attribution(TestModel(model_name="glm-4.7")) == ("test", "glm-4.7")

    def test_instrumented_wrapper_unwraps_to_underlying(self) -> None:
        model = OpenAIChatModel("gpt-5.2", provider=OpenAIProvider(api_key="k"))
        assert derive_model_attribution(InstrumentedModel(model)) == ("openai", "gpt-5.2")

    def test_nested_wrappers_unwrap_to_underlying(self) -> None:
        model = OpenAIChatModel("gpt-5.2", provider=OpenAIProvider(api_key="k"))
        nested = WrapperModel(WrapperModel(model))
        assert derive_model_attribution(nested) == ("openai", "gpt-5.2")

    def test_provider_colon_model_name_is_parsed(self) -> None:
        class _PrefixedNameModel:
            model_name = "openai:gpt-4o"

        assert derive_model_attribution(cast("Any", _PrefixedNameModel())) == ("openai", "gpt-4o")

    def test_underivable_model_returns_empty_pair(self) -> None:
        assert derive_model_attribution(cast("Any", object())) == ("", "")


class TestAttributionThroughRuns:
    """TestModel-driven runs attribute the agent's model, deps or not."""

    async def test_run_attributes_model_name_without_deps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = ProbeAgent(model=TestModel(model_name="glm-4.7"), deps_type=type(None))
        events = await _run_with_sink(agent, monkeypatch)
        assert len(events) == 1
        assert events[0].model_id == "glm-4.7"
        assert events[0].provider == "test"

    async def test_pydantic_deps_no_longer_mask_attribution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ConfigDict ``model_config`` is not ours — template must still win."""
        agent = PydanticDepsAgent(model=TestModel(model_name="glm-4.7"), deps_type=_PydanticDeps)
        events = await _run_with_sink(agent, monkeypatch, deps=_PydanticDeps())
        assert len(events) == 1
        assert events[0].model_id == "glm-4.7"  # was "unknown" before Task 3c
        assert events[0].provider == "test"

    async def test_wrapped_model_run_unwraps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """E2E wrapped-model run attributes the underlying model.

        Uses a plain ``WrapperModel``: running an ``InstrumentedModel``
        emits real OTel spans through the *global* tracer provider, making
        the test order-dependent on suites that install fake global
        providers (observed: 1/14347 failure via ``_FakeSpanProcessor``).
        Real-``InstrumentedModel`` unwrapping is covered hermetically in
        ``TestDeriveModelAttribution``.
        """
        agent = ProbeAgent(
            model=WrapperModel(TestModel(model_name="glm-4.7")), deps_type=type(None)
        )
        events = await _run_with_sink(agent, monkeypatch)
        assert len(events) == 1
        assert events[0].model_id == "glm-4.7"


class TestForRunFallbackChain:
    """for_run resolves deps-extracted > template > unknown, per field."""

    async def test_deps_model_config_preferred_over_template(self) -> None:
        template = NarrareObservability(provider_name="openai", model_id="gpt-5.2")
        deps = _DepsWithModelConfig(
            _ModelConfigStub(provider_name="anthropic", model_id="claude-sonnet-4-5")
        )
        fresh = await template.for_run(cast("Any", _FakeRunContext(deps=deps)))
        assert fresh._provider_name == "anthropic"
        assert fresh._model_id == "claude-sonnet-4-5"

    async def test_template_used_when_deps_lack_model_config(self) -> None:
        template = NarrareObservability(provider_name="openai", model_id="gpt-5.2")
        fresh = await template.for_run(cast("Any", _FakeRunContext(deps=_PlainDeps())))
        assert fresh._provider_name == "openai"
        assert fresh._model_id == "gpt-5.2"

    async def test_fields_fall_back_independently(self) -> None:
        template = NarrareObservability(provider_name="openai", model_id="gpt-5.2")
        deps = _DepsWithModelConfig(_ModelConfigStub(provider_name="anthropic"))
        fresh = await template.for_run(cast("Any", _FakeRunContext(deps=deps)))
        assert fresh._provider_name == "anthropic"  # deps wins
        assert fresh._model_id == "gpt-5.2"  # template fallback

    async def test_chain_ends_at_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bare template without deps: hooks still emit "unknown"."""
        _stub_estimate_cost(monkeypatch)
        ctx = _FakeUsageCtx()
        sink = RecordingSink()
        set_usage_event_sink(sink)
        try:
            obs = await NarrareObservability().for_run(cast("Any", ctx))
            await obs.before_model_request(cast("Any", ctx), cast("Any", None))
            await obs.after_model_request(
                cast("Any", ctx),
                request_context=cast("Any", None),
                response=ModelResponse(parts=[]),
            )
        finally:
            set_usage_event_sink(None)

        assert len(sink.events) == 1
        assert sink.events[0].provider == "unknown"
        assert sink.events[0].model_id == "unknown"
