"""Unit tests for ``narrare._app.rate_limits``.

Tests the module-level ``RateLimiter`` instances used as FastAPI dependencies.

Architecture decision AR-05-02:
    Uses in-memory ``pyrate_limiter``, NOT Redis. The ``RateLimiter``
    instances are created at module level so the same ``Limiter`` is
    shared across all requests — otherwise rate limits would never
    accumulate.

NOTE on pyrate_limiter 4.x:
    ``Limiter.try_acquire`` defaults to ``blocking=True`` — when a rate
    limit is exceeded the caller is blocked for the rate window duration.
    All direct ``Limiter`` tests use ``blocking=False`` to avoid timeouts.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.rate_limiter_dep import RateLimiter as _RateLimiterDep
from narrare._app.rate_limits import (
    AI_ANALYSIS_LIMITER,
    AI_LIGHT_LIMITER,
    AI_WRITE_LIMITER,
    AI_WS_LIMITER,
    SETUP_MODELS_LIMITER,
)

# Fresh limiters for per-test isolation — avoids test pollution from
# using the module-level singletons across multiple tests.
_SHORT_WINDOW = Duration.SECOND * 10


# ---------------------------------------------------------------------------
# Type-check tests — verify correct types (module-level constants)
# ---------------------------------------------------------------------------


class TestTypes:
    """Each module-level constant has the correct type."""

    def test_ai_write_limiter_is_rate_limiter_dep(self) -> None:
        assert isinstance(AI_WRITE_LIMITER, _RateLimiterDep)

    def test_ai_analysis_limiter_is_rate_limiter_dep(self) -> None:
        assert isinstance(AI_ANALYSIS_LIMITER, _RateLimiterDep)

    def test_ai_light_limiter_is_rate_limiter_dep(self) -> None:
        assert isinstance(AI_LIGHT_LIMITER, _RateLimiterDep)

    def test_setup_models_limiter_is_rate_limiter_dep(self) -> None:
        assert isinstance(SETUP_MODELS_LIMITER, _RateLimiterDep)

    def test_ai_ws_limiter_is_raw_limiter(self) -> None:
        assert isinstance(AI_WS_LIMITER, Limiter)


# ---------------------------------------------------------------------------
# FastAPI integration test — verifies 429 response from the dependency
# Uses per-test-factory limiters to avoid test isolation issues.
# ---------------------------------------------------------------------------


def _make_app(
    write_rate: int = 3,
    analysis_rate: int = 5,
    light_rate: int = 10,
) -> FastAPI:
    """Create a FastAPI app with rate-limited routes using fresh limiters.

    Each call creates independent ``Limiter`` instances so tests don't
    pollute each other.
    """
    _write_limiter = _RateLimiterDep(Limiter(Rate(write_rate, _SHORT_WINDOW)))
    _analysis_limiter = _RateLimiterDep(Limiter(Rate(analysis_rate, _SHORT_WINDOW)))
    _light_limiter = _RateLimiterDep(Limiter(Rate(light_rate, _SHORT_WINDOW)))

    _app = FastAPI()

    @_app.get("/write", dependencies=[Depends(_write_limiter)])
    async def _write() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @_app.get("/analysis", dependencies=[Depends(_analysis_limiter)])
    async def _analysis() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @_app.get("/light", dependencies=[Depends(_light_limiter)])
    async def _light() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    return _app


class TestWriteLimiter:
    """3 requests per window — writing endpoints."""

    def test_allows_first_three(self) -> None:
        with TestClient(_make_app(write_rate=3)) as client:
            for _ in range(3):
                resp = client.get("/write")
                assert resp.status_code == 200

    def test_rejects_fourth(self) -> None:
        with TestClient(_make_app(write_rate=3)) as client:
            for _ in range(3):
                client.get("/write")
            resp = client.get("/write")
            assert resp.status_code == 429


class TestAnalysisLimiter:
    """5 requests per window — analysis/chat/KB endpoints."""

    def test_allows_first_five(self) -> None:
        with TestClient(_make_app(analysis_rate=5)) as client:
            for _ in range(5):
                resp = client.get("/analysis")
                assert resp.status_code == 200

    def test_rejects_sixth(self) -> None:
        with TestClient(_make_app(analysis_rate=5)) as client:
            for _ in range(5):
                client.get("/analysis")
            resp = client.get("/analysis")
            assert resp.status_code == 429


class TestLightLimiter:
    """10 requests per window — name generation."""

    def test_allows_first_ten(self) -> None:
        with TestClient(_make_app(light_rate=10)) as client:
            for _ in range(10):
                resp = client.get("/light")
                assert resp.status_code == 200

    def test_rejects_eleventh(self) -> None:
        with TestClient(_make_app(light_rate=10)) as client:
            for _ in range(10):
                client.get("/light")
            resp = client.get("/light")
            assert resp.status_code == 429


class TestLimiterIndependence:
    """Each endpoint has its own rate-limit bucket."""

    def test_write_and_analysis_are_independent(self) -> None:
        app = _make_app(write_rate=3, analysis_rate=5)
        with TestClient(app) as client:
            # Exhaust write
            for _ in range(3):
                client.get("/write")
            assert client.get("/write").status_code == 429

            # Analysis should still work
            for i in range(5):
                resp = client.get("/analysis")
                assert resp.status_code == 200, (
                    f"Analysis request {i + 1} expected 200, got {resp.status_code}"
                )


# ---------------------------------------------------------------------------
# WebSocket limiter — raw pyrate_limiter.Limiter
# ---------------------------------------------------------------------------


class TestWebSocketLimiter:
    """AI_WS_LIMITER is a raw Limiter used inline in WebSocket handlers."""

    def test_rejects_after_three(self) -> None:
        limiter = Limiter(Rate(3, _SHORT_WINDOW))
        key = "ws:writing:user-1:chapter-a"
        for _ in range(3):
            assert limiter.try_acquire(key, blocking=False) is True
        assert limiter.try_acquire(key, blocking=False) is False

    def test_module_level_limiter_is_limiter(self) -> None:
        assert isinstance(AI_WS_LIMITER, Limiter)
