# tests/unit/api/analytics/test_usage_record_repository.py
"""Unit tests for ``UsageRecordRepository`` wiring + row mapping (fake session).

Mirrors ``tests/unit/api/notes/test_repository.py`` (fake-session repository
unit tests): the repository is a thin SQLAlchemy wrapper — these tests pin
the query wiring (caller user scope bind, half-open ``[start, end)`` bounds,
group/order keys, insert flush bookkeeping) and the DB-row → ``UsageAggRow``
mapping (date-trunc timestamp → ``date``, COALESCE'd cost → ``Decimal``)
without a real database. Aggregation SQL semantics (date_trunc bucketing,
``count(*) FILTER``, COALESCE, half-open bounds, attribution isolation) are
proven against real PostgreSQL in
``tests/integration/test_migration_0043_round_trip.py``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from tests.fakes.fake_db_session import FakeDbSession

from narrare.analytics.models import UsageRecordRow
from narrare.analytics.repository import UsageAggRow, UsageRecordRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _RowsResult:
    """Simulates a SQLAlchemy ``Result`` exposing ``all()`` (row tuples)."""

    def __init__(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self._rows = list(rows)

    def all(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _AggSession:
    """Minimal ``AsyncSession`` fake: preset aggregate rows + bookkeeping.

    The shared ``FakeDbSession`` covers scalar results only; the aggregate
    query reads whole rows via ``result.all()`` — the same reason the KB
    repository tests carry a local fake (test_relationship_repository.py).
    """

    def __init__(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self._rows = list(rows)
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> _RowsResult:
        self.statements.append(stmt)
        return _RowsResult(self._rows)


class _ScalarsResult:
    """Async-iterable scalar result — what ``stream_scalars()`` returns."""

    def __init__(self, rows: Sequence[UsageRecordRow]) -> None:
        self._iterator = iter(rows)

    def __aiter__(self) -> _ScalarsResult:
        return self

    async def __anext__(self) -> UsageRecordRow:
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _StreamSession:
    """Minimal ``AsyncSession`` fake for the streaming query (``stream``).

    Companion to ``_AggSession``: the stream path iterates scalars lazily
    instead of materializing ``result.all()``.
    """

    def __init__(self, rows: Sequence[UsageRecordRow]) -> None:
        self._rows = list(rows)
        self.statements: list[Any] = []

    async def stream_scalars(self, stmt: Any) -> _ScalarsResult:
        self.statements.append(stmt)
        return _ScalarsResult(self._rows)


def _make_repo(session: FakeDbSession | _AggSession) -> UsageRecordRepository:
    """Wrap a fake session in a repository.

    ``cast`` (not ``# type: ignore[arg-type]``) is the RULE-23-sanctioned
    seam for passing a fake where an ``AsyncSession`` is declared.
    """
    return UsageRecordRepository(cast("AsyncSession", session))


# ---------------------------------------------------------------------------
# Fixtures / seed data
# ---------------------------------------------------------------------------

_JAN = datetime(2026, 1, 1)
_FEB = datetime(2026, 2, 1)


def _seed_rows() -> list[tuple[Any, ...]]:
    """Aggregate rows as PostgreSQL would return them (month asc, cost desc).

    Two months, two intents, one unpriced bucket — the COALESCE'd cost of an
    all-unpriced bucket arrives as int ``0`` (asyncpg keeps NUMERIC sums as
    ``Decimal``; the coalesce fallback is a plain 0).
    """
    return [
        (_JAN, "summarize", "anthropic", "claude-haiku", 2, 150, 30, Decimal("0.003"), 0),
        (_JAN, "write", "openai", "gpt-x", 1, 50, 60, 0, 1),
        (_FEB, "summarize", "anthropic", "claude-haiku", 1, 70, 40, Decimal("0.004"), 0),
    ]


def _usage_row(**overrides: Any) -> UsageRecordRow:
    defaults: dict[str, Any] = {
        "user_id": uuid4(),
        "intent": "summarize",
        "provider": "anthropic",
        "model_id": "claude-haiku",
        "tokens_in": 10,
        "tokens_out": 20,
        "duration_ms": 500,
        "created_at": datetime(2026, 1, 10, tzinfo=UTC),
    }
    defaults.update(overrides)
    return UsageRecordRow(**defaults)


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------


class TestUsageRecordRepositoryInsert:
    async def test_insert_adds_row_and_flushes_once_without_refresh(self) -> None:
        """insert() appends the row and flushes; no refresh (no server defaults)."""
        session = FakeDbSession()
        repo = _make_repo(session)
        row = _usage_row()

        await repo.insert(row)

        assert session.added == [row]
        assert session.flush_count == 1
        assert session.refreshed == []


# ---------------------------------------------------------------------------
# Aggregate mapping (row tuple → UsageAggRow)
# ---------------------------------------------------------------------------


class TestUsageRecordRepositoryAggMapping:
    async def test_aggregate_range_maps_rows_preserving_db_order(self) -> None:
        """Rows map 1:1 onto UsageAggRow; DB order (month asc, cost desc) kept."""
        session = _AggSession(_seed_rows())
        repo = _make_repo(session)

        result = await repo.aggregate_range(
            uuid4(), datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC)
        )

        assert [type(row) for row in result] == [UsageAggRow] * 3
        first, second, third = result
        # Bucketing: date-trunc timestamp → calendar date (first of month).
        assert first.month == date(2026, 1, 1)
        assert isinstance(first.month, date)
        assert (first.intent, first.provider, first.model_id) == (
            "summarize",
            "anthropic",
            "claude-haiku",
        )
        assert (first.calls, first.tokens_in, first.tokens_out) == (2, 150, 30)
        assert first.cost_usd == Decimal("0.003")
        assert first.unpriced_calls == 0
        assert second.intent == "write"
        assert third.month == date(2026, 2, 1)

    async def test_aggregate_rows_are_frozen(self) -> None:
        """UsageAggRow is frozen — consumers (Tasks 7/8) can rely on immutability."""
        session = _AggSession(_seed_rows())
        repo = _make_repo(session)

        result = await repo.aggregate_range(uuid4(), _JAN, datetime(2026, 3, 1))

        with pytest.raises(FrozenInstanceError):
            # Explicit __setattr__ call: exactly what the assignment statement
            # compiles to — the frozen dataclass __setattr__ raises at runtime
            # (ruff B010 rejects the setattr() form, pyright rejects attribute
            # assignment on frozen dataclasses; RULE-23 forbids type: ignore).
            result[0].__setattr__("cost_usd", Decimal("99"))

    async def test_aggregate_coalesce_zero_is_normalized_to_decimal(self) -> None:
        """An all-unpriced bucket's COALESCE fallback (int 0) becomes Decimal."""
        session = _AggSession([row for row in _seed_rows() if row[1] == "write"])
        repo = _make_repo(session)

        result = await repo.aggregate_range(uuid4(), _JAN, datetime(2026, 3, 1))

        assert len(result) == 1
        assert isinstance(result[0].cost_usd, Decimal)
        assert result[0].cost_usd == Decimal("0")
        assert result[0].unpriced_calls == 1


# ---------------------------------------------------------------------------
# Aggregate query wiring
# ---------------------------------------------------------------------------


def _created_at_bounds(session: _AggSession) -> list[tuple[str, Any]]:
    """(operator-name, bound-value) of the created_at WHERE criteria.

    Companion to the notes-repo ``_user_id_bind`` helper: a refactor flipping
    ``>=``/``<`` (breaking ``[start, end)``) or dropping a bound fails here.
    """
    bounds: list[tuple[str, Any]] = []
    for crit in session.statements[0].whereclause.clauses:
        if crit.left.name == "created_at":
            bounds.append((crit.operator.__name__, crit.right.value))
    return bounds


class TestUsageRecordRepositoryAggWiring:
    async def test_aggregate_range_binds_caller_user_id_exclusively(self) -> None:
        """Exactly one user_id bind — the CALLER's id (attribution scoping).

        True cross-user invisibility is proven against real PostgreSQL in the
        integration round-trip test; here the scope bind is pinned so a
        dropped ``user_id ==`` condition fails the unit suite.
        """
        session = _AggSession([])
        repo = _make_repo(session)
        user_id = uuid4()

        await repo.aggregate_range(user_id, _JAN, datetime(2026, 3, 1))

        params = session.statements[0].compile().params
        user_binds = {key: value for key, value in params.items() if key.startswith("user_id")}
        assert list(user_binds.values()) == [user_id]

    async def test_aggregate_range_bounds_are_half_open(self) -> None:
        """Range is [start, end): created_at >= start AND created_at < end."""
        session = _AggSession([])
        repo = _make_repo(session)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 3, 1, tzinfo=UTC)

        await repo.aggregate_range(uuid4(), start, end)

        bounds = _created_at_bounds(session)
        assert [(op, value) for op, value in bounds] == [("ge", start), ("lt", end)]

    async def test_aggregate_range_groups_by_month_intent_provider_model(self) -> None:
        """GROUP BY = (date_trunc month, intent, provider, model_id)."""
        session = _AggSession([])
        repo = _make_repo(session)

        await repo.aggregate_range(uuid4(), _JAN, datetime(2026, 3, 1))

        grouped = session.statements[0]._group_by_clauses
        # SA renders the labeled bucket as a GROUP BY alias reference (valid PG).
        assert [clause.name for clause in grouped] == [
            "month",
            "intent",
            "provider",
            "model_id",
        ]
        assert grouped[0].element.name == "date_trunc"
        # Deterministic UTC bucketing (review finding): the truncation argument
        # must be `created_at AT TIME ZONE 'UTC'` — not a bare `created_at`,
        # which date_trunc would cut in the SESSION timezone (a non-UTC
        # session could then mislabel a month's first rows into the previous
        # month). Real-PG proof: integration round-trip test.
        tz_arg = list(grouped[0].element.clauses)[1]
        assert tz_arg.operator.opstring == "AT TIME ZONE"
        assert tz_arg.left.name == "created_at"
        assert tz_arg.right.value == "UTC"

    async def test_aggregate_range_orders_by_month_then_cost_desc(self) -> None:
        """ORDER BY = month ascending, then cost sum descending."""
        session = _AggSession([])
        repo = _make_repo(session)

        await repo.aggregate_range(uuid4(), _JAN, datetime(2026, 3, 1))

        ordered = session.statements[0]._order_by_clauses
        assert len(ordered) == 2
        assert str(ordered[1]).endswith("DESC")


# ---------------------------------------------------------------------------
# stream_month (CSV export source, spec B-4 — moved from test_costs_export
# to stay under the RULE-04 test-file limit; this is its natural home)
# ---------------------------------------------------------------------------


class TestUsageRecordRepositoryStreamMonth:
    async def test_stream_month_yields_rows_preserving_session_order(self) -> None:
        """Rows stream out 1:1 in the order the cursor produced them."""
        rows = [_usage_row(), _usage_row(created_at=datetime(2026, 1, 11))]
        session = _StreamSession(rows)
        repo = _make_repo(session)

        streamed = [row async for row in repo.stream_month(uuid4(), _JAN, _FEB)]

        assert streamed == rows

    async def test_stream_month_binds_caller_user_id_exclusively(self) -> None:
        """Exactly one user_id bind — the CALLER's id (attribution scoping)."""
        session = _StreamSession([])
        repo = _make_repo(session)
        user_id = uuid4()

        await anext(repo.stream_month(user_id, _JAN, _FEB), None)

        params = session.statements[0].compile().params
        user_binds = {key: value for key, value in params.items() if key.startswith("user_id")}
        assert list(user_binds.values()) == [user_id]

    async def test_stream_month_bounds_are_half_open(self) -> None:
        """Range is [start, end): created_at >= start AND created_at < end."""
        session = _StreamSession([])
        repo = _make_repo(session)

        await anext(repo.stream_month(uuid4(), _JAN, _FEB), None)

        bounds = [
            (crit.operator.__name__, crit.right.value)
            for crit in session.statements[0].whereclause.clauses
            if crit.left.name == "created_at"
        ]
        assert bounds == [("ge", _JAN), ("lt", _FEB)]

    async def test_stream_month_orders_by_created_at_ascending(self) -> None:
        """ORDER BY = created_at ascending (spec B-4: created_at order)."""
        session = _StreamSession([])
        repo = _make_repo(session)

        await anext(repo.stream_month(uuid4(), _JAN, _FEB), None)

        ordered = session.statements[0]._order_by_clauses
        assert len(ordered) == 1
        assert "created_at" in str(ordered[0])
        assert str(ordered[0]).endswith("ASC")

    async def test_stream_month_streams_in_yield_per_chunks(self) -> None:
        """Chunked row iteration (yield_per) — NOT an unbuffered full fetch."""
        session = _StreamSession([])
        repo = _make_repo(session)

        await anext(repo.stream_month(uuid4(), _JAN, _FEB), None)

        options = session.statements[0]._execution_options
        assert options.get("yield_per") == 500  # repository's pinned chunk
