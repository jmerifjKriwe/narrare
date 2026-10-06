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

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from narrare.analytics.models import UsageRecordRow
from narrare.analytics.repository import UsageRecordRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare_core.llm.usage_events import UsageEvent

logger = structlog.get_logger(__name__)


class SqlUsageEventSink:
    """Persists usage events via the repository — one session per event."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
