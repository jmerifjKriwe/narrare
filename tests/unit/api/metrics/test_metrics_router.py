"""Unit tests for metrics/router.py"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from httpx import ASGITransport, AsyncClient

from narrare._app.main import app


@pytest.fixture
def mock_engine() -> MagicMock:
    # narrare: allow-direct-llm  reason="Mocking SQLAlchemy Engine — no domain contract"
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=conn)
    ctx_manager.__aexit__ = AsyncMock(return_value=False)
    engine.connect = MagicMock(  # narrare: allow  reason="Mocking SQLAlchemy Engine connect method"
        return_value=ctx_manager
    )
    return engine


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealth:
    async def test_returns_200_with_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReady:
    @patch("narrare.metrics.router.get_engine")
    async def test_returns_200_when_db_healthy(
        self, mock_get_engine: AsyncMock, client: AsyncClient, mock_engine: MagicMock
    ) -> None:
        mock_get_engine.return_value = mock_engine
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
