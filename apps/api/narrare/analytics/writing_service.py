# apps/api/narrare/analytics/writing_service.py
"""Writing query service — read-side derivation for ``GET /analytics/writing``
(STATS-001 spec E-3/E-5; ADR-095 D4/D5).

Builds a :class:`WritingReport` from the repository's UTC-day
(words, event-count) totals: zero-filled 90-day dailies (window contract
N=90 v1), streaks per the today-grace rule, today's window bucket, the
ALL-TIME net total, and the novel-scoped goal overlay.

**Two deliberate bases (ADR-095):** dailies/streaks/today and the
all-time total derive from the *activity events* (honest net deltas,
day-0 boundary documented); ``goal.current_words`` reads *manuscript
state* — the live ``SUM(chapters.word_count)`` — because the events'
day-0 boundary would hide a novelist's pre-existing words from their own
goal progress. ``total_words`` is deliberately bounds-free (window-capped
totals would mislabel the number); only ``dailies``/``streaks``/``today_words``
are window values.

**Streak semantics (spec today-grace rule).** The current streak counts
back from today when today is active, else from yesterday — a streak
survives until the day ENDS; it is 0 when neither today nor yesterday is
active. The longest streak spans the report window (v1 boundary, not
all-time). Active day = ≥1 stored event (spec E-3 / ADR-095, exact): the
repository returns per-day event counts, so a day whose deltas cancel
(+100/-100) still counts as active; dailies keep the words basis and show
0 for such a day.

RULE-06: no SQL, no HTTP. The window length and the clock are injected
(RULE-18) with the spec defaults; the goal target arrives through the
:class:`GoalSource` seam (E5 plugs the ``ProjectSettings.writing_goals``
reader in at the DI factory — this module stays untouched).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from narrare.analytics.contracts import (
    WritingDailyPoint,
    WritingGoalProgress,
    WritingReport,
    WritingStreaks,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from narrare.analytics.contracts import GoalSource
    from narrare.analytics.writing_repository import WritingStatsQueryRepository

logger = structlog.get_logger(__name__)


def _run_ending_at(active: set[date], anchor: date) -> int:
    """Length of the consecutive active run ending at *anchor* (0 if inactive)."""
    run = 0
    day = anchor
    while day in active:
        run += 1
        day -= timedelta(days=1)
    return run


def _longest_run(active: set[date]) -> int:
    """Longest consecutive active run within the set (0 when empty)."""
    longest = 0
    for day in active:
        if day - timedelta(days=1) in active:
            continue  # mid-run — only count from run starts
        length = 1
        following = day + timedelta(days=1)
        while following in active:
            length += 1
            following += timedelta(days=1)
        longest = max(longest, length)
    return longest


def _streaks(active: set[date], today: date) -> WritingStreaks:
    """Current + longest streak (spec today-grace rule — see module docstring)."""
    anchor = today if today in active else today - timedelta(days=1)
    return WritingStreaks(current=_run_ending_at(active, anchor), longest=_longest_run(active))


class NullGoalSource:
    """Default :class:`GoalSource` — reports "no goal" for every novel.

    Fallback for the ``goal_source=None`` constructor path: E5 landed
    ``ProjectSettings.writing_goals`` and the DI factory
    (``dependencies.py``) wires ``ProjectSettingsGoalSource`` in its
    place; the service and router never change.
    """

    async def target_words(self, novel_id: UUID) -> int | None:
        del novel_id  # no target storage exists yet
        return None


class WritingQueryService:
    """Builds the writing report; implements ``WritingQueryServiceProtocol``.

    The report window (spec contract: 90 days) and the derivation clock are
    injected with production defaults — tests pin boundary math by fixing
    the clock instead of sleeping on ``datetime.now``.
    """

    def __init__(
        self,
        repo: WritingStatsQueryRepository,
        *,
        goal_source: GoalSource | None = None,
        window_days: int = 90,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if window_days < 1:
            raise ValueError("window_days must be >= 1")
        self._repo = repo
        self._goal_source = goal_source
        self._window_days = window_days
        self._clock = clock

    async def writing_report(self, user_id: UUID, novel_id: UUID | None) -> WritingReport:
        """Derive the writing report for *user_id*, optionally novel-scoped.

        The window is the last ``window_days`` UTC days ending today
        (half-open ``[today-(N-1), today+1)``); ``novel_id`` narrows the
        dailies/streaks/today window AND the all-time total to one novel's
        events, and gates the goal block.
        """
        today = self._clock().date()
        window_start = today - timedelta(days=self._window_days - 1)
        start = datetime(window_start.year, window_start.month, window_start.day, tzinfo=UTC)
        end = start + timedelta(days=self._window_days)

        totals = await self._repo.daily_totals(user_id, start, end, novel_id=novel_id)
        words_by_day = {day: words for day, words, _ in totals}
        dailies = [
            WritingDailyPoint(
                date=window_start + timedelta(days=offset),
                words=words_by_day.get(window_start + timedelta(days=offset), 0),
            )
            for offset in range(self._window_days)
        ]
        # Streak basis = stored events (spec E-3 / ADR-095), NOT the net sums:
        # a day whose deltas cancel (+100/-100) still counts as active.
        active = {day for day, _, events in totals if events >= 1}
        report = WritingReport(
            dailies=dailies,
            streaks=_streaks(active, today),
            today_words=words_by_day.get(today, 0),
            total_words=await self._repo.all_time_word_total(user_id, novel_id=novel_id),
            goal=await self._goal_block(novel_id),
        )
        logger.info(
            "writing_report_built",
            user_id=str(user_id),
            novel_id=None if novel_id is None else str(novel_id),
            window_days=self._window_days,
            active_days=len(active),
        )
        return report

    async def _goal_block(self, novel_id: UUID | None) -> WritingGoalProgress | None:
        """Goal overlay (spec E-4/E-5) — ``None`` unless goal data exists.

        ``None`` when: user-scope report (no novel), no goal source wired
        (pre-E5), or the novel's target is unset. A non-positive target is
        treated as unset too — progress against it is undefined (no
        ZeroDivision). ``current_words`` is the LIVE chapter word sum (state
        basis, ADR-095 D5), ``progress_pct`` rounded to one decimal.
        """
        if novel_id is None or self._goal_source is None:
            return None
        target = await self._goal_source.target_words(novel_id)
        if target is None or target <= 0:
            return None
        current = await self._repo.novel_word_total(novel_id)
        return WritingGoalProgress(
            target_words=target,
            current_words=current,
            progress_pct=round(current / target * 100, 1),
        )
