"""Regression tests for the custom ``RateLimiter`` FastAPI dependency.

Background — why this file exists:
    ``fastapi_limiter`` 0.2.0 is incompatible with FastAPI 0.116+. Its
    ``RateLimiter.__call__`` iterates over ``request.app.routes`` and reads
    ``route.path`` on every entry. FastAPI 0.116+ inserts
    ``_IncludedRouter`` objects (from ``app.include_router``) into that list,
    which have no ``.path`` attribute → ``AttributeError`` → the generic
    exception handler converts it to HTTP 500. Every rate-limited endpoint in
    CI failed with ``Registration failed: 500`` (25 e2e failures).

    The local dev server only worked because it was a stale process started
    before the FastAPI upgrade; CI starts fresh → always 500.

Fix:
    ``narrare._app.rate_limiter_dep.RateLimiter`` is a drop-in replacement
    built directly on ``pyrate_limiter`` (already used by ``AI_WS_LIMITER``
    for WebSockets). It derives the rate-limit key from ``request.url.path``
    and never iterates ``request.app.routes``.

These tests are intentionally PURE UNIT tests (no DB, no auth, no LLM) so they
isolate the rate-limiter dependency and run in milliseconds. They reproduce the
exact failure condition — an app whose ``request.app.routes`` contains a
``_IncludedRouter`` — which is what triggered the 500s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.rate_limiter_dep import RateLimiter

if TYPE_CHECKING:
    from starlette.requests import Request
# Short window so exhausted-limit tests reset quickly between tests. Each test
# builds its own Limiter to avoid cross-test state accumulation (same pattern
# as ``test_rate_limits.py``).
_SHORT_WINDOW = Duration.SECOND * 5


def _make_included_router_app(rate_limit: int = 3) -> FastAPI:
    """Build a FastAPI app whose routes contain a ``_IncludedRouter``.

    This is the exact shape that broke ``fastapi_limiter``: a sub-router is
    registered via ``app.include_router`` (with a prefix), so
    ``request.app.routes`` contains a ``_IncludedRouter`` object in addition
    to plain ``Route`` objects. The endpoint is guarded by our custom
    ``RateLimiter``.
    """
    limiter = RateLimiter(Limiter(Rate(rate_limit, _SHORT_WINDOW)))

    app = FastAPI()
    sub = _new_subrouter()

    @sub.get("/ping", dependencies=[Depends(limiter)])
    async def _ping() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    app.include_router(sub)
    return app


def _new_subrouter() -> APIRouter:
    """Return a fresh prefixed ``APIRouter`` (produces a ``_IncludedRouter``)."""
    return APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Regression: the original 500 bug
# ---------------------------------------------------------------------------


class TestIncludedRouterCompatibility:
    """The custom RateLimiter must work when ``app.routes`` has ``_IncludedRouter``.

    With the OLD ``fastapi_limiter`` these requests returned HTTP 500
    (``AttributeError: '_IncludedRouter' object has no attribute 'path'``).
    The custom dependency must NOT raise and must return 200.
    """

    def test_rate_limited_request_is_not_500(self) -> None:
        """Rate-limited request to an included-router route returns 200, not 500."""
        app = _make_included_router_app(rate_limit=3)
        with TestClient(app) as client:
            resp = client.get("/api/v1/ping")

        assert resp.status_code == 200, (
            f"Expected 200 (regression: was 500 with fastapi_limiter), "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_request_routes_actually_contain_included_router(self) -> None:
        """Guard: confirm the test scenario really triggers the bug condition.

        If a future FastAPI version stops putting ``_IncludedRouter`` into
        ``app.routes``, ``test_rate_limited_request_is_not_500`` would become
        vacuous. This test fails loudly in that case so the regression
        coverage stays meaningful.
        """
        app = _make_included_router_app()
        route_type_names = {type(r).__name__ for r in app.routes}
        assert "_IncludedRouter" in route_type_names, (
            f"Expected _IncludedRouter in app.routes to exercise the bug; "
            f"found types: {sorted(route_type_names)}"
        )


# ---------------------------------------------------------------------------
# Behavioural correctness: 429 enforcement
# ---------------------------------------------------------------------------


class TestRateLimitEnforcement:
    """The custom dependency must still enforce limits (return 429 when exceeded)."""

    def test_allows_requests_up_to_limit(self) -> None:
        app = _make_included_router_app(rate_limit=3)
        with TestClient(app) as client:
            for _ in range(3):
                resp = client.get("/api/v1/ping")
                assert resp.status_code == 200

    def test_rejects_request_over_limit_with_429(self) -> None:
        app = _make_included_router_app(rate_limit=3)
        with TestClient(app) as client:
            for _ in range(3):
                client.get("/api/v1/ping")
            resp = client.get("/api/v1/ping")
        assert resp.status_code == 429, (
            f"Expected 429 after exceeding limit, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Identifier: per-instance isolation + custom key support
# ---------------------------------------------------------------------------


class TestIdentifier:
    """Isolation is per ``RateLimiter`` instance; custom callbacks are invoked.

    Note on pyrate_limiter 4.x semantics:
        ``Limiter(Rate(...))`` creates a **single shared bucket**
        (``SingleBucketFactory.get`` ignores the ``name`` argument). Therefore
        rate-limit isolation in this codebase is achieved by using **separate
        ``RateLimiter`` instances** (each wrapping its own ``Limiter``) per
        endpoint group — see ``rate_limits.py``. The bucket key passed to
        ``try_acquire_async`` is informational (useful for logging / a future
        multi-bucket or Redis backend) but does not isolate within a single
        ``Limiter`` instance.
    """

    def test_separate_instances_have_independent_buckets(self) -> None:
        """Two ``RateLimiter`` instances wrap independent buckets.

        This mirrors the codebase design (``AI_WRITE_LIMITER`` vs
        ``AI_ANALYSIS_LIMITER`` etc.): each concern gets its own instance.
        """
        limiter_a = RateLimiter(Limiter(Rate(2, _SHORT_WINDOW)))
        limiter_b = RateLimiter(Limiter(Rate(2, _SHORT_WINDOW)))
        app = FastAPI()
        sub = _new_subrouter()

        @sub.get("/a", dependencies=[Depends(limiter_a)])
        async def _a() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"path": "a"}

        @sub.get("/b", dependencies=[Depends(limiter_b)])
        async def _b() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"path": "b"}

        app.include_router(sub)
        with TestClient(app) as client:
            # Exhaust instance A's bucket (2 requests)
            assert client.get("/api/v1/a").status_code == 200
            assert client.get("/api/v1/a").status_code == 200
            assert client.get("/api/v1/a").status_code == 429
            # Instance B is a separate bucket — still allowed
            assert client.get("/api/v1/b").status_code == 200

    def test_custom_identifier_callback_is_used(self) -> None:
        """A custom identifier callback overrides the default IP+path key."""
        calls: list[str] = []

        def _by_user(_request: Request) -> str:
            key = "user-42"
            calls.append(key)
            return key

        limiter = RateLimiter(
            Limiter(Rate(1, _SHORT_WINDOW)),
            identifier=_by_user,
        )
        app = FastAPI()
        sub = _new_subrouter()

        @sub.get("/x", dependencies=[Depends(limiter)])
        async def _x() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
            return {"ok": True}

        app.include_router(sub)
        with TestClient(app) as client:
            assert client.get("/api/v1/x").status_code == 200
            assert client.get("/api/v1/x").status_code == 429
        assert calls == ["user-42", "user-42"], f"custom identifier not used: {calls}"

    def test_async_custom_identifier_is_awaited(self) -> None:
        """An async identifier callback must be awaited.

        A non-awaited coroutine would be truthy → the limiter would treat
        every request as the same non-string key and behave incorrectly.
        This test passes only if the async callback is properly awaited and
        its returned string used as the bucket key (so the second request
        is rejected with 429).
        """

        async def _async_id(_request: Request) -> str:
            return "async-key"

        limiter = RateLimiter(
            Limiter(Rate(1, _SHORT_WINDOW)),
            identifier=_async_id,  # type: ignore[arg-type]
        )
        app = FastAPI()
        sub = _new_subrouter()

        @sub.get("/y", dependencies=[Depends(limiter)])
        async def _y() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
            return {"ok": True}

        app.include_router(sub)
        with TestClient(app) as client:
            first = client.get("/api/v1/y")
            second = client.get("/api/v1/y")
        assert first.status_code == 200
        assert second.status_code == 429


# ---------------------------------------------------------------------------
# Default identifier key derivation (X-Forwarded-For / loopback fallback)
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeURL:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeRequest:
    """Minimal request stand-in for the default identifier (pure unit test).

    Only the attributes ``_identifier`` reads are implemented: ``headers``
    (``.get``), ``client`` (``.host`` or ``None``), and ``url.path``.
    """

    def __init__(self, *, forwarded_for: str | None, client: _FakeClient | None) -> None:
        headers: dict[str, str] = {}
        if forwarded_for is not None:
            headers["X-Forwarded-For"] = forwarded_for
        self.headers = headers
        self.client = client
        self.url = _FakeURL("/api/v1/ping")


class TestIdentifierKeyDerivation:
    """The default identifier derives the bucket key from request IP + path."""

    async def test_x_forwarded_for_first_hop_is_used(self) -> None:
        """When present, the first X-Forwarded-For hop is the client IP."""
        limiter = RateLimiter(Limiter(Rate(1, _SHORT_WINDOW)))
        request = _FakeRequest(
            forwarded_for="203.0.113.1, 198.51.100.2", client=_FakeClient("ignored")
        )
        assert await limiter._identifier(cast("Request", request)) == "203.0.113.1:/api/v1/ping"

    async def test_no_client_falls_back_to_loopback(self) -> None:
        """No X-Forwarded-For and no client -> 127.0.0.1 loopback fallback."""
        limiter = RateLimiter(Limiter(Rate(1, _SHORT_WINDOW)))
        request = _FakeRequest(forwarded_for=None, client=None)
        assert await limiter._identifier(cast("Request", request)) == "127.0.0.1:/api/v1/ping"
