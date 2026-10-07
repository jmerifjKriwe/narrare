"""Embedding usage-event emission — ADR-093 surface (c) (STATS-002 slice D1).

``OpenAIEmbeddingProvider.embed_texts`` is the only seam that sees embedding
token counts (the SDK's ``CreateEmbeddingResponse.usage``), so it emits one
``UsageEvent`` per API batch response through the guarded helper
``emit_embedding_usage_event``. These tests use the provider's injected-client
DI pattern (see ``test_embeddings.py``) with response-shaped dataclass stubs
carrying ``data`` (sorted by index) and ``usage.total_tokens``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare_core.llm.usage_events import (
    UsageEvent,
    estimate_cost_usd,
    set_usage_context,
    set_usage_event_sink,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Response-shaped stubs (plain dataclasses — carry data + usage, unlike the
# MagicMock-spec fakes in _embedding_fakes.py which predate the usage field)
# ---------------------------------------------------------------------------


@dataclass
class _UsageStub:
    total_tokens: int | str | None = None


@dataclass
class _ItemStub:
    index: int = 0
    embedding: list[float] = field(default_factory=list)


@dataclass
class _ResponseStub:
    data: list[_ItemStub] = field(default_factory=list)
    usage: _UsageStub | None = None


class _FakeEmbeddingsResource:
    """Queued responses for ``client.embeddings.create``; records each call."""

    def __init__(self, responses: list[_ResponseStub]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _ResponseStub:
        self.calls.append(kwargs)
        return self._responses.pop(0)


@dataclass
class _FakeClient:
    embeddings: _FakeEmbeddingsResource


def _make_client(responses: list[_ResponseStub]) -> tuple[Any, _FakeEmbeddingsResource]:
    """Build an injected-client fake; the client is cast to ``Any`` (house
    pattern from test_cache_metrics.py) because the provider constructor
    annotates ``openai.AsyncOpenAI | None`` while tests inject a duck-typed
    stand-in."""
    resource = _FakeEmbeddingsResource(responses)
    return cast("Any", _FakeClient(embeddings=resource)), resource


def _batch_response(count: int, total_tokens: int | str | None) -> _ResponseStub:
    """One response for a batch of *count* texts (items indexed 0..count-1)."""
    return _ResponseStub(
        data=[_ItemStub(index=i, embedding=[float(i), 1.0]) for i in range(count)],
        usage=None if total_tokens is None else _UsageStub(total_tokens=total_tokens),
    )


# ---------------------------------------------------------------------------
# Sink + cost-patch fixtures (patterns from test_gateway_usage_events.py)
# ---------------------------------------------------------------------------


class RecordingSink:
    """Records UsageEvents (pattern from test_gateway_usage_events.py)."""

    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


@pytest.fixture
def recording_sink() -> Generator[RecordingSink]:
    sink = RecordingSink()
    set_usage_event_sink(sink)
    try:
        yield sink
    finally:
        set_usage_event_sink(None)


def _patch_estimate_cost(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, object]]) -> None:
    """Stub estimate_cost_usd in usage_events — no rates cache/models.dev I/O.

    The helper resolves ``estimate_cost_usd`` as a module global at call
    time, so patching the definition site intercepts every call; a wrong
    patch target would fail loudly via the ``cost_usd == 0.05`` assertion.
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


# ---------------------------------------------------------------------------
# Emission tests
# ---------------------------------------------------------------------------


class TestEmbeddingUsageEventEmission:
    async def test_one_event_per_batch(
        self, recording_sink: RecordingSink, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """150 texts with batch_size=100 → 2 API calls → 2 events, per-batch tokens."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        _patch_estimate_cost(monkeypatch, [])
        client, resource = _make_client([_batch_response(100, 1000), _batch_response(50, 500)])
        provider = OpenAIEmbeddingProvider(client=client, batch_size=100)

        result = await provider.embed_texts([f"text {i}" for i in range(150)], model="embed-unit")

        assert len(result) == 150
        assert len(resource.calls) == 2
        assert len(recording_sink.events) == 2
        # One event per batch response, in batch order — not one for the whole span.
        assert recording_sink.events[0].tokens_in == 1000
        assert recording_sink.events[1].tokens_in == 500
        assert all(e.duration_seconds >= 0.0 for e in recording_sink.events)

    async def test_event_fields_and_attribution(
        self, recording_sink: RecordingSink, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Event shape per spec D-2/D-6; ContextVars land on the event."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        _patch_estimate_cost(monkeypatch, [])
        client, _ = _make_client([_batch_response(1, 42)])
        provider = OpenAIEmbeddingProvider(client=client)

        user_id, novel_id = uuid4(), uuid4()
        set_usage_context(user_id=user_id, novel_id=novel_id)
        try:
            result = await provider.embed_texts(["hello"], model="embed-unit")
        finally:
            set_usage_context(user_id=None, novel_id=None)

        assert len(result) == 1
        assert len(recording_sink.events) == 1
        event = recording_sink.events[0]
        assert event.intent == "embeddings"
        assert event.provider == "openai"
        assert event.model_id == "embed-unit"  # resolved model incl. override param
        assert event.tokens_in == 42
        assert event.tokens_out == 0
        assert event.cache_read_tokens == 0
        assert event.cache_creation_tokens == 0
        assert event.duration_seconds >= 0.0
        assert event.cost_usd == 0.05
        assert event.timestamp.tzinfo is UTC
        assert event.user_id == user_id
        assert event.novel_id == novel_id

    async def test_cost_is_strict(
        self, recording_sink: RecordingSink, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """estimate_cost_usd called with the exact embedding shape (D-3)."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        cost_calls: list[dict[str, object]] = []
        _patch_estimate_cost(monkeypatch, cost_calls)
        client, _ = _make_client([_batch_response(1, 42)])
        provider = OpenAIEmbeddingProvider(client=client)

        await provider.embed_texts(["hello"], model="embed-unit")

        assert cost_calls == [
            {
                "provider": "openai",
                "model_id": "embed-unit",
                "tokens_in": 42,
                "tokens_out": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            }
        ]

    async def test_usage_omitted_skips_event(self, recording_sink: RecordingSink) -> None:
        """Compatible gateway omits usage → no event, no raise, debug log (D-5)."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        client, _ = _make_client([_batch_response(1, None)])
        provider = OpenAIEmbeddingProvider(client=client)

        with capture_logs() as logs:
            result = await provider.embed_texts(["hello"], model="embed-unit")

        assert len(result) == 1  # vectors still returned
        assert recording_sink.events == []
        assert any(
            e.get("event") == "embedding_usage_skipped" and e.get("log_level") == "debug"
            for e in logs
        )

    async def test_garbage_usage_does_not_raise(self, recording_sink: RecordingSink) -> None:
        """Runtime-malformed total_tokens → helper guard swallows, vectors returned."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        client, _ = _make_client([_batch_response(1, "garbage")])
        provider = OpenAIEmbeddingProvider(client=client)

        with capture_logs() as logs:
            result = await provider.embed_texts(["hello"], model="embed-unit")

        assert len(result) == 1  # vectors still returned — telemetry never breaks the run
        assert recording_sink.events == []
        failures = [e for e in logs if e.get("event") == "usage_event_emission_failed"]
        assert len(failures) == 1

    async def test_all_empty_texts_emit_nothing(self, recording_sink: RecordingSink) -> None:
        """All-empty input → zero API calls → zero events."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        client, resource = _make_client([])
        provider = OpenAIEmbeddingProvider(client=client)

        result = await provider.embed_texts(["", "  "], model="embed-unit")

        assert len(result) == 2
        assert all(v == [0.0] * 1536 for v in result)
        assert resource.calls == []
        assert recording_sink.events == []

    async def test_zero_token_response_emits_nothing(self, recording_sink: RecordingSink) -> None:
        """total_tokens == 0 (falsy) → skip per spec D-5."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        client, _ = _make_client([_batch_response(1, 0)])
        provider = OpenAIEmbeddingProvider(client=client)

        result = await provider.embed_texts(["hello"], model="embed-unit")

        assert len(result) == 1
        assert recording_sink.events == []

    async def test_test_provider_emits_nothing(self, recording_sink: RecordingSink) -> None:
        """TestEmbeddingProvider is untouched — emits nothing (D-7)."""
        from narrare_core.llm.embedding_providers import TestEmbeddingProvider

        provider = TestEmbeddingProvider()
        result = await provider.embed_texts(["hello", "world"])

        assert len(result) == 2
        assert recording_sink.events == []


# ---------------------------------------------------------------------------
# Rate math (spec §4 — patching the rates lookup, no models.dev I/O)
# ---------------------------------------------------------------------------


def test_embedding_rate_math(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec §4: embedding-model pricing is input-only (models.dev rates)."""
    monkeypatch.setattr(
        "narrare_core.llm.usage_events.get_rates_strict",
        lambda provider, model_id: {"input": 0.02, "output": 0.0},
    )

    cost = estimate_cost_usd("openai", "text-embedding-3-small", tokens_in=1_000_000, tokens_out=0)

    assert cost == pytest.approx(0.02)
