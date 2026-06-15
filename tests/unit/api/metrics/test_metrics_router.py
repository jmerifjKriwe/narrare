"""Unit tests for metrics/router.py"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from types import TracebackType

# Module-level state is shared across test files; reset before health checks.
import narrare._app.observability as _obs_mod
from narrare._app.main import app


def _reset_observability_state() -> None:
    """Reset observability module state to pristine."""
    with _obs_mod._state_lock:
        cast("Any", _obs_mod)._otel_available = None
        cast("Any", _obs_mod)._failure_reason = ""
        cast("Any", _obs_mod)._warning_emitted = False
        cast("Any", _obs_mod)._otel_state = None
        cast("Any", _obs_mod)._endpoint_configured = False


class FakeConnection:
    """Minimal async SQLAlchemy connection fake for readiness checks."""

    async def execute(self, statement: object) -> None:
        """Record that a statement could be executed successfully."""


class FakeConnectionContext:
    """Async context manager returned by FakeEngine.connect()."""

    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        """Enter the fake connection context."""
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the fake connection context without suppressing errors."""
        return False


class FakeEngine:
    """Minimal SQLAlchemy engine fake with async connect semantics."""

    def __init__(self) -> None:
        self._connection = FakeConnection()

    def connect(self) -> FakeConnectionContext:
        """Return an async connection context manager."""
        return FakeConnectionContext(self._connection)


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealth:
    async def test_returns_200_with_healthy_status(self, client: AsyncClient) -> None:
        """Health endpoint returns 200 with severity-based status.

        In the test environment OTel is importable but no endpoint is
        configured, so the state defaults to ``not_configured`` →
        ``severity == "healthy"``.
        """
        _reset_observability_state()
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"

        observability = body["observability"]
        expected_keys = {
            "available",
            "failure_reason",
            "warning_emitted",
            "state",
            "severity",
            "endpoint_configured",
        }
        assert set(observability) == expected_keys
        assert isinstance(observability["available"], bool)
        assert isinstance(observability["failure_reason"], str)
        assert isinstance(observability["warning_emitted"], bool)
        assert isinstance(observability["state"], str)
        assert isinstance(observability["severity"], str)
        assert isinstance(observability["endpoint_configured"], bool)
        assert observability["state"] in {
            "not_configured",
            "configured_ok",
            "configured_failed",
            "package_unavailable",
        }
        assert observability["severity"] in {"healthy", "degraded", "critical"}


class TestReady:
    @patch("narrare.metrics.router.get_engine")
    async def test_returns_200_when_db_healthy(
        self, mock_get_engine: AsyncMock, client: AsyncClient, fake_engine: FakeEngine
    ) -> None:
        mock_get_engine.return_value = fake_engine
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    @patch("narrare.metrics.router.get_engine")
    async def test_returns_503_when_db_unreachable(
        self, mock_get_engine: AsyncMock, client: AsyncClient
    ) -> None:
        mock_get_engine.side_effect = Exception("connection refused")
        response = await client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert "connection refused" in body["error"]


class TestMetrics:
    async def test_returns_prometheus_content(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
