"""Rate-limit dependency factories for API endpoints.

Follows the pattern established in ``auth/router.py``::

    dependencies=[Depends(rate_limiter)]

Each constant is a module-level :class:`_RateLimiterDep` wrapping a
:class:`pyrate_limiter.Limiter` with the configured rate.

IMPORTANT — module-level instances vs factory functions:
    ``RateLimiter`` must be a SINGLE instance shared across all requests
    so the ``Limiter`` can accumulate state.  A factory function returns
    a new ``Limiter`` per request — rate limits would never be enforced.

    ❌ Broken::

        def my_limiter() -> _RateLimiterDep:
            return _RateLimiterDep(Limiter(Rate(...)))
        # Depends(my_limiter) → new Limiter per request → no rate limit

    ✅ Correct (module-level instance)::

        MY_LIMITER = _RateLimiterDep(Limiter(Rate(...)))
        # Depends(MY_LIMITER) → same Limiter across requests → works!

Architecture decision AR-05-02:
    Uses **in-memory ``pyrate_limiter``** (same as auth), NOT Redis.
    This is the accepted risk — functional for single-instance, revisit if
    multi-instance deployment is pursued.

Per-user vs per-IP:
    The default rate-limit key is client IP (see ``RateLimiter._identifier``
    in ``rate_limiter_dep.py``). Given this is local-first single-user,
    IP-based is functionally equivalent to per-user. The
    ``GET /setup/providers/{p}/models`` endpoint has no authentication and
    uses IP-based rate limiting (default behavior).

    Note: with the default in-memory ``Limiter(Rate(...))`` (single shared
    bucket), the key is informational — isolation between endpoint groups
    comes from using separate ``RateLimiter`` instances (below), not the key.
"""

from __future__ import annotations

from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.rate_limiter_dep import RateLimiter as _RateLimiterDep

LONG_WINDOW_MS = Duration.MINUTE * 1

# -- Module-level RateLimiter instances (shared across requests) ------------


AI_WRITE_LIMITER = _RateLimiterDep(Limiter(Rate(3, LONG_WINDOW_MS)))
"""Per-user rate limit for AI writing endpoints — 3 requests/minute.

Applies to: write (generate), extend, rewrite, co-author, suggest.
"""

AI_ANALYSIS_LIMITER = _RateLimiterDep(Limiter(Rate(5, LONG_WINDOW_MS)))
"""Per-user rate limit for AI analysis/chat endpoints — 5 requests/minute.

Applies to: chat, consistency checks, beta-reader, POV analysis,
readability analysis, timeline extraction, KB extraction/improve/sessions.
"""

AI_LIGHT_LIMITER = _RateLimiterDep(Limiter(Rate(10, LONG_WINDOW_MS)))
"""Per-user rate limit for lightweight AI endpoints — 10 requests/minute.

Applies to: name generation.
"""

SETUP_MODELS_LIMITER = _RateLimiterDep(Limiter(Rate(10, LONG_WINDOW_MS)))
"""IP-based rate limit for unauthenticated provider model discovery — 10
requests/minute.

Applies to: ``GET /setup/providers/{provider}/models`` (no auth).
The default ``RateLimiter`` key is client IP, which is the correct
behaviour for unauthenticated endpoints.
"""

AI_PROMPT_LIVE_TEST_LIMITER = _RateLimiterDep(Limiter(Rate(5, LONG_WINDOW_MS)))
"""Per-user rate limit for PROMPT-003 prompt live test — 5 requests/minute.

Applies to: ``POST /api/v1/prompts/{prompt_id:path}/live-test``.
Matches the CR-07 v3 §B.1 spec cap of 5/min for the optional live test.
"""


# -- WebSocket limiter (raw pyrate_limiter, not FastAPI Dep) ----------------

AI_WS_LIMITER = Limiter(Rate(3, LONG_WINDOW_MS))
"""Rate limiter for WebSocket writing sessions — 3 requests/minute.

Returns a raw :class:`pyrate_limiter.Limiter` (not a FastAPI dependency)
because it is used directly inside WebSocket handlers (a ``RateLimiter`` dep
cannot be injected into a WebSocket receive loop).

Usage inside a WebSocket handler::

    if not AI_WS_LIMITER.try_acquire(ws_key, blocking=False):
        await websocket.send_json({"type": "error", "message": "Rate limited"})
        await websocket.close(code=4003, reason="Rate limited")
        return
"""
