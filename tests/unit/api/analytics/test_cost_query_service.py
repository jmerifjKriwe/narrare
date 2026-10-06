# tests/unit/api/analytics/test_cost_query_service.py
"""Unit tests for ``CostQueryService`` month-report bucketing (fake repository).

Mirrors the sibling repository test's fake-based approach: the service holds
no SQL — these tests pin the Python-side semantics (month resolution +
validation, single six-month window call, month-scoped totals/by_intent/
by_model bucketing, oldest-first trend with zero months, float conversions,
cost-desc sorting) against a fake repository returning canned ``UsageAggRow``s.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.analytics.contracts import CostQueryServiceProtocol
from narrare.analytics.repository import UsageAggRow
from narrare.analytics.service import CostQueryService, InvalidMonthError

if TYPE_CHECKING:
    import uuid

    from narrare.analytics.repository import UsageRecordRepository

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeUsageRepository:
    """Records ``aggregate_range`` calls; returns canned aggregate rows."""

    def __init__(self, rows: list[UsageAggRow]) -> None:
        self._rows = rows
        self.calls: list[tuple[uuid.UUID, datetime, datetime]] = []

    async def aggregate_range(
        self, user_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[UsageAggRow]:
        self.calls.append((user_id, start, end))
        return list(self._rows)


def _make_service(rows: list[UsageAggRow]) -> tuple[CostQueryService, _FakeUsageRepository]:
    """Service over a fake repo; ``cast`` is the RULE-23-sanctioned fake seam."""
    fake = _FakeUsageRepository(rows)
    return CostQueryService(cast("UsageRecordRepository", fake)), fake


# ---------------------------------------------------------------------------
# Fixtures / seed data
# ---------------------------------------------------------------------------


def _agg_row(
    month: date,
    intent: str,
    provider: str,
    model_id: str,
    *,
    calls: int = 1,
    tokens_in: int = 100,
    tokens_out: int = 50,
    cost: str = "0.005",
    unpriced_calls: int = 0,
) -> UsageAggRow:
    return UsageAggRow(
        month=month,
        intent=intent,
        provider=provider,
        model_id=model_id,
        calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=Decimal(cost),
        unpriced_calls=unpriced_calls,
    )


def _march_rows() -> list[UsageAggRow]:
    """Requested month 2026-03 (3 buckets) plus two older trend-only buckets.

    ``write`` spans two providers with the SAME model_id (``gpt-x``): the two
    rows must merge in ``by_intent`` but stay separate in ``by_model``.
    """
    return [
        _agg_row(
            date(2026, 3, 1),
            "summarize",
            "anthropic",
            "claude-haiku",
            calls=2,
            tokens_in=150,
            tokens_out=30,
            cost="0.003",
        ),
        _agg_row(
            date(2026, 3, 1),
            "write",
            "openai",
            "gpt-x",
            calls=1,
            tokens_in=50,
            tokens_out=60,
            cost="0.010",
            unpriced_calls=1,
        ),
        _agg_row(
            date(2026, 3, 1),
            "write",
            "azure",
            "gpt-x",
            calls=3,
            tokens_in=90,
            tokens_out=20,
            cost="0.006",
        ),
        _agg_row(
            date(2025, 11, 1),
            "chat",
            "openai",
            "gpt-x",
            calls=5,
            tokens_in=500,
            tokens_out=400,
            cost="0.100",
        ),
        _agg_row(
            date(2026, 1, 1),
            "summarize",
            "anthropic",
            "claude-haiku",
            calls=1,
            tokens_in=100,
            tokens_out=50,
            cost="0.002",
        ),
    ]


# ---------------------------------------------------------------------------
# Month resolution + validation
# ---------------------------------------------------------------------------


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    """Month arithmetic for expected-window assertions (year-wrap safe)."""
    total = year * 12 + month - 1 + delta
    return total // 12, total % 12 + 1


class TestMonthResolution:
    async def test_month_report_with_none_resolves_current_server_local_month(self) -> None:
        """month=None → current server-local month, reported and used as window end."""
        now = datetime.now().astimezone()
        service, fake = _make_service([])

        report = await service.month_report(uuid4(), None)

        assert report.month == f"{now.year:04d}-{now.month:02d}"
        assert report.trend[-1].month == report.month
        year, month = int(report.month[:4]), int(report.month[5:7])
        start_y, start_m = _shift(year, month, -5)
        end_y, end_m = _shift(year, month, 1)
        assert fake.calls[0][1] == datetime(start_y, start_m, 1, tzinfo=UTC)
        assert fake.calls[0][2] == datetime(end_y, end_m, 1, tzinfo=UTC)

    @pytest.mark.parametrize(
        ("bad_month", "reason"),
        [
            ("2026-13", "month out of range"),
            ("2026-00", "zero month"),
            ("abc", "non-numeric"),
            ("2026-1", "single-digit month"),
            ("20261", "missing separator"),
            ("", "empty string"),
            # Regex-valid but unconstructible: the six-month trend window
            # would leave datetime's constructible year range (0001-9999).
            ("0000-01", "window start before year 1"),
            ("9999-12", "window end after year 9999"),
            ("0001-01", "window start in year 0"),
        ],
    )
    async def test_month_report_with_invalid_month_raises_invalid_month_error(
        self, bad_month: str, reason: str
    ) -> None:
        """Malformed or unconstructible months raise InvalidMonthError pre-repo."""
        service, fake = _make_service([])

        # match="" would warn (always matches) — assert message content only
        # when there is one; the empty-string case asserts the type alone.
        match = re.escape(bad_month) if bad_month else None
        with pytest.raises(InvalidMonthError, match=match):
            await service.month_report(uuid4(), bad_month)

        assert fake.calls == []

    @pytest.mark.parametrize(
        ("edge_month", "expected_trend_start"),
        [
            ("0001-06", "0001-01"),  # earliest constructible six-month window
            ("9999-01", "9998-08"),  # latest constructible six-month window
        ],
    )
    async def test_month_report_with_constructible_boundary_month_succeeds(
        self, edge_month: str, expected_trend_start: str
    ) -> None:
        """The constructible boundary months must NOT be rejected (guard is
        window-aware, so years 0001-05 and 9999 within range still report)."""
        service, fake = _make_service([])

        report = await service.month_report(uuid4(), edge_month)

        assert report.month == edge_month
        assert report.trend[0].month == expected_trend_start
        assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# Bucketing (explicit month 2026-03)
# ---------------------------------------------------------------------------


class TestMonthReportBucketing:
    async def test_month_report_totals_scoped_to_requested_month(self) -> None:
        """Totals cover ONLY 2026-03 rows; float(Decimal) conversion applied."""
        service, _ = _make_service(_march_rows())

        report = await service.month_report(uuid4(), "2026-03")

        assert report.month == "2026-03"
        assert report.totals.calls == 6
        assert report.totals.tokens_in == 290
        assert report.totals.tokens_out == 110
        assert report.totals.cost_usd == pytest.approx(0.019)
        assert report.totals.unpriced_calls == 1

    async def test_month_report_by_intent_merges_intents_sorted_by_cost_desc(self) -> None:
        """Same intent across providers merges; rows sorted by cost descending."""
        service, _ = _make_service(_march_rows())

        report = await service.month_report(uuid4(), "2026-03")

        assert [(row.intent, row.calls, row.unpriced_calls) for row in report.by_intent] == [
            ("write", 4, 1),
            ("summarize", 2, 0),
        ]
        assert report.by_intent[0].cost_usd == pytest.approx(0.016)
        assert report.by_intent[1].cost_usd == pytest.approx(0.003)

    async def test_month_report_by_model_keeps_same_model_per_provider_separate(self) -> None:
        """Same model_id under two providers stays two rows; sorted cost desc."""
        service, _ = _make_service(_march_rows())

        report = await service.month_report(uuid4(), "2026-03")

        assert [
            (row.provider, row.model_id, row.calls, row.unpriced_calls) for row in report.by_model
        ] == [
            ("openai", "gpt-x", 1, 1),
            ("azure", "gpt-x", 3, 0),
            ("anthropic", "claude-haiku", 2, 0),
        ]
        assert [row.cost_usd for row in report.by_model] == pytest.approx([0.010, 0.006, 0.003])


# ---------------------------------------------------------------------------
# Trend + window
# ---------------------------------------------------------------------------


class TestMonthReportTrendAndWindow:
    async def test_month_report_trend_is_six_months_oldest_first_with_zero_months(self) -> None:
        """Trend spans the six months ending with `month`; empty months are 0.0."""
        service, _ = _make_service(_march_rows())

        report = await service.month_report(uuid4(), "2026-03")

        assert [point.month for point in report.trend] == [
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
        ]
        assert [point.cost_usd for point in report.trend] == pytest.approx(
            [0.0, 0.100, 0.0, 0.002, 0.0, 0.019]
        )

    async def test_month_report_makes_one_aggregate_call_over_six_month_window(self) -> None:
        """Exactly one repo call: [first of month-5, first of month+1), caller scope."""
        service, fake = _make_service(_march_rows())
        user_id = uuid4()

        await service.month_report(user_id, "2026-03")

        assert len(fake.calls) == 1
        called_user, start, end = fake.calls[0]
        assert called_user == user_id
        assert start == datetime(2025, 10, 1, tzinfo=UTC)
        assert end == datetime(2026, 4, 1, tzinfo=UTC)

    async def test_month_report_with_no_usage_returns_zeroed_report(self) -> None:
        """No rows → zeroed totals, empty breakdowns, all-zero six-point trend."""
        service, _ = _make_service([])

        report = await service.month_report(uuid4(), "2026-03")

        assert report.totals.calls == 0
        assert report.totals.cost_usd == 0.0
        assert report.totals.unpriced_calls == 0
        assert report.by_intent == []
        assert report.by_model == []
        assert len(report.trend) == 6
        assert all(point.cost_usd == 0.0 for point in report.trend)
        assert report.trend[-1].month == "2026-03"

    async def test_month_report_with_custom_trend_months_shrinks_window(self) -> None:
        """Injected trend_months=3 → 3-entry trend over a 3-month window."""
        fake = _FakeUsageRepository(_march_rows())
        narrow = CostQueryService(cast("UsageRecordRepository", fake), trend_months=3)

        report = await narrow.month_report(uuid4(), "2026-03")

        assert [point.month for point in report.trend] == ["2026-01", "2026-02", "2026-03"]
        assert fake.calls[-1][1] == datetime(2026, 1, 1, tzinfo=UTC)
        assert fake.calls[-1][2] == datetime(2026, 4, 1, tzinfo=UTC)

    async def test_service_with_trend_months_below_one_raises_value_error(self) -> None:
        """A non-positive window is a construction-time configuration error."""
        fake = _FakeUsageRepository([])

        with pytest.raises(ValueError, match="trend_months"):
            CostQueryService(cast("UsageRecordRepository", fake), trend_months=0)


# ---------------------------------------------------------------------------
# Contract conformance
# ---------------------------------------------------------------------------


async def test_cost_query_service_satisfies_protocol() -> None:
    """CostQueryService implements CostQueryServiceProtocol (Task 10 DI seam)."""
    service, _ = _make_service([])

    assert isinstance(service, CostQueryServiceProtocol)
