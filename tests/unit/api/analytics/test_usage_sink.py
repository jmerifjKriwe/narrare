# tests/unit/api/analytics/test_usage_sink.py
"""Unit tests for ``SqlUsageEventSink`` (STATS-002, spec §3.3/§3.4, ADR-093).

App-side adapter between the guarded Core emission seam and the analytics
repository: one session per event, event → row mapping (seconds→ms,
float→Decimal money, ``created_at`` from the event — never DB now()),
insert + commit. Per the brief the repository is replaced by a recording
fake; gate F2 drops unattributed events (debug log, no session opened —
they have no query surface); the sink never catches its own exceptions,
the Core emitter guard is the single enforcement point. The repository
itself is unit-tested in test_usage_record_repository.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.analytics import usage_sink
from narrare.analytics.usage_sink import SqlUsageEventSink
from narrare_core.llm.usage_events import UsageEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.analytics.models import UsageRecordRow

# ---------------------------------------------------------------------------
# Fakes (ADR-030: real fakes, no MagicMock)
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal ``AsyncSession`` fake: records ``commit`` in the shared op log."""

    def __init__(self, ops: list[str]) -> None:
        self._ops = ops

    async def commit(self) -> None:
        self._ops.append("commit")


class _FakeSessionCtx:
    """Async context manager — mirrors ``async with factory() as session``."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        del args


class _FakeSessionFactory:
    """Stands in for ``async_sessionmaker[AsyncSession]``; logs session opens."""

    def __init__(self, ops: list[str]) -> None:
        self._ops = ops
        self.opened = 0

    def __call__(self) -> _FakeSessionCtx:
        self._ops.append("open")
        self.opened += 1
        return _FakeSessionCtx(_FakeSession(self._ops))


@dataclass
class _Harness:
    """Sink wired to fakes + captured bookkeeping (op log, inserted rows)."""

    sink: SqlUsageEventSink
    factory: _FakeSessionFactory
    inserted: list[Any] = field(default_factory=list)
    ops: list[str] = field(default_factory=list)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    """Sink with the module's repository replaced by a recording fake."""
    ops: list[str] = []
    inserted: list[Any] = []
    factory = _FakeSessionFactory(ops)

    class _FakeRepository:
        def __init__(self, session: _FakeSession) -> None:
            self.session = session

        async def insert(self, row: UsageRecordRow) -> None:
            inserted.append(row)
            ops.append("insert")

    monkeypatch.setattr(usage_sink, "UsageRecordRepository", _FakeRepository)
    # cast: the sanctioned seam for a fake where async_sessionmaker is declared.
    sink = SqlUsageEventSink(cast("async_sessionmaker[AsyncSession]", factory))
    return _Harness(sink=sink, factory=factory, inserted=inserted, ops=ops)


# ---------------------------------------------------------------------------
# Event factory
# ---------------------------------------------------------------------------


def _make_event(**overrides: Any) -> UsageEvent:
    defaults: dict[str, Any] = {
        "timestamp": datetime(2026, 1, 15, 12, 30, tzinfo=UTC),
        "intent": "summarize",
        "provider": "anthropic",
        "model_id": "claude-haiku",
        "tokens_in": 1200,
        "tokens_out": 340,
        "cache_read_tokens": 100,
        "cache_creation_tokens": 20,
        "duration_seconds": 1.2349,  # → 1235 ms (rounded)
        "cost_usd": 0.001234,
        "user_id": uuid4(),
        "novel_id": uuid4(),
    }
    defaults.update(overrides)
    return UsageEvent(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSqlUsageEventSink:
    async def test_record_with_none_user_id_skips_without_session_or_insert(
        self, harness: _Harness
    ) -> None:
        with capture_logs() as logs:
            await harness.sink.record(_make_event(user_id=None))

        assert harness.factory.opened == 0  # no session opened
        assert harness.inserted == []  # nothing persisted
        skipped = [entry for entry in logs if entry["event"] == "usage_event_skipped_unattributed"]
        assert len(skipped) == 1
        assert skipped[0]["log_level"] == "debug"

    async def test_record_maps_event_fields_onto_row(self, harness: _Harness) -> None:
        event = _make_event()

        await harness.sink.record(event)

        assert len(harness.inserted) == 1
        row = harness.inserted[0]
        assert row.user_id == event.user_id
        assert row.novel_id == event.novel_id
        assert row.intent == "summarize"
        assert row.provider == "anthropic"
        assert row.model_id == "claude-haiku"
        assert row.tokens_in == 1200
        assert row.tokens_out == 340
        assert row.cache_read_tokens == 100
        assert row.cache_creation_tokens == 20
        assert row.duration_ms == 1235  # round(1.2349 * 1000)
        assert row.cost_usd == Decimal("0.001234")  # Decimal, not float
        assert row.created_at == event.timestamp  # from event, not DB now()

    async def test_record_without_cost_persists_unpriced_null_cost(self, harness: _Harness) -> None:
        await harness.sink.record(_make_event(cost_usd=None))
        assert harness.inserted[0].cost_usd is None

    async def test_record_without_novel_persists_null_novel(self, harness: _Harness) -> None:
        await harness.sink.record(_make_event(novel_id=None))
        assert harness.inserted[0].novel_id is None

    async def test_record_opens_single_session_and_commits_after_insert(
        self, harness: _Harness
    ) -> None:
        await harness.sink.record(_make_event())

        assert harness.factory.opened == 1  # own session per event
        assert harness.ops == ["open", "insert", "commit"]  # commit after insert
