# apps/api/narrare/analytics/contracts.py
"""Analytics cost-query contracts (RULE-03) — response models + service protocol.

STATS-002: the Pydantic models are the ``CostQueryService`` response contract;
the router (Task 10) depends on :class:`CostQueryServiceProtocol` as its DI
seam and serializes the models directly. Monetary values are ``float`` sums
converted from exact ``Decimal`` repository aggregates at the service
boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    import uuid


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


class CostMonthReport(BaseModel):
    """Monthly AI cost overview: month breakdowns + six-month trend.

    ``totals``/``by_intent``/``by_model`` are scoped to ``month``; ``trend``
    spans the six months ending with ``month`` (oldest first, zero months
    included).
    """

    month: str
    totals: CostTotals
    by_intent: list[CostIntentRow]
    by_model: list[CostModelRow]
    trend: list[CostTrendPoint]


@runtime_checkable
class CostQueryServiceProtocol(Protocol):
    """Read-side contract for the costs router (spec §4)."""

    async def month_report(self, user_id: uuid.UUID, month: str | None) -> CostMonthReport: ...
