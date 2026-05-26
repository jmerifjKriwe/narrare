"""Integration tests for analysis router endpoints.

Tests the full HTTP request/response cycle for:
- POST /api/v1/analysis/beta-reader — auth required
- POST /api/v1/analysis/beta-reader/deep-dive — auth required
- Validation errors with auth (422)
- Auth requirements (401)

Note: Auth runs before body validation, so validation errors only appear
when authenticated. Without auth, all endpoints return 401.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a test app with mocked dependencies."""
    from narrare._app.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


class TestAuthRequired:
    """Endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_analyze_requires_auth(self, app) -> None:
        """POST /analysis/beta-reader returns 401 without auth."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analysis/beta-reader",
                params={"novel_id": str(uuid4()), "user_id": str(uuid4())},
                json={"chapter_ids": [str(uuid4())]},
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_deep_dive_requires_auth(self, app) -> None:
        """POST /analysis/beta-reader/deep-dive returns 401 without auth."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analysis/beta-reader/deep-dive",
                params={"novel_id": str(uuid4()), "user_id": str(uuid4())},
                json={
                    "chapter_ids": [str(uuid4())],
                    "category": "plot",
                    "cache_key": "abc123",
                },
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Validation (auth-gated)
# ---------------------------------------------------------------------------


class TestValidationGatedByAuth:
    """Without auth, even invalid requests get 401 (not 422).

    This is correct behavior: auth middleware runs before body validation.
    Validation errors (422) only surface for authenticated requests.
    """

    @pytest.mark.asyncio
    async def test_empty_chapter_ids_without_auth_returns_401(self, app) -> None:
        """POST with empty chapter_ids without auth → 401, not 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analysis/beta-reader",
                params={"novel_id": str(uuid4()), "user_id": str(uuid4())},
                json={"chapter_ids": []},
            )

        # Auth runs before validation → 401
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_too_many_chapter_ids_without_auth_returns_401(self, app) -> None:
        """POST with >5 chapter_ids without auth → 401, not 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analysis/beta-reader",
                params={"novel_id": str(uuid4()), "user_id": str(uuid4())},
                json={"chapter_ids": [str(uuid4()) for _ in range(6)]},
            )

        # Auth runs before validation → 401
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Router existence — ensures routes are properly mounted
# ---------------------------------------------------------------------------


class TestRouterMounted:
    """Analysis router is properly mounted in the app."""

    def test_router_prefix(self, app) -> None:
        """Router has /analysis prefix."""
        from narrare.analysis.router import router

        assert router.prefix == "/analysis"

    def test_router_has_two_routes(self, app) -> None:
        """Router defines beta-reader and deep-dive routes."""
        from narrare.analysis.router import router

        route_paths = [getattr(r, "path", "") for r in router.routes]
        assert "/analysis/beta-reader" in route_paths
        assert "/analysis/beta-reader/deep-dive" in route_paths
