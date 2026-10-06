"""ModelRegistry usage-event emission — ADR-093 decision 4 (STATS-002).

``run()``/``stream()`` create ephemeral Agents WITHOUT capabilities, so the
observability capability never fires for them. This is the second, disjoint
emission point: one ``UsageEvent`` per registry call, attributed from the
resolved ``config`` (exact — no "unknown" fallbacks), tokens from the
pydantic-ai usage object, and a guarded seam that never breaks the run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from pydantic_ai import Agent
from structlog.testing import capture_logs

from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.usage_events import (
    UsageEvent,
    set_usage_context,
    set_usage_event_sink,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from narrare_core.llm.gateway import ModelRegistry


class RecordingSink:
    """Records UsageEvents (pattern copied from Task 2, not imported)."""

    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class ExplodingSink:
    async def record(self, event: UsageEvent) -> None:
        raise RuntimeError("sink down")


@pytest.fixture
def recording_sink() -> Generator[RecordingSink]:
    """Register a RecordingSink and guarantee seam teardown."""
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        yield sink
    finally:
        set_usage_event_sink(None)


def _patch_estimate_cost(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, object]]) -> None:
    """Stub estimate_cost_usd in usage_events (no rates I/O).

    The emitter lives in ``narrare_core.llm.usage_events`` and resolves
    ``estimate_cost_usd`` as a module global at call time, so patching the
    definition site intercepts every call. A wrong patch target would fail
    loudly via the ``cost_usd == 0.05`` assertion (and the strict
    ``raising`` default, since the function is defined there).
    """

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
                "tokens_out": tokens_out,
                "cache_read_tokens": cache_read_tokens,
                "cache_creation_tokens": cache_creation_tokens,
            }
        )
        return 0.05

    monkeypatch.setattr("narrare_core.llm.usage_events.estimate_cost_usd", fake_estimate)


class TestRunEmitsUsageEvent:
    """registry.run() emits exactly one UsageEvent attributed from the config."""

    async def test_run_emits_one_event_with_config_attribution(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        recording_sink: RecordingSink,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """One event: intent value, exact provider/model from config, TestModel tokens."""
        cost_calls: list[dict[str, object]] = []
        _patch_estimate_cost(monkeypatch, cost_calls)
        user_id, novel_id = uuid4(), uuid4()
        set_usage_context(user_id=user_id, novel_id=novel_id)
        try:
            output = await registry_with_test_model.run(
                LLMIntent.NAME_GENERATE,
                prompt="x",
                config=write_config,
            )
        finally:
            set_usage_context(user_id=None, novel_id=None)

        assert output == "Test response from pydantic-ai TestModel."
        assert len(recording_sink.events) == 1
        event = recording_sink.events[0]
        assert event.intent == LLMIntent.NAME_GENERATE.value == "name_generate"
        assert event.provider == write_config.provider_name
        assert event.model_id == write_config.model_id
        # Tokens come from the pydantic-ai usage object (TestModel produced output).
        assert isinstance(event.tokens_in, int) and event.tokens_in >= 0
        assert event.tokens_out > 0
        assert event.cache_read_tokens == 0
        assert event.cache_creation_tokens == 0
        assert event.duration_seconds >= 0.0
        # Cost flows through estimate_cost_usd with the same attribution.
        assert event.cost_usd == 0.05
        assert cost_calls == [
            {
                "provider": write_config.provider_name,
                "model_id": write_config.model_id,
                "tokens_in": event.tokens_in,
                "tokens_out": event.tokens_out,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            }
        ]
        # ContextVar attribution reaches the event.
        assert event.user_id == user_id
        assert event.novel_id == novel_id

    async def test_run_returns_output_when_sink_explodes(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """A raising sink must never break the product run (ADR-093 D1)."""
        set_usage_event_sink(ExplodingSink())
        try:
            output = await registry_with_test_model.run(
                LLMIntent.NAME_GENERATE,
                prompt="x",
                config=write_config,
            )
        finally:
            set_usage_event_sink(None)

        assert output == "Test response from pydantic-ai TestModel."


class TestStreamEmitsUsageEvent:
    """registry.stream() emits one UsageEvent before the final chunk."""

    async def test_stream_emits_one_event_after_final_chunk(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        recording_sink: RecordingSink,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Driving the full stream records exactly one event matching final-chunk usage."""
        cost_calls: list[dict[str, object]] = []
        _patch_estimate_cost(monkeypatch, cost_calls)

        final_usage = None
        async for chunk in registry_with_test_model.stream(
            intent=LLMIntent.WRITE,
            system_prompt="System.",
            user_prompt="Write.",
            config=write_config,
        ):
            if chunk.is_final:
                final_usage = chunk.usage

        assert final_usage is not None
        assert len(recording_sink.events) == 1
        event = recording_sink.events[0]
        assert event.intent == LLMIntent.WRITE.value
        assert event.provider == write_config.provider_name
        assert event.model_id == write_config.model_id
        # Tokens match the final chunk's usage (same pydantic-ai usage object).
        assert event.tokens_in == final_usage.prompt_tokens
        assert event.tokens_out == final_usage.completion_tokens
        assert event.user_id is None
        assert event.novel_id is None

    async def test_stream_still_yields_final_chunk_when_sink_explodes(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """A raising sink must not break the stream (WS writing turns path)."""
        set_usage_event_sink(ExplodingSink())
        try:
            chunks = [
                chunk
                async for chunk in registry_with_test_model.stream(
                    intent=LLMIntent.WRITE,
                    system_prompt="System.",
                    user_prompt="Write.",
                    config=write_config,
                )
            ]
        finally:
            set_usage_event_sink(None)

        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) == 1
        assert final_chunks[0].usage is not None


def _corrupt_result_usage_details(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every ``Agent.run`` result carry a malformed usage detail value.

    pydantic-ai drops non-numeric detail values while accumulating usage
    (``_incr_usage_tokens`` isinstance-guards them), so the corruption must
    be applied to the finished result's usage object — the same place a
    real provider payload with a garbage string would surface it at this
    seam despite the ``dict[str, int]`` annotation.
    """
    original_run = Agent.run

    async def run_with_garbage_details(agent: Agent[Any, Any], *args: Any, **kwargs: Any) -> Any:
        result = await original_run(agent, *args, **kwargs)
        # Deliberate annotation lie: simulates a runtime-malformed provider
        # payload (non-numeric detail value) that slips past dict[str, int].
        result.usage.details["cache_read_input_tokens"] = cast("int", "garbage")
        return result

    monkeypatch.setattr(Agent, "run", run_with_garbage_details)


class TestMalformedUsageDetailsNeverBreakRun:
    """FU-1 (STATS-002 follow-up): construction runs outside the guarded seam.

    ``emit_registry_usage_event`` coerces ``usage.details`` values and builds
    the ``UsageEvent`` BEFORE the guarded ``emit_usage_event`` call. A
    non-numeric detail value (runtime provider payload) must never raise
    into the product run (ADR-093 D1 residual gap).
    """

    async def test_run_with_garbage_cache_details_returns_output_emits_no_event(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        recording_sink: RecordingSink,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed details → run returns output, sink sees nothing, warning logged."""
        _patch_estimate_cost(monkeypatch, [])  # isolate rates I/O; cost is never reached
        _corrupt_result_usage_details(monkeypatch)

        with capture_logs() as logs:
            output = await registry_with_test_model.run(
                LLMIntent.NAME_GENERATE,
                prompt="x",
                config=write_config,
            )

        assert output == "Test response from pydantic-ai TestModel."
        # Sentinel sink: no (half-built) event may arrive.
        assert recording_sink.events == []
        failures = [e for e in logs if e.get("event") == "usage_event_emission_failed"]
        assert len(failures) == 1
        assert failures[0]["error"]
