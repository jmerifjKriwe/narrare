"""Unit tests for ``narrare._app.rate_limits``.

Tests the module-level ``RateLimiter`` instances used as FastAPI dependencies,
plus the operator-configurable governed-default resolver.

Architecture decision AR-05-02:
    Uses in-memory ``pyrate_limiter``, NOT Redis. The ``RateLimiter``
    instances are created at module level so the same ``Limiter`` is
    shared across all requests — otherwise rate limits would never
    accumulate.

Operator configuration (governed defaults, ADR-060 pattern):
    Each limiter's request count is operator-configurable via a
    ``NARRARE_RATE_LIMIT_*`` env var resolved once at import by
    :func:`_resolve_rate_limit_count`. The resolver is unit-tested directly
    (see :class:`TestResolveRateLimitCount`), the defaults are pinned
    (:class:`TestGovernedDefaults`), and the end-to-end env→limiter wiring is
    proven behaviorally (:class:`TestOperatorOverrideWiring`).

NOTE on pyrate_limiter 4.x:
    ``Limiter.try_acquire`` defaults to ``blocking=True`` — when a rate
    limit is exceeded the caller is blocked for the rate window duration.
    All direct ``Limiter`` tests use ``blocking=False`` to avoid timeouts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.rate_limiter_dep import RateLimiter as _RateLimiterDep

if TYPE_CHECKING:
    import pytest
from narrare._app.rate_limits import (
    AI_ANALYSIS_LIMITER,
    AI_LIGHT_LIMITER,
    AI_PROMPT_LIVE_TEST_LIMITER,
    AI_WRITE_LIMITER,
    AI_WS_LIMITER,
    LONG_WINDOW_MS,
    RATE_LIMIT_ANALYSIS_DEFAULT,
    RATE_LIMIT_LIGHT_DEFAULT,
    RATE_LIMIT_PROMPT_LIVE_TEST_DEFAULT,
    RATE_LIMIT_SETUP_MODELS_DEFAULT,
    RATE_LIMIT_WRITE_DEFAULT,
    RATE_LIMIT_WS_DEFAULT,
    RATE_LIMIT_WS_ENV_VAR,
    SETUP_MODELS_LIMITER,
    _resolve_rate_limit_count,  # pyright: ignore[reportPrivateUsage]
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

    def test_ai_prompt_live_test_limiter_is_rate_limiter_dep(self) -> None:
        assert isinstance(AI_PROMPT_LIVE_TEST_LIMITER, _RateLimiterDep)

    def test_ai_ws_limiter_is_raw_limiter(self) -> None:
        assert isinstance(AI_WS_LIMITER, Limiter)


# ---------------------------------------------------------------------------
# Governed-default resolver — operator-configurable count (ADR-060 pattern)
# ---------------------------------------------------------------------------


class TestResolveRateLimitCount:
    """``_resolve_rate_limit_count`` — single operator-scoped value.

    Mirrors ``TestTransportRetryGovernedSource`` in
    ``tests/unit/core/llm/test_transport_retry.py``. A sentinel default
    (``7``) distinct from every real default proves the fallback returns the
    *passed* default rather than any hardcoded value. The structured warning
    emitted on invalid input is verified by code inspection + RULE-11
    enforcement (no silent failures); these tests assert the observable
    fallback value, matching the established transport-retry test pattern.
    """

    _ENV = "NARRARE_TEST_RATE_LIMIT_RESOLVER"
    _DEFAULT = 7  # sentinel distinct from all real defaults (3/5/10)

    def test_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(self._ENV, raising=False)
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == self._DEFAULT

    def test_default_when_env_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(self._ENV, "")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == self._DEFAULT

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(self._ENV, "42")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == 42

    def test_one_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """1 is the minimum accepted count (0 would block every request)."""
        monkeypatch.setenv(self._ENV, "1")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == 1

    def test_invalid_int_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(self._ENV, "not-an-int")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == self._DEFAULT

    def test_below_minimum_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """0 is the kill-switch footgun — rejected, not honoured."""
        monkeypatch.setenv(self._ENV, "0")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == self._DEFAULT

    def test_negative_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(self._ENV, "-3")
        assert _resolve_rate_limit_count(self._ENV, self._DEFAULT) == self._DEFAULT


class TestGovernedDefaults:
    """Pin the governed defaults — accidental change fails the build.

    These are the RULE-18b regression guards: the values that were previously
    hardcoded are now exposed as governed defaults and must not silently
    change. Self-hosters / managed-hosting profiles rely on these as the
    documented baseline.
    """

    def test_write_default_is_three(self) -> None:
        assert RATE_LIMIT_WRITE_DEFAULT == 3

    def test_analysis_default_is_five(self) -> None:
        assert RATE_LIMIT_ANALYSIS_DEFAULT == 5

    def test_light_default_is_ten(self) -> None:
        assert RATE_LIMIT_LIGHT_DEFAULT == 10

    def test_setup_models_default_is_ten(self) -> None:
        assert RATE_LIMIT_SETUP_MODELS_DEFAULT == 10

    def test_prompt_live_test_default_is_five(self) -> None:
        assert RATE_LIMIT_PROMPT_LIVE_TEST_DEFAULT == 5

    def test_ws_default_is_three(self) -> None:
        assert RATE_LIMIT_WS_DEFAULT == 3


class TestOperatorOverrideWiring:
    """The operator env var provably reaches the limiter's effective rate.

    This is the RULE-18b effect test for rate-limit governed defaults
    (analogous to ``TestTransportRetryBehavioralEffect`` for transport retry):
    changing the operator env var changes the *observable* acquire limit. The
    limiter's real enforcement runs (``try_acquire``); only the config source
    is varied.

    Non-global-mutating design (test isolation, RULE-11/testing-standards):
        The module-level limiters read the env exactly once at import
        (restart-to-apply semantics). Reloading the module to re-run those
        statements would REPLACE the singletons with brand-new objects, which
        pollutes every importer that captured the ORIGINAL singleton at its own
        import time — e.g. ``router_voice_check.py`` captured
        ``AI_ANALYSIS_LIMITER`` via ``from ... import``, so a reload would
        leave the router holding a stale object while the module attribute
        points elsewhere (order-dependent test-isolation bug).

        Instead, this test exercises the IDENTICAL production code path that
        the module-level singletons use — ``_resolve_rate_limit_count`` →
        ``Rate(count, LONG_WINDOW_MS)`` → ``Limiter`` — on a LOCAL limiter
        built from a monkeypatched env. The env override provably changes the
        effective acquire count without touching any module-level singleton.
        ``monkeypatch`` auto-reverts the env at test exit, so no other test is
        affected.
    """

    def test_env_override_changes_effective_rate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Env override of 2 → resolver returns 2 ...
        monkeypatch.setenv(RATE_LIMIT_WS_ENV_VAR, "2")
        count = _resolve_rate_limit_count(RATE_LIMIT_WS_ENV_VAR, RATE_LIMIT_WS_DEFAULT)
        assert count == 2
        # ... and a limiter built from that count admits 2, rejects the 3rd.
        local_limiter = Limiter(Rate(count, LONG_WINDOW_MS))
        key = "test:operator-override-wiring:ws"
        assert local_limiter.try_acquire(key, blocking=False) is True
        assert local_limiter.try_acquire(key, blocking=False) is True
        # 3rd request in the window is rejected — the count came from the
        # env (=2), not the default (=3).
        assert local_limiter.try_acquire(key, blocking=False) is False
        # Default path (env unset) still resolves to the governed default.
        monkeypatch.delenv(RATE_LIMIT_WS_ENV_VAR, raising=False)
        assert (
            _resolve_rate_limit_count(RATE_LIMIT_WS_ENV_VAR, RATE_LIMIT_WS_DEFAULT)
            == RATE_LIMIT_WS_DEFAULT
        )


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
