"""Capability-path intent wiring — class-identity slugs (STATS-002 Task 3b).

The observability capability carries the agent-class identity as its
``intent`` (ADR-093, architecture ruling Option A): a snake_case slug
derived from the concrete agent class name by default, an
``observability_intent`` ClassVar override when declared, preserved
through ``for_run`` into the per-run copy, with the bare-capability
``"unknown"`` fallback unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.test import TestModel

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.capabilities.observability import NarrareObservability
from narrare_core.llm.usage_events import UsageEvent, set_usage_event_sink

if TYPE_CHECKING:
    import pytest


class RecordingSink:
    """Records UsageEvents (pattern from Task 3's tests, not imported)."""

    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class _FakeRunContext:
    """Minimal RunContext stand-in for hook-level tests."""

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


class SlugProbeAgent(NarrareAgent[None, str]):
    """CamelCase probe — derived slug must be ``"slug_probe"``."""


class POVDetectionAgent(NarrareAgent[None, str]):
    """Acronym-prefix probe — derived slug must be ``"pov_detection"``."""


class OverridingAgent(NarrareAgent[None, str]):
    """Probe using the ``observability_intent`` override point."""

    observability_intent = "custom_intent"


def _stub_estimate_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub estimate_cost_usd at the capability's import location (no rates I/O)."""
    monkeypatch.setattr(
        "narrare_core.agents.capabilities.observability.estimate_cost_usd",
        lambda *args, **kwargs: 0.01,
    )


async def _run_with_sink(
    agent: NarrareAgent[None, str],
    monkeypatch: pytest.MonkeyPatch,
) -> list[UsageEvent]:
    """Run an agent against a RecordingSink and return the emitted events."""
    _stub_estimate_cost(monkeypatch)
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        await agent.run("probe prompt", deps=None)
    finally:
        set_usage_event_sink(None)
    return sink.events


class TestDerivedClassIdentityIntent:
    """TestModel-driven runs emit the agent-class identity slug."""

    async def test_run_emits_derived_slug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent = SlugProbeAgent(model=TestModel(), deps_type=type(None))
        events = await _run_with_sink(agent, monkeypatch)
        assert len(events) == 1
        assert events[0].intent == "slug_probe"

    async def test_run_emits_slug_with_acronym_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Acronym prefixes stay intact: POVDetectionAgent → pov_detection."""
        agent = POVDetectionAgent(model=TestModel(), deps_type=type(None))
        events = await _run_with_sink(agent, monkeypatch)
        assert len(events) == 1
        assert events[0].intent == "pov_detection"

    async def test_classvar_override_wins_over_derived_slug(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = OverridingAgent(model=TestModel(), deps_type=type(None))
        events = await _run_with_sink(agent, monkeypatch)
        assert len(events) == 1
        assert events[0].intent == "custom_intent"


class TestIntentTemplateState:
    """Template intent is a constructor field, preserved by for_run."""

    async def test_for_run_preserves_template_intent(self) -> None:
        template = NarrareObservability(intent="chapter_summary")
        per_run = await template.for_run(cast("Any", _FakeRunContext(deps=None)))
        assert per_run is not template
        assert isinstance(per_run, NarrareObservability)
        assert per_run.intent == "chapter_summary"

    async def test_bare_construction_falls_back_to_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bare NarrareObservability() keeps the historical "unknown" fallback."""
        _stub_estimate_cost(monkeypatch)
        ctx = _FakeUsageCtx()
        sink = RecordingSink()
        set_usage_event_sink(sink)
        try:
            obs = NarrareObservability()
            await obs.before_model_request(cast("Any", ctx), cast("Any", None))
            await obs.after_model_request(
                cast("Any", ctx),
                request_context=cast("Any", None),
                response=ModelResponse(parts=[]),
            )
        finally:
            set_usage_event_sink(None)

        assert len(sink.events) == 1
        assert sink.events[0].intent == "unknown"
