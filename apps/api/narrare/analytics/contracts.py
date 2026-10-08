# apps/api/narrare/analytics/contracts.py
"""Analytics query contracts (RULE-03) — response models + service protocols.

STATS-002: the Pydantic models are the ``CostQueryService`` response contract;
the router depends on :class:`CostQueryServiceProtocol` as its DI seam and
serializes the models directly. Monetary values are ``float`` sums converted
from exact ``Decimal`` repository aggregates at the service boundary.

STATS-001 (ADR-095): the ``Writing*`` models are the ``WritingQueryService``
response contract for ``GET /analytics/writing`` (spec E-5);
:class:`GoalSource` is the goal-target read seam E5 plugs its
``ProjectSettings.writing_goals`` reader into.
"""

from __future__ import annotations

from datetime import (
    date,  # noqa: TC003 — load-bearing: pydantic resolves model annotations at runtime
)
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


class WritingDailyPoint(BaseModel):
    """One UTC day of the report window (``date`` serializes ``YYYY-MM-DD``)."""

    date: date
    words: int  # signed net words for the day (deletes are negative)


class WritingStreaks(BaseModel):
    """Consecutive-active-day streaks (spec today-grace rule)."""

    current: int
    longest: int


class WritingGoalProgress(BaseModel):
    """Novel goal overlay — target vs LIVE manuscript words (spec E-4)."""

    target_words: int
    current_words: int
    progress_pct: float  # one decimal place


class WritingReport(BaseModel):
    """``GET /analytics/writing`` response (spec E-5).

    ``dailies`` spans the last 90 days ending today (UTC days, zero-filled,
    oldest first); ``today_words`` is the window's today bucket.
    ``total_words`` is the all-time net words recorded for the scope
    (user, or user + novel) — deliberately not window-capped: a 90-day
    number labelled "total" would mislabel it. ``goal`` is present only
    for a novel-scoped request whose novel has a target set.
    """

    dailies: list[WritingDailyPoint]
    streaks: WritingStreaks
    today_words: int
    total_words: int
    goal: WritingGoalProgress | None = None


@runtime_checkable
class WritingQueryServiceProtocol(Protocol):
    """Read-side contract for the writing-stats route (spec E-5)."""

    async def writing_report(
        self, user_id: uuid.UUID, novel_id: uuid.UUID | None
    ) -> WritingReport: ...


@runtime_checkable
class GoalSource(Protocol):
    """Read seam for a novel's writing-goal target (spec E-4).

    ``None`` = the novel has no goal set. Implemented until E5 lands
    ``ProjectSettings.writing_goals`` by ``NullGoalSource`` (always
    ``None``); E5 swaps it at the DI factory without touching consumers.
    """

    async def target_words(self, novel_id: uuid.UUID) -> int | None: ...
