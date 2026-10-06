# tests/unit/api/analytics/test_costs_router.py
"""Router-level tests for ``GET /analytics/costs`` (STATS-002 spec §4).

Local-app harness (minimal ``FastAPI()`` + ``include_router(router)``): the
production app does NOT include the analytics router yet — registration is
Task 11 (``_app/main.py``) — so the ``create_app()`` harness used by
registered routers (``test_chapter_router.py`` convention) would 404 here.

Auth is overridden via ``dependency_overrides[get_current_user_id]`` (the
canonical Task 9 auth dependency). Delegation is verified against a fake
service implementing ``CostQueryServiceProtocol``; the year-edge 422 cases
run the REAL ``CostQueryService`` over a fake repository (the fake would
never raise) through the ``InvalidMonthError`` → 422 handler that Task 11
must register app-level (mirrors the ``ScopeError`` handler precedent in
``_app/main.py``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from tests.fakes.fake_db_session import FakeDbSession

from narrare._app.dependencies import get_current_user_id
from narrare.analytics.contracts import (
    CostMonthReport,
    CostQueryServiceProtocol,
    CostTotals,
)
from narrare.analytics.dependencies import get_cost_query_service
from narrare.analytics.repository import UsageAggRow, UsageRecordRepository
from narrare.analytics.router import invalid_month_error_handler, router
from narrare.analytics.service import CostQueryService, InvalidMonthError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeCostQueryService:
    """Fake ``CostQueryServiceProtocol`` — records ``month_report`` calls."""

    def __init__(self, report: CostMonthReport) -> None:
        self._report = report
        self.calls: list[tuple[UUID, str | None]] = []

    async def month_report(self, user_id: UUID, month: str | None) -> CostMonthReport:
        self.calls.append((user_id, month))
        return self._report


class _FakeUsageRepository:
    """Empty fake repo for the real-service year-edge tests (no SQL)."""

    async def aggregate_range(self, user_id: UUID, start: object, end: object) -> list[UsageAggRow]:
        return []


def _real_service() -> CostQueryService:
    """Real bucketing service over an empty fake repo (RULE-23 fake seam)."""
    return CostQueryService(cast("UsageRecordRepository", _FakeUsageRepository()))


def _zeroed_report(month: str) -> CostMonthReport:
    return CostMonthReport(
        month=month,
        totals=CostTotals(calls=0, tokens_in=0, tokens_out=0, cost_usd=0.0, unpriced_calls=0),
        by_intent=[],
        by_model=[],
        trend=[],
    )


def _make_app(
    service: CostQueryServiceProtocol | _FakeCostQueryService, *, authenticate: bool = True
) -> FastAPI:
    """Minimal app: analytics router + auth/service overrides + 422 handler."""
    app = FastAPI()
    app.include_router(router)
    # Decorator-form registration (generic typing accepts the narrow exc type,
    # matching _app/main.py's handlers; add_exception_handler() does not).
    app.exception_handler(InvalidMonthError)(invalid_month_error_handler)
    if authenticate:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_cost_query_service] = lambda: service
    return app


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Delegation (fake service)
# ---------------------------------------------------------------------------


async def test_get_costs_without_month_defaults_to_none_and_returns_report() -> None:
    """200: no ``month`` query → service receives ``None``; report serialized."""
    fake = _FakeCostQueryService(_zeroed_report("2026-10"))

    async with _client(_make_app(fake)) as ac:
        response = await ac.get("/analytics/costs")

    assert response.status_code == status.HTTP_200_OK
    assert fake.calls == [(UUID(TEST_USER_ID), None)]
    assert CostMonthReport.model_validate(response.json()) == fake._report


async def test_get_costs_with_explicit_month_passes_it_through_to_service() -> None:
    """200: ``?month=YYYY-MM`` reaches the service unchanged."""
    fake = _FakeCostQueryService(_zeroed_report("2026-03"))

    async with _client(_make_app(fake)) as ac:
        response = await ac.get("/analytics/costs", params={"month": "2026-03"})

    assert response.status_code == status.HTTP_200_OK
    assert fake.calls == [(UUID(TEST_USER_ID), "2026-03")]
    assert response.json()["month"] == "2026-03"


async def test_get_costs_scopes_to_the_authenticated_user() -> None:
    """The overridden auth id (JWT ``sub``) — not any client input — is passed."""
    fake = _FakeCostQueryService(_zeroed_report("2026-10"))

    async with _client(_make_app(fake)) as ac:
        await ac.get("/analytics/costs")

    assert fake.calls[0][0] == UUID(TEST_USER_ID)


@pytest.mark.parametrize("bad_month", ["2026-13", "garbage"])
async def test_get_costs_with_malformed_month_returns_422(bad_month: str) -> None:
    """FastAPI Query pattern rejects malformed months before the service runs."""
    fake = _FakeCostQueryService(_zeroed_report("2026-10"))

    async with _client(_make_app(fake)) as ac:
        response = await ac.get("/analytics/costs", params={"month": bad_month})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Year edge (real service — regex-valid but unconstructible window)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("edge_month", ["0000-01", "9999-12"])
async def test_get_costs_with_unconstructible_year_returns_422_not_500(
    edge_month: str,
) -> None:
    """Regex-valid months with unconstructible windows → 422 (InvalidMonthError).

    Task 7 review rider: these used to escape as bare ``ValueError`` → 500.
    """
    app = _make_app(_real_service())

    async with _client(app) as ac:
        response = await ac.get("/analytics/costs", params={"month": edge_month})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert edge_month in response.json()["detail"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_get_costs_without_token_returns_401() -> None:
    """401 unauthenticated; the service is never called."""
    fake = _FakeCostQueryService(_zeroed_report("2026-10"))

    async with _client(_make_app(fake, authenticate=False)) as ac:
        response = await ac.get("/analytics/costs")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"
    assert fake.calls == []


# ---------------------------------------------------------------------------
# DI wiring (production factory, no request)
# ---------------------------------------------------------------------------


def test_get_cost_query_service_wires_repo_from_session() -> None:
    """Production wiring: ``CostQueryService(UsageRecordRepository(session))``."""
    service = get_cost_query_service(cast("AsyncSession", FakeDbSession()))

    assert isinstance(service, CostQueryService)
    assert isinstance(
        service._repo,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
        UsageRecordRepository,
    )
