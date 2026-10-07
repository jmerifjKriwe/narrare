# apps/api/narrare/analytics/repository.py
"""Usage-record repository — DB queries only (RULE-06 / RULE-08).

Persistence and month aggregation for ``UsageRecordRow`` (STATS-002).
Aggregation semantics (spec §3.3/§4, plan Task 6): group by
``(date_trunc('month', created_at AT TIME ZONE 'UTC'), intent, provider,
model_id)`` with call counts, token sums, an OPTIONAL cost sum —
``COALESCE`` to 0 because a bucket may contain only unpriced calls — and
``unpriced_calls`` counted via ``count(*) FILTER (WHERE cost_usd IS NULL)``.
The range is half-open ``[start, end)`` and every read is scoped to the
caller's ``user_id``.

**Timezone guarantee: month buckets are UTC calendar months, independent of
the DB session timezone.** ``date_trunc`` is applied to the naive UTC
timestamp (``created_at AT TIME ZONE 'UTC'``), so a bucket is derived from a
row's UTC wall-clock month regardless of the session's ``TIME ZONE`` GUC —
without the pin, a non-UTC session would truncate in local time and could
mislabel a month's first rows into the previous month.

SQL semantics are verified against real PostgreSQL in
``tests/integration/test_migration_0043_round_trip.py``; the unit tests
exercise query wiring and row mapping with a fake session only (same split
as the notes repository).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare._app.base_repository import BaseRepository
from narrare.analytics.models import UsageRecordRow

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator


@dataclass(frozen=True)
class UsageAggRow:
    """One aggregated bucket keyed by (month, intent, provider, model_id)."""

    month: date  # first day of the bucket month
    intent: str
    provider: str
    model_id: str
    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal  # SUM over priced rows (0 when all unpriced — COALESCE)
    unpriced_calls: int


def _bucket_month(value: datetime | date) -> date:
    """``date_trunc`` (UTC-pinned) yields a naive timestamp; the contract field is a date."""
    return value.date() if isinstance(value, datetime) else value


def _to_decimal(value: Decimal | int | None) -> Decimal:
    """Normalize ``COALESCE(sum(cost_usd), 0)``: NUMERIC sums are Decimal, the fallback 0 is int.

    ``None`` cannot occur behind the COALESCE; mapping it to 0 keeps the
    helper total (defensive) instead of asserting an invariant the type
    system cannot see through the SQL expression.
    """
    if value is None:
        return Decimal("0")
    return value if isinstance(value, Decimal) else Decimal(value)


def _to_agg_row(
    month: datetime | date,
    intent: str,
    provider: str,
    model_id: str,
    calls: int,
    tokens_in: int,
    tokens_out: int,
    cost: Decimal | int,
    unpriced_calls: int,
) -> UsageAggRow:
    """Map one result row (positional, SELECT column order) onto the contract."""
    return UsageAggRow(
        month=_bucket_month(month),
        intent=intent,
        provider=provider,
        model_id=model_id,
        calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=_to_decimal(cost),
        unpriced_calls=unpriced_calls,
    )


class UsageRecordRepository(BaseRepository):
    """Persistence + monthly aggregation for AI cost-tracking usage records."""

    async def insert(self, row: UsageRecordRow) -> None:
        """Append one usage event (append-only telemetry — spec §3.4)."""
        self._session.add(row)
        await self._flush()

    async def aggregate_range(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> list[UsageAggRow]:
        """Monthly cost buckets for one user, half-open ``[start, end)``.

        Buckets are UTC calendar months (see module docstring), independent
        of the DB session timezone. Rows are ordered by month, then cost
        (descending). Callers get an empty list when the range contains no
        usage for the user.
        """
        month_bucket = func.date_trunc(
            "month", UsageRecordRow.created_at.op("AT TIME ZONE")("UTC")
        ).label("month")
        cost_sum = func.coalesce(func.sum(UsageRecordRow.cost_usd), 0).label("cost_usd")
        stmt = (
            select(
                month_bucket,
                UsageRecordRow.intent,
                UsageRecordRow.provider,
                UsageRecordRow.model_id,
                func.count().label("calls"),
                func.sum(UsageRecordRow.tokens_in).label("tokens_in"),
                func.sum(UsageRecordRow.tokens_out).label("tokens_out"),
                cost_sum,
                func.count().filter(UsageRecordRow.cost_usd.is_(None)).label("unpriced_calls"),
            )
            .where(
                UsageRecordRow.user_id == user_id,
                UsageRecordRow.created_at >= start,  # [start, end) — half-open
                UsageRecordRow.created_at < end,
            )
            .group_by(
                month_bucket,
                UsageRecordRow.intent,
                UsageRecordRow.provider,
                UsageRecordRow.model_id,
            )
            .order_by(month_bucket.asc(), cost_sum.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_agg_row(*row) for row in result.all()]

    async def month_spend_by_user(self, start: datetime) -> dict[uuid.UUID, Decimal]:
        """Per-user priced spend at/after *start* — guard hydration (ADR-094 D5).

        One GROUP BY over ALL users (no user scoping — the budget guard
        arms every wallet at once): ``COALESCE(SUM(cost_usd), 0)`` so a
        user with only unpriced rows surfaces as ``Decimal("0")`` rather
        than being absent. Priced rows only — SQL ``SUM`` skips NULLs, so
        unpriced calls never count toward a USD budget (ADR-094 D8
        honesty). No upper bound: the caller passes the current UTC month
        start, and the month is open on the write side.
        """
        stmt = (
            select(
                UsageRecordRow.user_id,
                func.coalesce(func.sum(UsageRecordRow.cost_usd), 0),
            )
            .where(UsageRecordRow.created_at >= start)
            .group_by(UsageRecordRow.user_id)
        )
        result = await self._session.execute(stmt)
        return {user_id: _to_decimal(total) for user_id, total in result.all()}

    async def stream_month(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> AsyncIterator[UsageRecordRow]:
        """Stream raw usage rows for one window, half-open ``[start, end)``.

        The CSV export source (spec B-4): user-scoped, ``created_at`` order,
        ``yield_per``-chunked row iteration — rows are pulled lazily from a
        server-side cursor, so no full-month list is ever held in memory.
        """
        stmt = (
            select(UsageRecordRow)
            .where(
                UsageRecordRow.user_id == user_id,
                UsageRecordRow.created_at >= start,  # [start, end) — half-open
                UsageRecordRow.created_at < end,
            )
            .order_by(UsageRecordRow.created_at.asc())
            # 500 rows per server-side cursor fetch: constant memory for
            # month-wide exports (spec B-4). Pinned query-shape literal —
            # a technical cursor property of THIS query, not a config knob.
            .execution_options(yield_per=500)
        )
        result = await self._session.stream_scalars(stmt)
        async for row in result:
            yield row
