# apps/api/narrare/analytics/budget_guard.py
"""DB-backed budget guard — the API-side ``BudgetGuard`` impl (ADR-094).

Implements the Core Protocol (``narrare_core.llm.budget.BudgetGuard``)
with two state sources, neither of which touches the DB on the check
path (ADR-094 D8):

- **Running month total** — read from the usage sink's in-process state
  (``MonthTotalsSource``): startup-hydrated from ``usage_records``,
  incremented per priced write, rolled over lazily by month-key
  comparison on write AND read (spec A-4).
- **Budget config** — ``(monthly_budget_usd, budget_mode)`` per user,
  cached in-process. Hydration is lazy per user: an uncached first check
  schedules a background refresh on the running loop and returns
  (fail-open for that one call — the same ~1-call boundary latency
  ADR-094 D10 documents for threshold crossing); every later check
  enforces from the cache. The settings write-through hook
  (``budget_invalidation``, spec A-7) drops the entry so the next check
  re-fetches — no DB read ever runs on the check path itself.

``check`` is SYNC by Core contract, so lazy hydration runs as a task on
the caller's event loop (the gate executes inside async request handling;
in a sync-only context there is no loop and the guard no-ops). A refresh
that cannot read the config logs a warning and leaves the cache empty —
a broken config read must fail open rather than brick every LLM call
(the gate is opt-in enforcement; ``warn`` is the default mode).

Decision matrix (ADR-094 D8): no budget ⇒ return; ``warn`` ⇒ return;
``block`` AND month spend ≥ budget ⇒ raise :class:`BudgetExceededError`.
The Decimal→float conversion at the raise boundary is REQUIRED — the
Core error attrs are float (pyright enforces).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.analytics.budget_invalidation import set_budget_config_invalidator
from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
from narrare_core.shared.errors import BudgetExceededError

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.analytics.contracts import MonthTotalsSource
    from narrare.analytics.usage_sink import SqlUsageEventSink

logger = structlog.get_logger(__name__)


class UserBudgetGuard:
    """Pre-call budget check backed by the sink's totals + cached config."""

    def __init__(
        self,
        totals: MonthTotalsSource,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._totals = totals
        self._session_factory = session_factory
        self._config: dict[UUID, tuple[Decimal | None, str]] = {}
        self._refresh_inflight: set[UUID] = set()
        self._refresh_tasks: set[asyncio.Task[None]] = set()

    def check(self, user_id: UUID) -> None:
        """Return when the call may proceed; raise when it must be stopped.

        Uncached users fail open once while their config loads in the
        background (see module docstring); a cached ``(None, mode)``
        entry is a REAL "no budget" answer and needs no refresh.
        """
        entry = self._config.get(user_id)
        if entry is None:
            self._schedule_refresh(user_id)
            return
        budget, mode = entry
        if budget is None or mode != "block":
            return
        spend = self._totals.month_total(user_id)
        if spend >= budget:
            # Required Decimal→float conversion: the Core error attrs are
            # float by contract (pyright enforces).
            raise BudgetExceededError(
                user_id, month_spend_usd=float(spend), monthly_budget_usd=float(budget)
            )

    def drop_cached_config(self, user_id: UUID, /) -> None:
        """Invalidation-hook target (spec A-7): drop the cached config.

        Position-only parameter: this is the ``BudgetConfigInvalidator``
        callback shape registered via ``set_budget_config_invalidator``.
        Deliberately a PURE drop — no immediate re-fetch: the hook fires
        inside the settings request, BEFORE its transaction commits, so a
        separate-session refresh would read the pre-commit row and re-cache
        the stale config. The next check finds the cache empty, fails open
        once, and lazily rehydrates from committed data (post-commit by
        then — LLM calls arrive in later requests).
        """
        self._config.pop(user_id, None)

    async def refresh_config(self, user_id: UUID) -> None:
        """Read one user's budget config through the settings repository.

        Short-lived session, read-only intent: the repository's
        auto-created row (settings-less user) is never committed here.
        Fail-open on errors — logged, never raised (RULE-11: visible, and
        a degraded config read must not break the guarded call path).
        """
        try:
            async with self._session_factory() as session:
                settings = await UserAiSettingsRepository(session).get(user_id)
        except Exception:
            logger.warning("budget_config_refresh_failed", user_id=str(user_id), exc_info=True)
        else:
            self._config[user_id] = (
                None if settings.monthly_budget_usd is None else settings.monthly_budget_usd,
                settings.budget_mode,
            )
        finally:
            self._refresh_inflight.discard(user_id)

    def _schedule_refresh(self, user_id: UUID) -> None:
        """Schedule the lazy refresh on the running loop (once per user)."""
        if user_id in self._refresh_inflight:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("budget_config_refresh_skipped_no_loop", user_id=str(user_id))
            return
        self._refresh_inflight.add(user_id)
        task = loop.create_task(self.refresh_config(user_id))
        self._refresh_tasks.add(task)  # strong ref: pending tasks must not be GC'd
        task.add_done_callback(self._refresh_tasks.discard)


async def arm_budget_guard(
    sink: SqlUsageEventSink, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Hydrate the sink's running month total, then arm the guard slots.

    Called once at app startup (lifespan). ADR-094 D5: restart-safe arming —
    one aggregate SELECT (``UsageRecordRepository.month_spend_by_user``,
    RULE-08) re-hydrates the per-user UTC-month totals the sink then keeps
    incrementing; the guard's budget config is NOT hydrated here — it caches
    lazily per user on first check (spec A-4), off the check path.

    Hydration failure degrades to an EMPTY total (fail-open, logged): the
    budget gate is opt-in enforcement and must never prevent API startup —
    the graceful-degradation posture of ADR-093 D1.
    """
    from datetime import UTC, datetime

    from narrare.analytics.repository import UsageRecordRepository
    from narrare_core.llm.budget import set_budget_guard

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        async with session_factory() as session:
            totals = await UsageRecordRepository(session).month_spend_by_user(month_start)
    except Exception:
        logger.warning("budget_totals_hydration_failed", exc_info=True)
        totals = {}
    sink.hydrate(totals)
    guard = UserBudgetGuard(totals=sink, session_factory=session_factory)
    set_budget_config_invalidator(guard.drop_cached_config)
    set_budget_guard(guard)
    logger.info("budget_guard_armed", hydrated_users=len(totals))
