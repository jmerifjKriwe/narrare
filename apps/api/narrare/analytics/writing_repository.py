# apps/api/narrare/analytics/writing_repository.py
"""Writing-stats read repository — UTC-day aggregation (STATS-001 E-3, RULE-08).

Read-side derivation home for ``GET /analytics/writing`` (ADR-095 D4): the
dailies/streaks window and the goal word-sum are derived at query time over
``writing_activity_events`` / ``chapters``.

**Module split (RULE-04/RULE-06).** ``repository.py`` hosts the write-side
``WritingActivityEventRepository`` (insert telemetry) and sits at its
250-line hard limit; this sibling hosts the read-side aggregation class —
the ``writing_stats_*`` sibling-module convention ADR-095 prescribes
("the analytics core files stay untouched"). Appending events and deriving
aggregates are separate responsibilities; the classes share nothing.

**Timezone guarantee: day buckets are UTC calendar days, independent of the
DB session timezone.** ``date_trunc`` is applied to the naive UTC timestamp
(``created_at AT TIME ZONE 'UTC'``), mirroring the month bucketing in
``repository.py`` — without the pin, a non-UTC session would truncate in
local time and could mislabel a day's edge rows into the neighboring day.

SQL semantics are verified against real PostgreSQL in the migration-0045
round-trip family; unit tests exercise query wiring and row mapping with a
fake session only (same split as the usage-record repository).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare._app.base_repository import BaseRepository
from narrare.analytics.writing_models import WritingActivityEventRow
from narrare.chapters.models import Chapter

if TYPE_CHECKING:
    import uuid


def _bucket_day(value: datetime | date) -> date:
    """``date_trunc`` (UTC-pinned) yields a naive timestamp; the contract field is a date."""
    return value.date() if isinstance(value, datetime) else value


class WritingStatsQueryRepository(BaseRepository):
    """Read-side aggregation for the writing report (dailies + goal basis)."""

    async def daily_totals(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> list[tuple[date, int]]:
        """Signed net word sums per UTC day for ``[start, end)``, day-ascending.

        User-scoped; ``novel_id`` optionally narrows to one novel's events.
        Days without events are absent from the result — the service
        zero-fills the report window.
        """
        day_bucket = func.date_trunc(
            "day", WritingActivityEventRow.created_at.op("AT TIME ZONE")("UTC")
        ).label("day")
        stmt = (
            select(day_bucket, func.coalesce(func.sum(WritingActivityEventRow.delta_words), 0))
            .where(
                WritingActivityEventRow.user_id == user_id,
                WritingActivityEventRow.created_at >= start,  # [start, end) — half-open
                WritingActivityEventRow.created_at < end,
            )
            .group_by(day_bucket)
            .order_by(day_bucket.asc())
        )
        if novel_id is not None:
            stmt = stmt.where(WritingActivityEventRow.novel_id == novel_id)
        result = await self._session.execute(stmt)
        return [(_bucket_day(day), int(words)) for day, words in result.all()]

    async def novel_word_total(self, novel_id: uuid.UUID) -> int:
        """Live ``SUM(chapters.word_count)`` for one novel (goal progress basis).

        ADR-095 D5: goals read manuscript STATE, not activity events — the
        events' day-0 boundary would hide a novelist's pre-existing words
        from their own progress. COALESCE → 0 (a chapterless novel is 0
        progress, never NULL).
        """
        stmt = select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
            Chapter.novel_id == novel_id
        )
        result = await self._session.execute(stmt)
        total = result.scalar()
        # None is impossible behind the COALESCE; mapping it keeps the method
        # total instead of asserting an invariant the type system cannot see
        # through the SQL expression (mirrors repository._to_decimal).
        return 0 if total is None else int(total)
