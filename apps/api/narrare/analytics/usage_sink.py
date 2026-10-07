# apps/api/narrare/analytics/usage_sink.py
"""SQL usage-event sink — Core seam adapter for AI cost tracking (STATS-002).

Implements the ``UsageEventSink`` protocol (Task 2 Core seam, ADR-093) on
the write side: maps one frozen ``UsageEvent`` onto ``UsageRecordRow`` and
persists it through ``UsageRecordRepository`` in its own short-lived
session (RULE-08: no SQLAlchemy queries here — build the row, delegate).

Mapping decisions (spec §3.4):
- ``duration_seconds`` (float) → ``duration_ms`` (INTEGER), rounded.
- ``cost_usd`` (float | None) → ``NUMERIC(12,6)`` via ``Decimal(str(...))``
  so money never travels as float; ``None`` stays ``NULL`` (unpriced).
- ``created_at`` = the event's own timestamp — the column deliberately has
  no default so a late sink write cannot drift from the observed call.

Gate F2: events without ``user_id`` are dropped with a debug log BEFORE
any session is opened — unattributed rows have no query surface (every
read is user-scoped), so persisting them would be dead data. The sink
does not catch its own exceptions: ``emit_usage_event`` (Core) is the
single guarded enforcement point (ADR-093 D1), so a sink failure never
breaks a product run and is logged exactly once, at the seam.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from narrare.analytics.models import UsageRecordRow
from narrare.analytics.repository import UsageRecordRepository

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare_core.llm.usage_events import UsageEvent

logger = structlog.get_logger(__name__)


def _utc_month_key(now: datetime) -> str:
    """UTC calendar-month key (``YYYY-MM``) — the repository's bucket unit.

    ADR-094 D6: the budget month is the UTC calendar month, identical to
    the repository's UTC-pinned ``date_trunc`` bucketing, so totals and
    the costs panel can never disagree.
    """
    moment = now.astimezone(UTC)
    return f"{moment.year:04d}-{moment.month:02d}"


class SqlUsageEventSink:
    """Persists usage events via the repository — one session per event.

    Also maintains the in-process per-user UTC-month running total that
    arms the budget guard (ADR-094 D5, spec A-4): startup-hydrated via
    :meth:`hydrate`, incremented after each successful priced write.
    Rollover is lazy by month-key comparison on write AND read — no
    scheduler (ADR-080); the read-side re-check keeps a stale month's
    totals from ever enforcing even when no write has occurred yet.
    Money stays ``Decimal`` end-to-end.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._totals_month = _utc_month_key(clock())
        self._totals: dict[UUID, Decimal] = {}

    async def record(self, event: UsageEvent) -> None:
        """Map one event to a row, then insert + commit in its own session."""
        if event.user_id is None:
            logger.debug("usage_event_skipped_unattributed", intent=event.intent)
            return
        row = UsageRecordRow(
            user_id=event.user_id,
            novel_id=event.novel_id,
            intent=event.intent,
            provider=event.provider,
            model_id=event.model_id,
            tokens_in=event.tokens_in,
            tokens_out=event.tokens_out,
            cache_read_tokens=event.cache_read_tokens,
            cache_creation_tokens=event.cache_creation_tokens,
            duration_ms=round(event.duration_seconds * 1000),
            cost_usd=None if event.cost_usd is None else Decimal(str(event.cost_usd)),
            created_at=event.timestamp,
        )
        async with self._session_factory() as session:
            await UsageRecordRepository(session).insert(row)
            await session.commit()
        # Arm the budget gate AFTER the commit: only durable spend counts
        # (a rolled-back insert must not inflate the running total).
        if row.cost_usd is not None:
            self._add_spend(row.user_id, row.cost_usd)

    # ------------------------------------------------------------------
    # Running month total (ADR-094 D5 — read by ``UserBudgetGuard``)
    # ------------------------------------------------------------------

    def hydrate(self, totals: dict[UUID, Decimal]) -> None:
        """Replace the totals for the CURRENT UTC month (startup arming).

        The repository aggregation is expected to be scoped to the current
        month start; re-keying here keeps hydration correct even when it
        runs right after a month rollover.
        """
        self._rollover_if_stale()
        self._totals = dict(totals)

    def month_total(self, user_id: UUID) -> Decimal:
        """Current-UTC-month total for one user (0 when none recorded).

        Read-side rollover guard: a stored month-key that no longer
        matches means no priced write has happened this month yet — last
        month's spend must not leak into this month's budget check.
        """
        if self._totals_month != _utc_month_key(self._clock()):
            return Decimal("0")
        return self._totals.get(user_id, Decimal("0"))

    def _add_spend(self, user_id: UUID, amount: Decimal) -> None:
        """Increment the user's total, rolling the month over if stale."""
        self._rollover_if_stale()
        self._totals[user_id] = self._totals.get(user_id, Decimal("0")) + amount

    def _rollover_if_stale(self) -> None:
        """Write-side rollover: first touch of a new month clears the dict."""
        key = _utc_month_key(self._clock())
        if self._totals_month != key:
            self._totals = {}
            self._totals_month = key
