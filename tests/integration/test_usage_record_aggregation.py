# tests/integration/test_usage_record_aggregation.py
"""UsageRecordRepository aggregation semantics against real PostgreSQL.

Split from ``test_migration_0043_round_trip.py`` for the RULE-04 file-size
limit (same wiring-unit / semantics-integration split as the notes
repository): the round-trip file proves migration 0043's schema contracts,
this file proves the aggregation SQL itself — the unit tests carry a fake
session only. Covered here on real PostgreSQL: ``date_trunc`` month
bucketing (UTC-pinned by the repository), token/cost sums, COALESCE for an
unpriced-only bucket, ``count(*) FILTER`` unpriced_calls, half-open
``[start, end)`` bounds and per-user attribution isolation.

Tests carry ``@pytest.mark.schema_mutating`` so ``just test`` and CI run them
in the dedicated SERIAL phase: each re-asserts ``upgrade head`` via alembic
and must never race the round-trip file's mid-run downgrade (nor another
xdist worker's alembic call).
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.analytics.models import UsageRecordRow
from narrare.analytics.repository import UsageRecordRepository
from tests.integration._usage_record_test_support import (
    JAN_1,
    engine,
    run_alembic,
    seed_user,
)

_MAR_1 = datetime(2026, 3, 1, tzinfo=UTC)
_APR_1 = datetime(2026, 4, 1, tzinfo=UTC)


def _usage(
    user_id: _uuid.UUID,
    *,
    when: datetime,
    intent: str,
    provider: str,
    model: str,
    tin: int,
    tout: int,
    cost: Decimal | None,
) -> UsageRecordRow:
    return UsageRecordRow(
        user_id=user_id,
        intent=intent,
        provider=provider,
        model_id=model,
        tokens_in=tin,
        tokens_out=tout,
        duration_ms=100,
        cost_usd=cost,
        created_at=when,
    )


@pytest.mark.schema_mutating
class TestUsageRecordAggregation:
    """Repository aggregation semantics on real PG."""

    async def test_aggregate_range_semantics_on_real_pg(self) -> None:
        """Bucketing, sums, COALESCE, FILTER count, [start, end) and isolation."""
        run_alembic("upgrade", "head")

        user_a = _uuid.uuid4()
        user_b = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await seed_user(conn, user_a)
                await seed_user(conn, user_b)

            async with AsyncSession(eng) as session:
                # Deterministic month bucketing regardless of the server's TZ GUC.
                await session.execute(sqlalchemy.text("SET TIME ZONE 'UTC'"))
                repo = UsageRecordRepository(session)

                # user_a: priced Jan bucket (2 calls), unpriced Jan bucket
                # (1 row mid-month + 1 row EXACTLY at start — proves >=),
                # priced Feb bucket, and a row EXACTLY at end (proves <).
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 10, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=100,
                        tout=10,
                        cost=Decimal("0.001"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 20, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=50,
                        tout=20,
                        cost=Decimal("0.002"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 15, 12, tzinfo=UTC),
                        intent="write",
                        provider="openai",
                        model="gpt-x",
                        tin=70,
                        tout=40,
                        cost=None,
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=JAN_1,
                        intent="write",
                        provider="openai",
                        model="gpt-x",
                        tin=30,
                        tout=5,
                        cost=None,
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 2, 10, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=80,
                        tout=60,
                        cost=Decimal("0.004"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=_MAR_1,
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=11,
                        tout=12,
                        cost=Decimal("0.009"),
                    )
                )
                # user_b interleaves the SAME month/model as user_a.
                await repo.insert(
                    _usage(
                        user_b,
                        when=datetime(2026, 1, 25, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=1000,
                        tout=100,
                        cost=Decimal("0.999"),
                    )
                )

                rows_a = await repo.aggregate_range(user_a, JAN_1, _MAR_1)
                rows_a_full = await repo.aggregate_range(user_a, JAN_1, _APR_1)
                rows_b = await repo.aggregate_range(user_b, JAN_1, _APR_1)

            jan_priced, jan_unpriced, feb = rows_a

            # Month bucketing: date_trunc → first-of-month date (strictly date).
            assert [r.month for r in rows_a] == [date(2026, 1, 1)] * 2 + [date(2026, 2, 1)]
            assert all(type(r.month) is date for r in rows_a)
            # Order: month asc, then cost desc within the month.
            assert [(r.intent, r.model_id) for r in rows_a] == [
                ("summarize", "claude-haiku"),
                ("write", "gpt-x"),
                ("summarize", "claude-haiku"),
            ]
            # Sums + priced bucket.
            assert (jan_priced.calls, jan_priced.tokens_in, jan_priced.tokens_out) == (2, 150, 30)
            assert jan_priced.cost_usd == Decimal("0.003")
            assert jan_priced.unpriced_calls == 0
            # Unpriced-only bucket: COALESCE cost 0, FILTER count 2 (incl. the
            # at-start row → start bound is INCLUSIVE, [ not (.
            assert jan_unpriced.calls == 2
            assert jan_unpriced.tokens_in == 100
            assert jan_unpriced.cost_usd == Decimal("0")
            assert jan_unpriced.unpriced_calls == 2
            # Feb bucket.
            assert feb.calls == 1
            assert feb.cost_usd == Decimal("0.004")
            # Half-open upper bound: the at-end row is NOT in [Jan, Mar) ...
            assert len(rows_a) == 3
            # ... but exists as its own March bucket in [Jan, Apr).
            assert rows_a_full[-1].month == date(2026, 3, 1)
            assert (rows_a_full[-1].calls, rows_a_full[-1].cost_usd) == (1, Decimal("0.009"))
            # Attribution isolation: user_b sees only their own bucket; none of
            # user_a's rows leak into it (and vice versa).
            assert len(rows_b) == 1
            assert (rows_b[0].calls, rows_b[0].tokens_in) == (1, 1000)
            assert rows_b[0].cost_usd == Decimal("0.999")
            assert all(r.cost_usd != Decimal("0.999") for r in rows_a_full)
        finally:
            await eng.dispose()

    async def test_aggregate_range_month_bucketing_is_utc_regardless_of_session_tz(self) -> None:
        """First/last-day UTC rows keep their UTC bucket under a non-UTC session TZ.

        Regression guard for the review finding: with a bare
        ``date_trunc('month', created_at)`` PG truncates in the SESSION
        timezone — under ``Europe/Berlin``, 2026-02-01T00:10Z would be cut to
        Jan 31 Berlin (= Jan 31 bucket) and 2026-02-28T23:30Z to Mar 1 Berlin
        (a bogus Feb 28 bucket). The repository pins
        ``created_at AT TIME ZONE 'UTC'``, so both rows land in the single
        February UTC bucket. The session TZ here is deliberately non-UTC.
        """
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await seed_user(conn, user_id)

            async with AsyncSession(eng) as session:
                await session.execute(sqlalchemy.text("SET TIME ZONE 'Europe/Berlin'"))
                repo = UsageRecordRepository(session)
                await repo.insert(
                    _usage(
                        user_id,
                        when=datetime(2026, 2, 1, 0, 10, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=10,
                        tout=20,
                        cost=Decimal("0.001"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_id,
                        when=datetime(2026, 2, 28, 23, 30, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=30,
                        tout=40,
                        cost=Decimal("0.002"),
                    )
                )

                rows = await repo.aggregate_range(
                    user_id,
                    datetime(2026, 1, 1, tzinfo=UTC),
                    datetime(2026, 3, 1, tzinfo=UTC),
                )

            # ONE shared February bucket — session-tz truncation would have
            # produced two buckets (Jan 31 + Feb 28) instead.
            assert len(rows) == 1
            assert rows[0].month == date(2026, 2, 1)
            assert rows[0].calls == 2
            assert rows[0].cost_usd == Decimal("0.003")
        finally:
            await eng.dispose()

    async def test_month_spend_by_user_hydration_semantics_on_real_pg(self) -> None:
        """Guard hydration (ADR-094 D5): per-user sums, NULL-skipping, >= start.

        ``month_spend_by_user`` is the budget guard's startup-hydration
        source: all users at once, priced rows only (SUM skips NULLs —
        unpriced calls never count toward a USD budget, ADR-094 D8), the
        ``>= start`` bound inclusive at the month start, and no upper bound
        (the current month is open on the write side).
        """
        run_alembic("upgrade", "head")

        user_a = _uuid.uuid4()
        user_b = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await seed_user(conn, user_a)
                await seed_user(conn, user_b)

            async with AsyncSession(eng) as session:
                repo = UsageRecordRepository(session)

                # user_a: priced rows in two months (the guard's window spans
                # everything at/after the month start), one EXACTLY at start
                # (proves >=), and an unpriced row that must NOT count.
                for when, cost in (
                    (JAN_1, Decimal("0.050")),  # at start — inclusive
                    (datetime(2026, 1, 10, 12, tzinfo=UTC), Decimal("0.001")),
                    (datetime(2026, 1, 15, 12, tzinfo=UTC), None),  # skipped
                    (datetime(2026, 2, 10, 12, tzinfo=UTC), Decimal("0.004")),
                ):
                    await repo.insert(
                        _usage(
                            user_a,
                            when=when,
                            intent="summarize",
                            provider="anthropic",
                            model="claude-haiku",
                            tin=10,
                            tout=5,
                            cost=cost,
                        )
                    )
                # user_b interleaves the same month — per-user isolation.
                await repo.insert(
                    _usage(
                        user_b,
                        when=datetime(2026, 1, 25, 12, tzinfo=UTC),
                        intent="write",
                        provider="openai",
                        model="gpt-x",
                        tin=90,
                        tout=9,
                        cost=Decimal("0.999"),
                    )
                )

                from_jan = await repo.month_spend_by_user(JAN_1)
                from_feb = await repo.month_spend_by_user(datetime(2026, 2, 1, tzinfo=UTC))

            assert from_jan[user_a] == Decimal("0.055")  # 0.050 + 0.001 + 0.004
            assert from_jan[user_b] == Decimal("0.999")
            assert from_feb == {user_a: Decimal("0.004")}  # user_b: no rows
        finally:
            await eng.dispose()
