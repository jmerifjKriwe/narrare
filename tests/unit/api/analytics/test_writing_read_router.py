# tests/unit/api/analytics/test_writing_read_router.py
"""Unit tests for the writing-stats read shell: repository query wiring +
``GET /analytics/writing`` (STATS-001 E-5, ADR-095 D4).

Two layers in ONE module under the RULE-04 test-budget cap (7 files for
E4; the recorder test file merges layers the same way when they serve one
behavior): the ``WritingStatsQueryRepository`` fake-session wiring tests
pin the UTC-day pin (``date_trunc('day', created_at AT TIME ZONE 'UTC')``
— the cheap unit-level mirror of the usage-month query-shape assertion;
real-PG proof lives in the 0045 round-trip family), half-open bounds,
user/novel scoping, day ordering, and the goal word-sum query. The router
tests run ``create_app()`` (NotFoundError → 404 mapping is app-level)
with overridden auth/session/service: delegation, novel_id passthrough,
401, and the foreign ≡ unknown 404 gate matrix.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from tests.fakes.fake_db_session import FakeDbSession, FakeResult
from tests.unit.api.analytics._repository_fakes import _AggSession

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.analytics.contracts import (
    WritingDailyPoint,
    WritingGoalProgress,
    WritingReport,
    WritingStreaks,
)
from narrare.analytics.dependencies import (
    get_writing_query_service,
    verify_writing_novel_scope,
)
from narrare.analytics.writing_repository import WritingStatsQueryRepository
from narrare.analytics.writing_service import NullGoalSource, WritingQueryService
from narrare.novels.models import Novel
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

USER_ID = "00000000-0000-0000-0000-0000000000ff"
_NOVEL_ID = uuid4()
_TODAY = date(2026, 10, 8)
_START = datetime(2026, 7, 11, tzinfo=UTC)
_END = datetime(2026, 10, 9, tzinfo=UTC)

_WRITING_URL = "/api/v1/analytics/writing"


# ---------------------------------------------------------------------------
# Repository: daily_totals query wiring + mapping (fake session)
# ---------------------------------------------------------------------------


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
            (datetime(2026, 10, 1), 120),
            (datetime(2026, 10, 2), -30),  # deletes are honest negatives
            (datetime(2026, 10, 3), 0),  # COALESCE fallback arrives as int 0
        ]

        result = await _repo(_AggSession(rows)).daily_totals(uuid4(), _START, _END)

        assert result == [
            (date(2026, 10, 1), 120),
            (date(2026, 10, 2), -30),
            (date(2026, 10, 3), 0),
        ]
        assert all(isinstance(day, date) for day, _ in result)

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


# ---------------------------------------------------------------------------
# Router: GET /analytics/writing (create_app harness — app-level 404 mapping)
# ---------------------------------------------------------------------------


class _FakeWritingService:
    """Fake ``WritingQueryServiceProtocol`` — records ``writing_report`` calls."""

    def __init__(self, report: WritingReport) -> None:
        self._report = report
        self.calls: list[tuple[UUID, UUID | None]] = []

    async def writing_report(self, user_id: UUID, novel_id: UUID | None) -> WritingReport:
        self.calls.append((user_id, novel_id))
        return self._report


def _canned_report(goal: WritingGoalProgress | None = None) -> WritingReport:
    return WritingReport(
        dailies=[
            WritingDailyPoint(date=_TODAY - timedelta(days=offset), words=0) for offset in range(90)
        ],
        streaks=WritingStreaks(current=0, longest=0),
        today_words=0,
        total_words=0,
        goal=goal,
    )


def _make_app(service: _FakeWritingService, *, authenticate: bool = True) -> FastAPI:
    """Production app with overridden auth/service; gate reads the fake session."""
    application = create_app()
    if authenticate:
        application.dependency_overrides[get_current_user_id] = lambda: USER_ID
    application.dependency_overrides[get_writing_query_service] = lambda: service
    return application


def _install_session(app: FastAPI, *queued: object) -> FakeDbSession:
    """Override the session dependency with a queued-result fake (gate lookup)."""
    session = FakeDbSession(results=list(queued))
    app.dependency_overrides[get_async_session] = lambda: session
    return session


class TestWritingRoute:
    async def test_get_writing_delegates_and_defaults_novel_to_none(self) -> None:
        """200: no ``novel_id`` query → service receives None; report serialized."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL)

        assert response.status_code == status.HTTP_200_OK
        assert fake.calls == [(UUID(USER_ID), None)]
        assert WritingReport.model_validate(response.json()) == fake._report

    async def test_get_writing_passes_owned_novel_id_through_to_service(self) -> None:
        """200: ``?novel_id=`` (owned) reaches the service unchanged."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app, Novel(id=_NOVEL_ID, user_id=UUID(USER_ID)))  # gate lookup

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL, params={"novel_id": str(_NOVEL_ID)})

        assert response.status_code == status.HTTP_200_OK
        assert fake.calls == [(UUID(USER_ID), _NOVEL_ID)]

    async def test_get_writing_without_token_returns_401(self) -> None:
        """401 unauthenticated; the service is never called."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake, authenticate=False)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert fake.calls == []

    async def test_foreign_novel_returns_404_without_service_call(self) -> None:
        """Foreign ≡ unknown (anti-enumeration): 404, zero service work."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app, None)  # gate lookup misses → NotFoundError

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL, params={"novel_id": str(_NOVEL_ID)})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "detail": f"Novel ({_NOVEL_ID}) not found",
            "code": "NOT_FOUND",
        }
        assert fake.calls == []

    async def test_unknown_novel_404_shape_matches_foreign(self) -> None:
        """Unknown novel id → the SAME 404 body shape as a foreign one."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app, None)
        unknown = uuid4()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL, params={"novel_id": str(unknown)})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "detail": f"Novel ({unknown}) not found",
            "code": "NOT_FOUND",
        }

    async def test_goal_block_serializes_when_set(self) -> None:
        """A set goal rides the report JSON (badge data in one round trip)."""
        report = _canned_report(
            goal=WritingGoalProgress(target_words=50000, current_words=12345, progress_pct=24.7)
        )
        fake = _FakeWritingService(report)
        app = _make_app(fake)
        _install_session(app, Novel(id=_NOVEL_ID, user_id=UUID(USER_ID)))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL, params={"novel_id": str(_NOVEL_ID)})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["goal"] == {
            "target_words": 50000,
            "current_words": 12345,
            "progress_pct": 24.7,
        }

    async def test_goal_block_defaults_to_null_when_unset(self) -> None:
        """User-scope (or target-less novel) → ``goal: null`` (spec E-5)."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL)

        assert response.json()["goal"] is None


# ---------------------------------------------------------------------------
# The optional-scope gate dependency (direct unit matrix)
# ---------------------------------------------------------------------------


class TestVerifyWritingNovelScope:
    async def test_absent_novel_id_passes_without_a_query(self) -> None:
        """User-scope report: the gate is a no-op — no session touched."""
        session = FakeDbSession()

        await verify_writing_novel_scope(cast("AsyncSession", session), USER_ID, novel_id=None)

        assert session.statements == []

    async def test_present_novel_id_is_ownership_gated(self) -> None:
        """A present novel_id rides the canonical gate — foreign → NotFoundError."""
        session = FakeDbSession(results=[None])  # ownership lookup misses

        with pytest.raises(NotFoundError) as exc_info:
            await verify_writing_novel_scope(
                cast("AsyncSession", session), USER_ID, novel_id=_NOVEL_ID
            )

        assert str(exc_info.value) == f"Novel ({_NOVEL_ID}) not found"


# ---------------------------------------------------------------------------
# DI wiring (production factory, no request)
# ---------------------------------------------------------------------------


def test_get_writing_query_service_wires_repo_and_null_goal_source() -> None:
    """Production wiring: query repository over the session + E5 placeholder."""
    service = get_writing_query_service(cast("AsyncSession", FakeDbSession()))

    assert isinstance(service, WritingQueryService)
    assert isinstance(
        service._repo,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
        WritingStatsQueryRepository,
    )
    assert isinstance(
        service._goal_source,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
        NullGoalSource,
    )
