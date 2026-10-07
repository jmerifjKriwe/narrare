# tests/unit/api/analytics/_cost_service_helpers.py
"""Shared fake + seed helpers for the ``CostQueryService`` test modules.

Split out of ``test_cost_query_service.py`` (RULE-04): the month/trend
tests and the budget-overlay tests share the same fake usage repository,
row factory, and March seed data.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from narrare.analytics.repository import UsageAggRow
from narrare.analytics.service import CostQueryService

if TYPE_CHECKING:
    import uuid

    from narrare.analytics.repository import UsageRecordRepository


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
