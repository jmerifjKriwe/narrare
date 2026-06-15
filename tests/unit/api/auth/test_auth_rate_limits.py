"""Regression tests for auth rate-limiter — factory vs singleton bug.

The bug: ``auth/router.py`` originally used factory functions
(``_register_rate_limiter``, ``_login_rate_limiter``) that returned
a NEW ``RateLimiter`` on every invocation.  FastAPI calls
``Depends(factory_function)`` per request, so each request got a
fresh ``Limiter`` with zero accumulated state — the rate counter
was always zero, limits were NEVER enforced.

Fix: Replace factory functions with module-level **singleton**
``_RateLimiterDep`` instances (same pattern used by
``narrare._app.rate_limits``).

Regression test strategy:
    1. Mount the real ``auth.router`` on a fresh ``FastAPI`` app.
    2. Override ``_get_auth_service`` (requires DB) with a mock.
    3. Fire N requests (where N = rate limit) → expect 2xx.
    4. Fire request N+1 → **must** get **429** (proof the limiter
       is shared across requests).

    BEFORE the fix (factory functions): request N+1 gets 2xx → test
    fails (RED).
    AFTER the fix (module-level singletons): request N+1 gets 429 →
    test passes (GREEN).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from narrare.auth.router import _get_auth_service, router
from narrare.auth.schemas import TokenResponse


class TestAuthRegisterRateLimiter:
    """``/auth/register`` — 3 requests/min → 4th must be 429."""

    def test_register_ratelimit_allows_first_three_blocks_fourth(
        self,
    ) -> None:
        """Verify the /auth/register rate limiter is a shared singleton.

        Sends 3 requests (should succeed within the 3/min limit) then
        a 4th (must be rejected with 429).
        """
        # Arrange
        app = FastAPI()
        app.include_router(router)

        mock_service = _make_mock_auth_service()

        # Override the DB-backed _get_auth_service with our mock
        app.dependency_overrides[_get_auth_service] = lambda: mock_service

        client = TestClient(app)

        # Act & Assert — 3 requests allowed
        for i in range(3):
            resp = client.post(
                "/auth/register",
                json={"email": "test@example.com", "password": "password123"},
            )
            assert resp.status_code in (200, 201), (
                f"Request {i + 1}/3 expected 2xx, got {resp.status_code}"
            )

        # 4th request → rate limited
        resp = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 429, f"Expected 429 (rate limited), got {resp.status_code}"


class TestAuthLoginRateLimiter:
    """``/auth/login`` — 5 requests/min → 6th must be 429."""

    def test_login_ratelimit_allows_first_five_blocks_sixth(
        self,
    ) -> None:
        """Verify the /auth/login rate limiter is a shared singleton.

        Sends 5 requests (should succeed within the 5/min limit) then
        a 6th (must be rejected with 429).
        """
        # Arrange
        app = FastAPI()
        app.include_router(router)

        mock_service = _make_mock_auth_service()
        app.dependency_overrides[_get_auth_service] = lambda: mock_service

        client = TestClient(app)

        # Act & Assert — 5 requests allowed
        for i in range(5):
            resp = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )
            assert resp.status_code in (200, 201), (
                f"Request {i + 1}/5 expected 2xx, got {resp.status_code}"
            )

        # 6th request → rate limited
        resp = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 429, f"Expected 429 (rate limited), got {resp.status_code}"


class TestAuthRateLimitersAreIndependent:
    """Register and login have separate rate limit buckets.

    Uses object-identity checks (not HTTP requests) to avoid cross-test
    pollution from module-level singleton state.
    """

    def test_register_and_login_use_separate_limiter_instances(self) -> None:
        """``_REGISTER_LIMITER`` and ``_LOGIN_LIMITER`` are distinct objects
        with their own backing ``Limiter`` — changes to one do not affect
        the other."""
        from narrare.auth.router import _LOGIN_LIMITER, _REGISTER_LIMITER

        assert _REGISTER_LIMITER is not _LOGIN_LIMITER, "Must be separate _RateLimiterDep instances"
        assert _REGISTER_LIMITER.limiter is not _LOGIN_LIMITER.limiter, (
            "Each must have its own pyrate Limiter"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_auth_service() -> AsyncMock:
    """Create a mocked AuthService that returns valid TokenResponse values.

    Uses ``AsyncMock`` so ``await service.register()`` works.
    Returns actual ``TokenResponse`` objects so FastAPI's
    ``response_model`` serialisation does not choke on bare mocks.
    """
    mock = AsyncMock()

    mock.register = AsyncMock(
        return_value=TokenResponse(
            access_token="test-access",
            refresh_token="test-refresh",
            token_type="bearer",
            expires_in=3600,
        ),
    )
    mock.login = AsyncMock(
        return_value=TokenResponse(
            access_token="test-access",
            refresh_token="test-refresh",
            token_type="bearer",
            expires_in=3600,
        ),
    )
    return mock
