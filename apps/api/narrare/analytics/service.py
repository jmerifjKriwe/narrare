# apps/api/narrare/analytics/service.py
"""Cost query service — monthly AI cost reports (STATS-002, spec §4).

Fetches ONE aggregation window (default: six months, the spec contract) from
``UsageRecordRepository`` and buckets the rows Python-side into a
:class:`CostMonthReport`: month-scoped totals/by-intent/by-model breakdowns
plus an oldest-first trend (zero months included). Breakdown rows are sorted
by cost (descending) on the exact ``Decimal`` sums before the boundary
``float()`` conversions.

Documented simplification (spec §4): ``month=None`` resolves to the current
SERVER-LOCAL month, while repository buckets are UTC calendar months — near a
month boundary a server in a non-UTC timezone can attribute edge-of-month
usage to the neighboring bucket. ``UsageAggRow.month`` is presented as UTC
and is never re-localized here.
RULE-06: no SQL, no HTTP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import MAXYEAR, MINYEAR, UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from narrare.analytics._csv_format import header_line, usage_record_line
from narrare.analytics.contracts import (
    CostIntentRow,
    CostModelRow,
    CostMonthReport,
    CostTotals,
    CostTrendPoint,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from narrare.analytics.repository import UsageAggRow, UsageRecordRepository

logger = structlog.get_logger(__name__)

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class InvalidMonthError(ValueError):
    """The requested month is not a ``YYYY-MM`` string with a 01-12 month, or
    its trend window is not constructible (edge years outside 0001-9999)."""


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Shift a (year, month) pair by ``delta`` months (year-wrap safe)."""
    total = year * 12 + month - 1 + delta
    return total // 12, total % 12 + 1


def _month_label(year: int, month: int) -> str:
    """Canonical report/trend month key (``YYYY-MM``)."""
    return f"{year:04d}-{month:02d}"


def _month_start(year: int, month: int) -> datetime:
    """UTC midnight on the first of the month — the repository's window unit."""
    return datetime(year, month, 1, tzinfo=UTC)


def _resolve_month(month: str | None) -> tuple[int, int]:
    """(year, month) for the request; ``None`` → current server-local month.

    Raises:
        InvalidMonthError: If ``month`` is not ``YYYY-MM`` with month 01-12.
    """
    if month is None:
        now = datetime.now().astimezone()
        return now.year, now.month
    if _MONTH_PATTERN.match(month) is None:
        raise InvalidMonthError(f"Invalid month {month!r}; expected YYYY-MM (e.g. 2026-03)")
    return int(month[:4]), int(month[5:7])


def _validate_window(year: int, month: int, *, trend_months: int) -> None:
    """Reject months whose trend window is not constructible (Task 7 rider).

    The window ``[month-(trend-1), month+1)`` must stay inside datetime's
    constructible year range (``MINYEAR``-``MAXYEAR``): regex-valid months
    like ``0000-01`` (window start year -1) or ``9999-12`` (window end year
    10000) would otherwise crash with a bare ``ValueError`` at
    :func:`_month_start` — surfacing as HTTP 500 instead of 422.

    Raises:
        InvalidMonthError: If either window edge year is out of range.
    """
    for offset in (-(trend_months - 1), 1):
        edge_year, _ = _shift_month(year, month, offset)
        if not MINYEAR <= edge_year <= MAXYEAR:
            raise InvalidMonthError(
                f"Month {_month_label(year, month)} is outside the reportable "
                f"range: its {trend_months}-month window leaves the constructible "
                f"year range {MINYEAR:04d}-{MAXYEAR:04d}"
            )


@dataclass
class _Bucket:
    """Mutable accumulator for one intent/model/month slice."""

    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    unpriced_calls: int = 0

    def add(self, row: UsageAggRow) -> None:
        self.calls += row.calls
        self.tokens_in += row.tokens_in
        self.tokens_out += row.tokens_out
        self.cost_usd += row.cost_usd
        self.unpriced_calls += row.unpriced_calls


class CostQueryService:
    """Builds monthly cost reports; implements ``CostQueryServiceProtocol``.

    The trend window length is injected (RULE-18: no hardcoded operational
    constants) and defaults to the spec §4 contract of six months.
    """

    def __init__(self, repo: UsageRecordRepository, *, trend_months: int = 6) -> None:
        if trend_months < 1:
            raise ValueError("trend_months must be >= 1")
        self._repo = repo
        self._trend_months = trend_months

    async def month_report(self, user_id: uuid.UUID, month: str | None) -> CostMonthReport:
        """Window report ending with the requested (or current) month."""
        year, mon = _resolve_month(month)
        _validate_window(year, mon, trend_months=self._trend_months)
        first_offset = -(self._trend_months - 1)
        window_start = _month_start(*_shift_month(year, mon, first_offset))
        window_end = _month_start(*_shift_month(year, mon, 1))
        rows = await self._repo.aggregate_range(user_id, window_start, window_end)

        requested = date(year, mon, 1)
        trend_costs: dict[date, Decimal] = {
            _month_start(*_shift_month(year, mon, offset)).date(): Decimal("0")
            for offset in range(first_offset, 1)
        }
        totals = _Bucket()
        by_intent: dict[str, _Bucket] = {}
        by_model: dict[tuple[str, str], _Bucket] = {}
        for row in rows:
            if row.month == requested:
                totals.add(row)
                by_intent.setdefault(row.intent, _Bucket()).add(row)
                by_model.setdefault((row.provider, row.model_id), _Bucket()).add(row)
            if row.month in trend_costs:
                trend_costs[row.month] += row.cost_usd

        report = CostMonthReport(
            month=_month_label(year, mon),
            totals=CostTotals(
                calls=totals.calls,
                tokens_in=totals.tokens_in,
                tokens_out=totals.tokens_out,
                cost_usd=float(totals.cost_usd),
                unpriced_calls=totals.unpriced_calls,
            ),
            by_intent=[
                CostIntentRow(
                    intent=intent,
                    calls=bucket.calls,
                    cost_usd=float(bucket.cost_usd),
                    unpriced_calls=bucket.unpriced_calls,
                )
                for intent, bucket in sorted(
                    by_intent.items(), key=lambda item: item[1].cost_usd, reverse=True
                )
            ],
            by_model=[
                CostModelRow(
                    provider=provider,
                    model_id=model_id,
                    calls=bucket.calls,
                    cost_usd=float(bucket.cost_usd),
                    unpriced_calls=bucket.unpriced_calls,
                )
                for (provider, model_id), bucket in sorted(
                    by_model.items(), key=lambda item: item[1].cost_usd, reverse=True
                )
            ],
            trend=[
                CostTrendPoint(month=_month_label(key.year, key.month), cost_usd=float(cost))
                for key, cost in sorted(trend_costs.items())
            ],
        )
        logger.info(
            "cost_month_report_built",
            user_id=str(user_id),
            month=report.month,
            buckets=len(rows),
        )
        return report

    def export_csv_headers(self, month: str | None) -> dict[str, str]:
        """Resolve + validate the month; build the CSV download headers.

        Eager on purpose: month validation must run BEFORE the router
        constructs the ``StreamingResponse`` — once streaming starts, the
        status code is already sent and an ``InvalidMonthError`` would
        surface as a broken 200 instead of 422 (house streaming precedent).
        The costs endpoint's year-window guard is reused (trend window) so
        BOTH endpoints accept exactly the same months — month semantics
        identical (global constraint); it subsumes the export window's
        constructibility.

        Raises:
            InvalidMonthError: Regex-invalid or year-edge month (→ 422 via
                the app-registered handler).
        """
        year, mon = _resolve_month(month)
        _validate_window(year, mon, trend_months=self._trend_months)
        filename = f"narrare-costs-{_month_label(year, mon)}.csv"
        return {"Content-Disposition": f'attachment; filename="{filename}"'}

    async def export_csv_lines(self, user_id: uuid.UUID, month: str | None) -> AsyncIterator[str]:
        """Stream the month's usage records as CSV lines (spec B-2..B-5).

        Yields the BOM+header line, then one line per record in
        ``created_at`` order, pulling rows lazily from the repository
        stream (spec B-4 — constant memory). Month validation is repeated
        here so direct callers (bypassing :meth:`export_csv_headers`) also
        fail fast before the first line is produced.

        Raises:
            InvalidMonthError: On the first iteration for an invalid month.
        """
        year, mon = _resolve_month(month)
        _validate_window(year, mon, trend_months=self._trend_months)
        label = _month_label(year, mon)
        start = _month_start(year, mon)
        end = _month_start(*_shift_month(year, mon, 1))

        yield header_line()

        rows = 0
        async for record in self._repo.stream_month(user_id, start, end):
            rows += 1
            yield usage_record_line(record)
        logger.info("cost_csv_export_streamed", user_id=str(user_id), month=label, rows=rows)
