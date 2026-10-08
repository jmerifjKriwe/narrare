# apps/api/narrare/analytics/writing_stats_recorder.py
"""Writing-stats recorder — contract + SQL impl for content-write capture
(STATS-001, ADR-095).

The :class:`WritingStatsRecorder` Protocol (RULE-03) is the seam the four
content-write surfaces (chapters update/delete, co-author apply, import
commit — Task E3) depend on; :class:`SqlWritingStatsRecorder` persists one
append-only signed delta event per call through
``WritingActivityEventRepository`` in its own short-lived session
(RULE-08: build the row here, SQLAlchemy only in the repository).

**Attribution is explicit.** ``user_id``/``novel_id``/``chapter_id`` are
plain keyword parameters — unlike ``UsageEvent`` emission (STATS-002), the
call sites KNOW the user, novel, and chapter they are writing, so ContextVar
propagation would add indirection without removing any error class.

**Never-raises — and why the guard lives HERE, not at the call sites.**
``SqlUsageEventSink`` (STATS-002) does not catch its own exceptions because
its caller, Core's ``emit_usage_event``, is the single guarded enforcement
point (ADR-093 D1) — a sink failure is logged exactly once at that seam.
The writing recorder has no such outer guard: its callers are content-write
services whose failure posture is "a stats capture must never break a user
write" (ADR-095). Guarding at N call sites would duplicate the try/except
and invite drift (one forgotten guard = a broken editor save), so the
recorder itself is the single enforcement point: ANY persistence failure is
swallowed with a ``writing_stats_record_failed`` warning and the write path
continues untouched. This is the RULE-11 graceful-class posture, applied at
the seam where the stakes are lowest (telemetry) and the blast radius
highest (the user's manuscript).

**Zero deltas are skipped** (debug log, before any session is opened):
empty chapter creates, restores to identical content, and empty-chapter
deletes carry no signal — storing them would pollute day-bucketing and
streak windows with no-op rows (ADR-095: a day is active iff it has ≥1
event).

``created_at`` is stamped from the injected clock at write time — the
column has NO server default (model + migration 0045), so a late write
cannot drift from the observed edit, and import commits are attributed to
the day of import, never backdated (ADR-095 D1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from narrare.analytics.repository import WritingActivityEventRepository
from narrare.analytics.writing_models import WritingActivityEventRow

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)


@runtime_checkable
class WritingStatsRecorder(Protocol):
    """Capture one signed word-count delta from a content-write surface.

    Implementations MUST be safe to call inline in a write path: they
    return normally on success, on a skipped (zero) delta, AND on internal
    failure — stats capture never surfaces an error to its caller
    (ADR-095 never-raises ruling).
    """

    async def record_delta(
        self,
        *,
        user_id: UUID,
        novel_id: UUID,
        chapter_id: UUID | None,
        delta_words: int,
    ) -> None:
        """Record a signed word-count delta for one chapter write.

        ``delta_words == 0`` is a legitimate no-op call (restores to
        identical content) and persists nothing. ``chapter_id`` is ``None``
        only where the write surface has no chapter identity yet.
        """
        ...


class SqlWritingStatsRecorder:
    """Persists writing deltas via the repository — one session per event."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def record_delta(
        self,
        *,
        user_id: UUID,
        novel_id: UUID,
        chapter_id: UUID | None,
        delta_words: int,
    ) -> None:
        """Persist one signed delta; any failure is swallowed with a warning."""
        if delta_words == 0:
            logger.debug(
                "writing_stats_delta_skipped_zero",
                novel_id=str(novel_id),
                chapter_id=None if chapter_id is None else str(chapter_id),
            )
            return
        try:
            row = WritingActivityEventRow(
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                delta_words=delta_words,
                created_at=self._clock(),
            )
            async with self._session_factory() as session:
                await WritingActivityEventRepository(session).insert_writing_event(row)
                await session.commit()
        except Exception as exc:
            logger.warning(
                "writing_stats_record_failed",
                error=str(exc),
                exc_info=True,
            )
