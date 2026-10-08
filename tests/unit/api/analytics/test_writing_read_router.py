# tests/unit/api/analytics/test_writing_read_router.py
"""Unit tests for the writing-stats read shell: ``GET /analytics/writing``
(STATS-001 E-5, ADR-095 D4) plus the optional-scope gate and DI wiring.

The ``WritingStatsQueryRepository`` SUM-query wiring tests (daily totals,
novel word total, all-time total) live in the sibling
``test_writing_read_router_totals.py`` (RULE-04 test-budget split; the
recorder test file likewise merges layers when they serve one behavior).
This module runs ``create_app()`` (NotFoundError → 404 mapping is
app-level) with overridden auth/session/service: delegation, novel_id
passthrough, 401, the foreign ≡ unknown 404 gate matrix, the
malformed-novel_id 422, goal-block serialization, the direct gate matrix,
and the production DI wiring.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from tests.fakes.fake_db_session import FakeDbSession

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
from narrare.analytics.writing_service import WritingQueryService
from narrare.novels.models import Novel
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

USER_ID = "00000000-0000-0000-0000-0000000000ff"
_NOVEL_ID = uuid4()
_TODAY = date(2026, 10, 8)

_WRITING_URL = "/api/v1/analytics/writing"


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

    async def test_malformed_novel_id_returns_422_without_service_call(self) -> None:
        """422 matrix: a non-UUID ``novel_id`` fails request validation before
        the scope gate and the service run."""
        fake = _FakeWritingService(_canned_report())
        app = _make_app(fake)
        _install_session(app)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(_WRITING_URL, params={"novel_id": "not-a-uuid"})

        assert response.status_code == 422
        assert fake.calls == []

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


def test_get_writing_query_service_wires_repo_and_project_settings_goal_source() -> None:
    """Production wiring: query repository + real goal source, same session.

    E5 swapped the ``NullGoalSource`` placeholder for the real
    ``ProjectSettingsGoalSource`` (project_settings.writing_goals) at this
    one factory — service/router untouched (the E4 seam contract).
    """
    from narrare.settings.writing_goals import ProjectSettingsGoalSource

    service = get_writing_query_service(cast("AsyncSession", FakeDbSession()))

    assert isinstance(service, WritingQueryService)
    assert isinstance(
        service._repo,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
        WritingStatsQueryRepository,
    )
    assert isinstance(
        service._goal_source,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
        ProjectSettingsGoalSource,
    )
