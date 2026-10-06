"""NarrareObservability UsageEvent emission — ADR-093 decision 4 (STATS-002).

One ``UsageEvent`` per model request, emitted after ``record_success`` and
the cache-metrics block: token/cache counts, unknown fallbacks, deps-based
provider/model, ContextVar attribution, and a sink that never breaks the run.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from pydantic_ai.messages import ModelResponse
from structlog.testing import capture_logs

from narrare_core.agents.capabilities.observability import NarrareObservability
from narrare_core.llm.usage_events import (
    UsageEvent,
    set_usage_context,
    set_usage_event_sink,
)

if TYPE_CHECKING:
    import pytest


class RecordingSink:
    """Records UsageEvents (pattern copied from Task 2, not imported)."""

    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class ExplodingSink:
    async def record(self, event: UsageEvent) -> None:
        raise RuntimeError("sink down")


class _FakeUsage:
    """Minimal RunUsage stub (input/output/total tokens + details)."""

    def __init__(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        details: dict[str, int] | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.details: dict[str, int] = details or {}


class _FakeUsageCtx:
    """ctx stub exposing usage + deps for before/after_model_request."""

    def __init__(self, usage: _FakeUsage, deps: object = None) -> None:
        self.usage = usage
        self.deps = deps


class _FakeModelConfig:
    provider_name = "test_provider"
    model_id = "test-model-v1"


class _FakeDepsWithModelConfig:
    model_config = _FakeModelConfig()


def _patch_estimate_cost(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, object]]) -> None:
    """Stub estimate_cost_usd at the capability's import location (no rates I/O)."""

    def fake_estimate(
        provider: str,
        model_id: str,
        *,
        tokens_in: int,
        tokens_out: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        calls.append(
            {
                "provider": provider,
                "model_id": model_id,
                "tokens_in": tokens_in,
                "cache_read_tokens": cache_read_tokens,
                "cache_creation_tokens": cache_creation_tokens,
                "tokens_out": tokens_out,
            }
        )
        return 0.05

    monkeypatch.setattr(
        "narrare_core.agents.capabilities.observability.estimate_cost_usd",
        fake_estimate,
    )


async def _emit_once(monkeypatch: pytest.MonkeyPatch, ctx: _FakeUsageCtx) -> None:
    """Drive before/after_model_request with a minimal ModelResponse."""
    obs = NarrareObservability()
    await obs.before_model_request(cast("Any", ctx), cast("Any", None))
    await obs.after_model_request(
        cast("Any", ctx),
        request_context=cast("Any", None),
        response=ModelResponse(parts=[]),
    )


class TestUsageEventEmission:
    """after_model_request emits one UsageEvent per model request (ADR-093 D4)."""

    async def test_after_model_request_without_deps_emits_event_with_unknown_fallbacks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No deps.model_config → intent/provider/model_id fall back to "unknown"."""
        cost_calls: list[dict[str, object]] = []
        _patch_estimate_cost(monkeypatch, cost_calls)

        ctx = _FakeUsageCtx(
            _FakeUsage(
                input_tokens=100,
                output_tokens=40,
                total_tokens=140,
                details={
                    "cache_read_input_tokens": 500,
                    "cache_creation_input_tokens": 200,
                },
            ),
            deps=None,
        )
        response = ModelResponse(parts=[])
        sink = RecordingSink()
        set_usage_event_sink(sink)
        set_usage_context(user_id=None, novel_id=None)
        try:
            obs = NarrareObservability()
            await obs.before_model_request(cast("Any", ctx), cast("Any", None))
            result = await obs.after_model_request(
                cast("Any", ctx),
                request_context=cast("Any", None),
                response=response,
            )
        finally:
            set_usage_event_sink(None)

        assert result is response
        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.intent == "unknown"
        assert event.provider == "unknown"
        assert event.model_id == "unknown"
        assert event.tokens_in == 100
        assert event.tokens_out == 40
        assert event.cache_read_tokens == 500
        assert event.cache_creation_tokens == 200
        assert event.duration_seconds >= 0.0
        assert isinstance(event.timestamp, datetime)
        assert event.cost_usd == 0.05
        assert event.user_id is None
        assert event.novel_id is None
        # Cost estimator receives the same fallbacks and token counts
        assert cost_calls == [
            {
                "provider": "unknown",
                "model_id": "unknown",
                "tokens_in": 100,
                "tokens_out": 40,
                "cache_read_tokens": 500,
                "cache_creation_tokens": 200,
            }
        ]

    async def test_after_model_request_takes_provider_model_from_deps_model_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider/model on the event come from deps.model_config via for_run."""
        cost_calls: list[dict[str, object]] = []
        _patch_estimate_cost(monkeypatch, cost_calls)

        ctx = _FakeUsageCtx(
            _FakeUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            deps=_FakeDepsWithModelConfig(),
        )
        sink = RecordingSink()
        set_usage_event_sink(sink)
        try:
            obs = NarrareObservability()
            per_run = await obs.for_run(cast("Any", ctx))
            await per_run.before_model_request(cast("Any", ctx), cast("Any", None))
            await per_run.after_model_request(
                cast("Any", ctx),
                request_context=cast("Any", None),
                response=ModelResponse(parts=[]),
            )
        finally:
            set_usage_event_sink(None)

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.provider == "test_provider"
        assert event.model_id == "test-model-v1"
        assert cost_calls[0]["provider"] == "test_provider"
        assert cost_calls[0]["model_id"] == "test-model-v1"

    async def test_after_model_request_attributes_contextvars_to_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """user_id/novel_id ContextVars land on the emitted event."""
        _patch_estimate_cost(monkeypatch, [])

        ctx = _FakeUsageCtx(_FakeUsage(input_tokens=7, output_tokens=3, total_tokens=10))
        user_id, novel_id = uuid4(), uuid4()
        sink = RecordingSink()
        set_usage_event_sink(sink)
        set_usage_context(user_id=user_id, novel_id=novel_id)
        try:
            await _emit_once(monkeypatch, ctx)
        finally:
            set_usage_event_sink(None)
            set_usage_context(user_id=None, novel_id=None)

        assert len(sink.events) == 1
        assert sink.events[0].user_id == user_id
        assert sink.events[0].novel_id == novel_id

    async def test_after_model_request_with_exploding_sink_still_returns_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing sink must never break the model run (guarded seam)."""
        _patch_estimate_cost(monkeypatch, [])

        ctx = _FakeUsageCtx(_FakeUsage(input_tokens=1, output_tokens=1, total_tokens=2))
        response = ModelResponse(parts=[])
        set_usage_event_sink(ExplodingSink())
        try:
            obs = NarrareObservability()
            await obs.before_model_request(cast("Any", ctx), cast("Any", None))
            result = await obs.after_model_request(
                cast("Any", ctx),
                request_context=cast("Any", None),
                response=response,
            )
        finally:
            set_usage_event_sink(None)

        assert result is response

    async def test_after_model_request_with_garbage_details_returns_response_and_emits_no_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FU-1: malformed usage.details must never raise into the model run."""
        _patch_estimate_cost(monkeypatch, [])  # cost is never reached
        # Deliberate annotation lie: simulates a runtime-malformed provider
        # payload (non-numeric detail value) that slips past dict[str, int].
        garbage_details = cast("dict[str, int]", {"cache_read_input_tokens": "garbage"})
        ctx = _FakeUsageCtx(
            _FakeUsage(input_tokens=10, output_tokens=5, total_tokens=15, details=garbage_details)
        )
        response = ModelResponse(parts=[])
        sink = RecordingSink()
        set_usage_event_sink(sink)
        try:
            with capture_logs() as logs:
                obs = NarrareObservability()
                await obs.before_model_request(cast("Any", ctx), cast("Any", None))
                result = await obs.after_model_request(
                    cast("Any", ctx),
                    request_context=cast("Any", None),
                    response=response,
                )
        finally:
            set_usage_event_sink(None)

        assert result is response
        # Sentinel sink: no (half-built) event may arrive.
        assert sink.events == []
        failures = [e for e in logs if e.get("event") == "usage_event_emission_failed"]
        assert len(failures) == 1
        assert failures[0]["error"]
