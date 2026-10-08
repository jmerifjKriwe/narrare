# tests/unit/api/analytics/test_writing_query_service.py
"""Unit tests for ``WritingQueryService`` — writing-report derivation (E4).

The service holds no SQL (RULE-08): streaks/today/total are pure Python over
the repository's UTC-day net sums, so these tests drive the PUBLIC
``writing_report`` with an injected clock + a fake repository and pin the
spec's boundary matrix — zero-filled ordered dailies, default half-open
window, streak gaps / today-silent grace / year boundary / leap Feb-29 /
single day, and the goal overlay (None vs set, LIVE word-count basis,
one-decimal pct rounding). SQL wiring lives in test_writing_read_router.py;
real-PostgreSQL bucketing semantics in the 0045 round-trip family.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.analytics.contracts import (
    GoalSource,
    WritingQueryServiceProtocol,
    WritingReport,
)
from narrare.analytics.writing_service import NullGoalSource, WritingQueryService

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from narrare.analytics.writing_repository import WritingStatsQueryRepository

# Fixed "today" (UTC): the derivation clock is injected, never datetime.now().
_TODAY = date(2026, 10, 8)
_NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
_WINDOW_START = _TODAY - timedelta(days=89)  # default 90-day window start


class _FakeRepo:
    """Canned ``daily_totals``/``novel_word_total``; records window calls."""

    def __init__(
        self, totals: list[tuple[date, int]] | None = None, *, word_total: int = 0
    ) -> None:
        self.totals = totals if totals is not None else []
        self.word_total = word_total
        self.calls: list[tuple[UUID, datetime, datetime, UUID | None]] = []

    async def daily_totals(
        self, user_id: UUID, start: datetime, end: datetime, *, novel_id: UUID | None = None
    ) -> list[tuple[date, int]]:
        self.calls.append((user_id, start, end, novel_id))
        return self.totals

    async def novel_word_total(self, novel_id: UUID) -> int:
        del novel_id
        return self.word_total


class _FakeGoalSource:
    """Canned ``GoalSource`` — records which novel it was asked about."""

    def __init__(self, target: int | None) -> None:
        self.target = target
        self.asked: list[UUID] = []

    async def target_words(self, novel_id: UUID) -> int | None:
        self.asked.append(novel_id)
        return self.target


def _make_service(
    repo: _FakeRepo,
    *,
    goal_source: GoalSource | None = None,
    clock: Callable[[], datetime] = lambda: _NOW,
    window_days: int = 90,
) -> WritingQueryService:
    # cast = the RULE-23-sanctioned fake seam (mirrors _cost_service_helpers).
    return WritingQueryService(
        cast("WritingStatsQueryRepository", repo),
        goal_source=goal_source,
        clock=clock,
        window_days=window_days,
    )


def _active(days_before_today: tuple[int, ...]) -> list[tuple[date, int]]:
    """Totals table marking the given offsets-from-today as active (10 net words)."""
    return [(_TODAY - timedelta(days=offset), 10) for offset in days_before_today]


# ---------------------------------------------------------------------------
# Dailies window + totals
# ---------------------------------------------------------------------------


class TestDailiesWindow:
    async def test_report_with_no_events_zero_fills_90_days_oldest_first(self) -> None:
        """No events → 90 zero days, ordered oldest-first, ending today."""
        report = await _make_service(_FakeRepo()).writing_report(uuid4(), None)

        assert len(report.dailies) == 90
        assert report.dailies[0].date == _WINDOW_START
        assert report.dailies[-1].date == _TODAY
        assert [point.words for point in report.dailies] == [0] * 90
        assert [point.date for point in report.dailies] == sorted(
            point.date for point in report.dailies
        )

    async def test_default_window_is_half_open_ending_tomorrow_exclusive(self) -> None:
        """Repo window = [today-89d 00:00 UTC, today+1d 00:00 UTC) — today included."""
        repo = _FakeRepo()

        await _make_service(repo).writing_report(uuid4(), None)

        _, start, end, novel_id = repo.calls[0]
        assert start == datetime(2026, 7, 11, tzinfo=UTC)
        assert end == datetime(2026, 10, 9, tzinfo=UTC)  # exclusive — covers all of today
        assert novel_id is None

    async def test_totals_are_signed_net_sums_mapped_onto_their_days(self) -> None:
        """Event sums land on their UTC days; absent days stay zero-filled."""
        totals = [
            (_TODAY, 150),
            (_TODAY - timedelta(days=1), -50),
            (_TODAY - timedelta(days=30), 200),
        ]
        report = await _make_service(_FakeRepo(totals)).writing_report(uuid4(), None)

        by_date = {point.date: point.words for point in report.dailies}
        assert by_date[_TODAY] == 150
        assert by_date[_TODAY - timedelta(days=1)] == -50  # deletes are honest negatives
        assert by_date[_TODAY - timedelta(days=30)] == 200
        assert by_date[_TODAY - timedelta(days=2)] == 0  # silent day zero-filled

    async def test_today_and_total_words_come_from_the_window(self) -> None:
        """today_words is today's bucket; total is the window's signed sum."""
        totals = [
            (_TODAY, 150),
            (_TODAY - timedelta(days=1), -50),
            (_TODAY - timedelta(days=30), 200),
        ]
        report = await _make_service(_FakeRepo(totals)).writing_report(uuid4(), None)

        assert report.today_words == 150
        assert report.total_words == 300  # 150 - 50 + 200 — net honesty (ADR-095)

    async def test_novel_id_reaches_the_repository_query(self) -> None:
        """The optional novel filter scopes the aggregation query, not just the goal."""
        repo = _FakeRepo()
        novel_id = uuid4()

        await _make_service(repo).writing_report(uuid4(), novel_id)

        assert repo.calls[0][3] == novel_id


# ---------------------------------------------------------------------------
# Streaks (spec today-grace rule; pure derivation over the day sums)
# ---------------------------------------------------------------------------


class TestStreaks:
    async def test_streaks_with_gap_count_current_and_longest_separately(self) -> None:
        """Active {today-1, today-2, today-5, today-6}: current 2, longest 2."""
        report = await _make_service(_FakeRepo(_active((1, 2, 5, 6)))).writing_report(uuid4(), None)

        assert report.streaks.current == 2
        assert report.streaks.longest == 2

    async def test_today_silent_streak_survives_until_the_day_ends(self) -> None:
        """Grace rule: today silent but yesterday active → count back from yesterday."""
        report = await _make_service(_FakeRepo(_active((1, 2, 3)))).writing_report(uuid4(), None)

        assert report.streaks.current == 3

    async def test_today_and_yesterday_silent_means_current_zero(self) -> None:
        """Active only at today-2 → the streak died the day before yesterday."""
        report = await _make_service(_FakeRepo(_active((2,)))).writing_report(uuid4(), None)

        assert report.streaks.current == 0
        assert report.streaks.longest == 1

    async def test_today_active_counts_today_in_the_current_streak(self) -> None:
        """Active today + yesterday, gap before → current 2."""
        report = await _make_service(_FakeRepo(_active((0, 1)))).writing_report(uuid4(), None)

        assert report.streaks.current == 2
        assert report.streaks.longest == 2

    async def test_single_active_day_today(self) -> None:
        """One active day (today) → current 1, longest 1."""
        report = await _make_service(_FakeRepo(_active((0,)))).writing_report(uuid4(), None)

        assert (report.streaks.current, report.streaks.longest) == (1, 1)

    async def test_streak_survives_the_year_boundary(self) -> None:
        """A run across Dec 31 → Jan 1 is consecutive (calendar-aware timedelta)."""
        totals = [
            (date(2025, 12, 30), 10),
            (date(2025, 12, 31), 10),
            (date(2026, 1, 1), 10),
            (date(2026, 1, 2), 10),
        ]
        clock = lambda: datetime(2026, 1, 2, 9, 0, tzinfo=UTC)  # noqa: E731 — injected clock

        report = await _make_service(_FakeRepo(totals), clock=clock).writing_report(uuid4(), None)

        assert report.streaks.current == 4
        assert report.streaks.longest == 4

    async def test_streak_counts_leap_february_29(self) -> None:
        """2024 is a leap year: Feb 28 → Feb 29 → Mar 1 is a 3-day run."""
        totals = [
            (date(2024, 2, 28), 10),
            (date(2024, 2, 29), 10),
            (date(2024, 3, 1), 10),
        ]
        clock = lambda: datetime(2024, 3, 1, 8, 0, tzinfo=UTC)  # noqa: E731 — injected clock

        report = await _make_service(_FakeRepo(totals), clock=clock).writing_report(uuid4(), None)

        assert report.streaks.current == 3

    async def test_net_zero_day_does_not_extend_a_streak(self) -> None:
        """SUM granularity: a day whose events perfectly cancel (SUM 0 — e.g.
        +100 write, -100 delete) is indistinguishable from silence (documented
        approximation of ADR-095's ≥1-event rule) — it breaks the run."""
        totals = [
            (_TODAY - timedelta(days=2), 100),
            (_TODAY - timedelta(days=1), 0),  # events cancelled out
            (_TODAY, 5),
        ]
        report = await _make_service(_FakeRepo(totals)).writing_report(uuid4(), None)

        assert (report.streaks.current, report.streaks.longest) == (1, 1)


# ---------------------------------------------------------------------------
# Goal overlay (spec E-4/E-5 — target from source, LIVE word-count basis)
# ---------------------------------------------------------------------------


class TestGoalBlock:
    async def test_user_scope_report_has_no_goal_block(self) -> None:
        """No novel_id → goal None; the goal source is never consulted."""
        source = _FakeGoalSource(target=50000)

        report = await _make_service(_FakeRepo(), goal_source=source).writing_report(uuid4(), None)

        assert report.goal is None
        assert source.asked == []

    async def test_no_goal_source_wired_means_no_goal_block(self) -> None:
        """goal_source=None (pre-E5 wiring) → goal None without error."""
        report = await _make_service(_FakeRepo()).writing_report(uuid4(), uuid4())

        assert report.goal is None

    async def test_novel_without_target_has_no_goal_block(self) -> None:
        """Source answers None (target unset) → goal None."""
        novel_id = uuid4()
        source = _FakeGoalSource(target=None)

        report = await _make_service(_FakeRepo(), goal_source=source).writing_report(
            uuid4(), novel_id
        )

        assert report.goal is None
        assert source.asked == [novel_id]

    async def test_goal_block_pairs_target_with_live_word_count(self) -> None:
        """target from the source, current from the LIVE chapter word sum (E-4)."""
        repo = _FakeRepo(word_total=12345)
        source = _FakeGoalSource(target=50000)

        report = await _make_service(repo, goal_source=source).writing_report(uuid4(), uuid4())

        assert report.goal is not None
        assert (report.goal.target_words, report.goal.current_words) == (50000, 12345)
        assert report.goal.progress_pct == 24.7  # round(12345 / 50000 * 100, 1)

    async def test_progress_pct_rounds_to_one_decimal(self) -> None:
        """100 of 300 words → 33.3 % (not 33.33…)."""
        report = await _make_service(
            _FakeRepo(word_total=100), goal_source=_FakeGoalSource(target=300)
        ).writing_report(uuid4(), uuid4())

        assert report.goal is not None
        assert report.goal.progress_pct == 33.3

    async def test_non_positive_target_is_treated_as_unset(self) -> None:
        """target ≤ 0 makes progress undefined → goal None (no ZeroDivision)."""
        for target in (0, -100):
            report = await _make_service(
                _FakeRepo(word_total=10), goal_source=_FakeGoalSource(target=target)
            ).writing_report(uuid4(), uuid4())

            assert report.goal is None


# ---------------------------------------------------------------------------
# Contract + wiring edges
# ---------------------------------------------------------------------------


class TestWritingQueryServiceWiring:
    async def test_service_satisfies_writing_query_service_protocol(self) -> None:
        """RULE-03: the router depends on the protocol; the impl satisfies it."""
        assert isinstance(_make_service(_FakeRepo()), WritingQueryServiceProtocol)

    def test_null_goal_source_satisfies_goal_source_protocol(self) -> None:
        """The E5 placeholder seam implements ``GoalSource`` (always None)."""
        assert isinstance(NullGoalSource(), GoalSource)

    async def test_window_days_below_one_is_rejected(self) -> None:
        """A non-positive window would emit zero dailies — constructor guard."""
        with pytest.raises(ValueError, match="window_days"):
            _make_service(_FakeRepo(), window_days=0)

    async def test_report_is_a_writing_report(self) -> None:
        """The public method returns the contract response model (spec E-5)."""
        report = await _make_service(_FakeRepo()).writing_report(uuid4(), None)

        assert isinstance(report, WritingReport)
