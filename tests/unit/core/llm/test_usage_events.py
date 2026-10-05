"""UsageEvent sink seam — protocol, slot, attribution vars, strict cost fn."""

from datetime import UTC
from uuid import uuid4

import pytest

from narrare_core.llm.usage_events import (
    UsageEvent,
    emit_usage_event,
    estimate_cost_usd,
    get_usage_event_sink,
    set_usage_context,
    set_usage_event_sink,
    usage_novel_id,
    usage_user_id,
)


def _event(**over):
    base = {
        "timestamp": __import__("datetime").datetime.now(UTC),
        "intent": "draft",
        "provider": "zai",
        "model_id": "glm-5.3",
        "tokens_in": 1000,
        "tokens_out": 200,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "duration_seconds": 1.5,
        "cost_usd": None,
        "user_id": None,
        "novel_id": None,
    }
    base.update(over)
    return UsageEvent(**base)


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class ExplodingSink:
    async def record(self, event: UsageEvent) -> None:
        raise RuntimeError("sink down")


async def test_emit_without_sink_is_noop():
    set_usage_event_sink(None)
    await emit_usage_event(_event())  # must not raise


async def test_emit_delivers_to_registered_sink():
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        await emit_usage_event(_event())
        assert len(sink.events) == 1
        assert get_usage_event_sink() is sink
    finally:
        set_usage_event_sink(None)


async def test_emit_swallows_sink_exception():
    set_usage_event_sink(ExplodingSink())
    try:
        await emit_usage_event(_event())  # must not raise
    finally:
        set_usage_event_sink(None)


def test_set_usage_context_sets_both_vars():
    user, novel = uuid4(), uuid4()
    set_usage_context(user_id=user, novel_id=novel)
    assert usage_user_id.get() == user
    assert usage_novel_id.get() == novel
    set_usage_context(user_id=None, novel_id=None)


def test_estimate_cost_known_model(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0},
    )
    # 1M input + 1M output => 2.0 + 6.0
    assert estimate_cost_usd(
        "zai", "glm-5.3", tokens_in=1_000_000, tokens_out=1_000_000
    ) == pytest.approx(8.0)


def test_estimate_cost_cache_math(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0, "cache_read": 0.2, "cache_write": 4.0},
    )
    # input includes cache reads: non-cached part at input rate, cached at cache_read,
    # cache writes at cache_write
    cost = estimate_cost_usd(
        "zai",
        "glm-5.3",
        tokens_in=1_000_000,
        tokens_out=0,
        cache_read_tokens=400_000,
        cache_creation_tokens=100_000,
    )
    expected = 0.6 * 2.0 + 0.4 * 0.2 + 0.1 * 4.0
    assert cost == pytest.approx(expected)


def test_estimate_cost_unknown_model_is_none(monkeypatch):
    monkeypatch.setattr("narrare_core.llm.usage_events.get_rates_strict", lambda p, m: None)
    assert estimate_cost_usd("zai", "mystery", tokens_in=10, tokens_out=10) is None


def test_estimate_cost_zero_tokens_is_zero(monkeypatch):
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda p, m: {"input": 2.0, "output": 6.0},
    )
    assert estimate_cost_usd("zai", "glm-5.3", tokens_in=0, tokens_out=0) == 0.0
