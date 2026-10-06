# apps/api/narrare/analytics/repository.py
"""Usage-record repository — DB queries only (RULE-06 / RULE-08).

Persistence and month aggregation for ``UsageRecordRow`` (STATS-002).
Aggregation semantics (spec §3.5): group by
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


def _to_decimal(value: Decimal | int) -> Decimal:
    """Normalize ``COALESCE(sum(cost_usd), 0)``: NUMERIC sums are Decimal, the fallback 0 is int."""
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
