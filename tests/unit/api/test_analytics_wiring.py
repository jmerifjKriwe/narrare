# tests/unit/api/test_analytics_wiring.py
"""App-wiring tests for STATS-002 (Task 11): router, handler, middleware, sink.

Proves on the REAL ``create_app()`` harness that:

1. ``GET /api/v1/analytics/costs`` is routed (analytics router included).
2. ``InvalidMonthError`` is handled app-level (decorator-form registration).
3. ``UsageAttributionMiddleware`` wraps outermost (added last).
4. Lifespan startup registers the ``SqlUsageEventSink`` on the Core seam and
   shutdown clears it — with the module-level session factory bound.
5. Handoff case: ``"0000-01"`` on the real app ⇒ 422 ``INVALID_MONTH`` (not
   404/500) — proving router inclusion AND handler registration end-to-end.

No database is required: the lifespan only stores the session factory, and
the service rejects ``"0000-01"`` before the repository is touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from narrare._app.database import get_session_factory
from narrare._app.dependencies import get_current_user_id
from narrare.analytics.middleware import UsageAttributionMiddleware
from narrare.analytics.router import invalid_month_error_handler
from narrare.analytics.service import InvalidMonthError
from narrare.analytics.usage_sink import SqlUsageEventSink
from narrare_core.llm.usage_events import get_usage_event_sink

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI

import pytest

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"
COSTS_PATH = "/api/v1/analytics/costs"


@pytest.fixture
def app() -> Iterator[FastAPI]:
    """Fresh real app per test (mirrors test_main_origin_validation)."""
    from narrare._app.main import create_app

    application = create_app()
    application.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield application
    application.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Router + handler registration
# ---------------------------------------------------------------------------


class TestRouteWiring:
    def test_costs_route_is_registered_on_real_app(self, app: FastAPI) -> None:
        # FastAPI ≥0.129 wraps included routers as lazy ``_IncludedRouter``
        # objects, so flat ``app.routes`` enumeration no longer lists included
        # paths. The OpenAPI schema is the public, version-stable surface for
        # the same assertion; the year-edge test below proves actual routing.
        assert COSTS_PATH in app.openapi()["paths"]

    def test_invalid_month_handler_is_registered_app_level(self, app: FastAPI) -> None:
        assert app.exception_handlers.get(InvalidMonthError) is invalid_month_error_handler


# ---------------------------------------------------------------------------
# Middleware ordering — last-added wraps outermost
# ---------------------------------------------------------------------------


class TestMiddlewareWiring:
    def test_attribution_middleware_wraps_outermost(self, app: FastAPI) -> None:
        # Starlette's add_middleware() inserts at index 0, so the FIRST entry
        # of user_middleware is the OUTERMOST wrapper.
        assert app.user_middleware, "expected user middleware on the app"
        assert app.user_middleware[0].cls is UsageAttributionMiddleware


# ---------------------------------------------------------------------------
# Lifespan sink registration / clear
# ---------------------------------------------------------------------------


class TestSinkLifecycle:
    def test_startup_registers_sql_sink_and_shutdown_clears_it(self, app: FastAPI) -> None:
        with TestClient(app):
            sink = get_usage_event_sink()
            assert isinstance(sink, SqlUsageEventSink)
            # The exact production sessionmaker must be bound (wiring proof).
            assert sink._session_factory is get_session_factory()  # pyright: ignore[reportPrivateUsage]
        assert get_usage_event_sink() is None


# ---------------------------------------------------------------------------
# Handoff case — year-edge month on the real app
# ---------------------------------------------------------------------------


class TestYearEdgeHandoff:
    def test_year_edge_month_returns_422_on_real_app(self, app: FastAPI) -> None:
        with TestClient(app) as client:
            response = client.get(COSTS_PATH, params={"month": "0000-01"})

        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "INVALID_MONTH"
