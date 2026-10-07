# apps/api/narrare/analytics/contracts.py
"""Analytics cost-query contracts (RULE-03) — response models + service protocol.

STATS-002: the Pydantic models are the ``CostQueryService`` response contract;
the router (Task 10) depends on :class:`CostQueryServiceProtocol` as its DI
seam and serializes the models directly. Monetary values are ``float`` sums
converted from exact ``Decimal`` repository aggregates at the service
boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal


class CostTotals(BaseModel):
    """Aggregate over all usage recorded in the requested month."""

    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    unpriced_calls: int  # calls whose cost was NULL at write time


class CostIntentRow(BaseModel):
    """Per-intent breakdown row (sorted by cost, descending)."""

    intent: str
    calls: int
    cost_usd: float
    unpriced_calls: int


class CostModelRow(BaseModel):
    """Per-(provider, model) breakdown row (sorted by cost, descending).

    The same ``model_id`` offered by two providers yields two rows.
    """

    provider: str
    model_id: str
    calls: int
    cost_usd: float
    unpriced_calls: int


class CostTrendPoint(BaseModel):
    """One month of the six-month trend (``month`` is ``YYYY-MM``)."""

    month: str
    cost_usd: float


class CostBudgetBlock(BaseModel):
    """Budget overlay for the costs report (spec A-6, ADR-094 D6/D8).

    ``CostMonthReport.budget`` is ``None`` when the user set no budget;
    present otherwise — the warn badge's one-round-trip data.
    ``over_budget`` uses the same ``>=`` boundary as the block-mode gate:
    one rule, both surfaces. ``budget_mode`` is the settings CHECK domain
    ('warn' | 'block' — ADR-094 D7).
    """

    monthly_budget_usd: float
    budget_mode: Literal["warn", "block"]
    month_spend_usd: float
    over_budget: bool


class CostMonthReport(BaseModel):
    """Monthly AI cost overview: month breakdowns + six-month trend.

    ``totals``/``by_intent``/``by_model`` are scoped to ``month``; ``trend``
    spans the six months ending with ``month`` (oldest first, zero months
    included). ``budget`` overlays the user's budget when one is set.
    """

    month: str
    totals: CostTotals
    by_intent: list[CostIntentRow]
    by_model: list[CostModelRow]
    trend: list[CostTrendPoint]
    budget: CostBudgetBlock | None = None


@runtime_checkable
class CostQueryServiceProtocol(Protocol):
    """Read-side contract for the costs router (spec §4)."""

    async def month_report(self, user_id: uuid.UUID, month: str | None) -> CostMonthReport: ...


@runtime_checkable
class MonthTotalsSource(Protocol):
    """Read seam over the sink's running UTC-month totals (ADR-094 D5).

    Implemented by ``SqlUsageEventSink`` (startup-hydrated, incremented
    per priced write, lazily rolled over by month-key comparison on write
    AND read — spec A-4); consumed by ``UserBudgetGuard.check``.
    """

    def month_total(self, user_id: uuid.UUID) -> Decimal: ...
