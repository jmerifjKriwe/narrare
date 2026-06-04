"""Unit tests for metrics/router.py"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from types import TracebackType

from narrare._app.main import app


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
    async def test_returns_200_with_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

        observability = body["observability"]
        assert set(observability) == {"available", "failure_reason", "warning_emitted"}
        assert isinstance(observability["available"], bool)
        assert isinstance(observability["failure_reason"], str)
        assert isinstance(observability["warning_emitted"], bool)


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
