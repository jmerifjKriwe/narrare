"""Integration tests for health and metrics endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient

import pytest

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_health_no_auth_required(self, client: AsyncClient) -> None:
        """Health endpoint must not require authentication."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestMetricsEndpoint:
    async def test_metrics_returns_prometheus_format(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        body = response.text
        assert len(body) > 0
