# tests/unit/api/analytics/test_writing_read_router_totals.py
"""``WritingStatsQueryRepository`` SUM-query wiring for the writing-stats read
shell (STATS-001 E-5/E4, ADR-095 D4/D5) — fake-session tests split out of
``test_writing_read_router.py`` under the RULE-04 test-budget cap.

The daily-totals tests pin the UTC-day bucket (``date_trunc('day',
created_at AT TIME ZONE 'UTC')`` — the cheap unit-level mirror of the
usage-month query-shape assertion; real-PG proof lives in the 0045
round-trip family), half-open bounds, exclusive user binding, optional
novel scoping, day ordering, and the per-day event count (streak basis).
The word-total tests pin the goal word-sum basis (ADR-095 D5:
SUM(chapters.word_count)) and the E4-fix all-time total (SUM(delta_words)
with NO window bounds).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from tests.fakes.fake_db_session import FakeDbSession, FakeResult
from tests.unit.api.analytics._repository_fakes import _AggSession

from narrare.analytics.writing_repository import WritingStatsQueryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_NOVEL_ID = uuid4()
_START = datetime(2026, 7, 11, tzinfo=UTC)
_END = datetime(2026, 10, 9, tzinfo=UTC)


def _repo(session: _AggSession | FakeDbSession) -> WritingStatsQueryRepository:
    """Repository over a fake session (``cast`` = the RULE-23 fake seam)."""
    return WritingStatsQueryRepository(cast("AsyncSession", session))


def _novel_id_criterion(session: _AggSession) -> bool:
    """Whether the executed statement filters on ``novel_id``."""
    return any(
        getattr(crit.left, "name", None) == "novel_id"
        for crit in session.statements[0].whereclause.clauses
    )


class TestDailyTotalsQuery:
    async def test_daily_totals_pins_utc_day_bucket(self) -> None:
        """Query-shape pin: date_trunc('day', created_at AT TIME ZONE 'UTC').

        Without the pin a non-UTC session would cut days in local time and
        mislabel edge-of-day rows (same rationale as the usage-month pin).
        """
        session = _AggSession([])

        await _repo(session).daily_totals(uuid4(), _START, _END)

        grouped = session.statements[0]._group_by_clauses
        assert [clause.name for clause in grouped] == ["day"]
        assert grouped[0].element.name == "date_trunc"
        tz_arg = list(grouped[0].element.clauses)[1]
        assert tz_arg.operator.opstring == "AT TIME ZONE"
        assert tz_arg.left.name == "created_at"
        assert tz_arg.right.value == "UTC"

    async def test_daily_totals_bounds_are_half_open(self) -> None:
        """Range is [start, end): created_at >= start AND created_at < end."""
        session = _AggSession([])

        await _repo(session).daily_totals(uuid4(), _START, _END)

        bounds = [
            (crit.operator.__name__, crit.right.value)
            for crit in session.statements[0].whereclause.clauses
            if crit.left.name == "created_at"
        ]
        assert bounds == [("ge", _START), ("lt", _END)]

    async def test_daily_totals_binds_caller_user_id_exclusively(self) -> None:
        """Exactly one user_id bind — the CALLER's id (attribution scoping)."""
        session = _AggSession([])
        user_id = uuid4()

        await _repo(session).daily_totals(user_id, _START, _END)

        params = session.statements[0].compile().params
        user_binds = {key: value for key, value in params.items() if key.startswith("user_id")}
        assert list(user_binds.values()) == [user_id]

    async def test_daily_totals_novel_filter_applies_only_when_present(self) -> None:
        """novel_id=None → user-scope query; a novel id adds exactly that filter."""
        unscoped = _AggSession([])
        await _repo(unscoped).daily_totals(uuid4(), _START, _END)
        assert not _novel_id_criterion(unscoped)

        novel_id = uuid4()
        scoped = _AggSession([])
        await _repo(scoped).daily_totals(uuid4(), _START, _END, novel_id=novel_id)

        assert _novel_id_criterion(scoped)
        params = scoped.statements[0].compile().params
        assert [value for key, value in params.items() if key.startswith("novel_id")] == [novel_id]

    async def test_daily_totals_maps_rows_day_ordered(self) -> None:
        """Rows map 1:1 (naive date-trunc timestamp → date) preserving DB order."""
        rows = [
            (datetime(2026, 10, 1), 120, 2),
            (datetime(2026, 10, 2), -30, 1),  # deletes are honest negatives
            (datetime(2026, 10, 3), 0, 3),  # COALESCE fallback arrives as int 0
        ]

        result = await _repo(_AggSession(rows)).daily_totals(uuid4(), _START, _END)

        assert result == [
            (date(2026, 10, 1), 120, 2),
            (date(2026, 10, 2), -30, 1),
            (date(2026, 10, 3), 0, 3),
        ]
        assert all(isinstance(day, date) for day, _, _ in result)

    async def test_daily_totals_orders_by_day_ascending(self) -> None:
        """ORDER BY = day ascending (oldest-first dailies contract)."""
        session = _AggSession([])

        await _repo(session).daily_totals(uuid4(), _START, _END)

        ordered = session.statements[0]._order_by_clauses
        assert len(ordered) == 1
        assert str(ordered[0]).endswith("ASC")


class TestNovelWordTotalQuery:
    async def test_novel_word_total_returns_the_live_chapter_word_sum(self) -> None:
        """Goal progress basis (ADR-095 D5): SUM(chapters.word_count), not events."""
        session = FakeDbSession(results=[FakeResult(value=4321)])

        total = await _repo(session).novel_word_total(_NOVEL_ID)

        assert total == 4321
        params = session.statements[0].compile().params
        assert [value for key, value in params.items() if key.startswith("novel_id")] == [_NOVEL_ID]

    async def test_novel_word_total_maps_defensive_none_to_zero(self) -> None:
        """COALESCE makes NULL impossible; a None slip maps to 0 (mirrors _to_decimal)."""
        session = FakeDbSession(results=[FakeResult(value=None)])

        assert await _repo(session).novel_word_total(_NOVEL_ID) == 0


class TestAllTimeWordTotalQuery:
    async def test_all_time_word_total_sums_events_without_window_bounds(self) -> None:
        """ALL-TIME total (E4 fix round 1): SUM(delta_words) with NO created_at
        bounds — the 90-day window bounds dailies/streaks, never the total."""
        session = FakeDbSession(results=[FakeResult(value=1500)])

        total = await _repo(session).all_time_word_total(uuid4())

        assert total == 1500
        where = session.statements[0].whereclause
        assert where.left.name == "user_id"  # the ONLY criterion — no created_at bounds

    async def test_all_time_word_total_novel_filter_applies_only_when_present(self) -> None:
        """novel_id=None → user-scope sum; a novel id adds exactly that filter."""
        unscoped = FakeDbSession(results=[FakeResult(value=0)])
        await _repo(unscoped).all_time_word_total(uuid4())
        unscoped_params = unscoped.statements[0].compile().params
        assert [key for key in unscoped_params if key.startswith("novel_id")] == []

        novel_id = uuid4()
        scoped = FakeDbSession(results=[FakeResult(value=700)])

        total = await _repo(scoped).all_time_word_total(uuid4(), novel_id=novel_id)

        assert total == 700
        scoped_params = scoped.statements[0].compile().params
        assert [value for key, value in scoped_params.items() if key.startswith("novel_id")] == [
            novel_id
        ]

    async def test_all_time_word_total_maps_defensive_none_to_zero(self) -> None:
        """COALESCE makes NULL impossible; a None slip maps to 0 (mirrors _to_decimal)."""
        session = FakeDbSession(results=[FakeResult(value=None)])

        assert await _repo(session).all_time_word_total(uuid4()) == 0
