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

Operator configuration (governed defaults):
    The request **count** of every limiter below is operator-configurable
    via a dedicated ``NARRARE_RATE_LIMIT_*`` environment variable, following
    the governed-default pattern established by ADR-060 (LLM transport
    retry — see ``packages/core/narrare_core/llm/_transport_retry.py``).

    * **Governed default:** each ``RATE_LIMIT_*_DEFAULT`` constant. These
      match the previously hardcoded counts; an accidental change is caught
      by ``tests/unit/api/_app/test_rate_limits.py`` (RULE-18b).
    * **Operator override:** the matching ``NARRARE_RATE_LIMIT_*`` env var.
      Self-hosters / managed-hosting profiles may raise or lower the count;
      **users may not** — there is no DB/UI surface.
    * **Restart to apply:** limiters are constructed ONCE at import time
      (see "module-level instances" above), so each env var is read exactly
      once via :func:`_resolve_rate_limit_count`. Change the env, restart
      the API — consistent with transport-retry being resolved at provider
      construction.
    * **Window is fixed:** only the count is configurable. The window stays
      :data:`LONG_WINDOW_MS` (1 minute). Making the window configurable is
      out of scope and intentionally not offered.
    * **Invalid values are rejected, not ignored (RULE-11):** a non-integer
      or a value below :data:`RATE_LIMIT_MIN_COUNT` emits a structured
      warning and falls back to the governed default. A count of 0 would
      block every request and is not a supported kill-switch.

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

import os
from typing import Final

import structlog
from pyrate_limiter import Duration, Limiter, Rate

from narrare._app.rate_limiter_dep import RateLimiter as _RateLimiterDep

logger = structlog.get_logger(__name__)

LONG_WINDOW_MS = Duration.MINUTE * 1

#: Minimum accepted rate-limit count. ``0`` would block every request and is
#: not a supported kill-switch; values below this fall back to the default.
RATE_LIMIT_MIN_COUNT: Final[int] = 1


def _resolve_rate_limit_count(env_var: str, default: int) -> int:
    """Resolve an operator-configurable rate-limit request count.

    Reads ``env_var``; falls back to ``default`` when the variable is unset,
    empty, non-integer, or below :data:`RATE_LIMIT_MIN_COUNT`. Invalid values
    emit a structured warning (RULE-11: no silent failures), mirroring
    ``narrare_core.llm._transport_retry.get_transport_max_retries``.

    Args:
        env_var: The operator override environment variable name.
        default: The governed default count (used on any invalid/missing value).

    Returns:
        The resolved request count (``>= RATE_LIMIT_MIN_COUNT``).
    """
    raw = os.environ.get(env_var)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "rate_limit_invalid_env",
            env_var=env_var,
            value=raw,
            fallback=default,
        )
        return default
    if value < RATE_LIMIT_MIN_COUNT:
        logger.warning(
            "rate_limit_below_minimum",
            env_var=env_var,
            value=value,
            minimum=RATE_LIMIT_MIN_COUNT,
            fallback=default,
        )
        return default
    return value


# -- Module-level RateLimiter instances (shared across requests) ------------

# AI writing endpoints.
RATE_LIMIT_WRITE_DEFAULT: Final[int] = 3
RATE_LIMIT_WRITE_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_WRITE"

AI_WRITE_LIMITER = _RateLimiterDep(
    Limiter(
        Rate(
            _resolve_rate_limit_count(
                RATE_LIMIT_WRITE_ENV_VAR,
                RATE_LIMIT_WRITE_DEFAULT,
            ),
            LONG_WINDOW_MS,
        ),
    ),
)
"""Per-user rate limit for AI writing endpoints — 3 requests/minute.

Applies to: write (generate), extend, rewrite, co-author, suggest.
Override count via :data:`RATE_LIMIT_WRITE_ENV_VAR` (restart to apply).
"""

# AI analysis / chat / KB endpoints.
RATE_LIMIT_ANALYSIS_DEFAULT: Final[int] = 5
RATE_LIMIT_ANALYSIS_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_ANALYSIS"

AI_ANALYSIS_LIMITER = _RateLimiterDep(
    Limiter(
        Rate(
            _resolve_rate_limit_count(
                RATE_LIMIT_ANALYSIS_ENV_VAR,
                RATE_LIMIT_ANALYSIS_DEFAULT,
            ),
            LONG_WINDOW_MS,
        ),
    ),
)
"""Per-user rate limit for AI analysis/chat endpoints — 5 requests/minute.

Applies to: chat, consistency checks, beta-reader, POV analysis,
readability analysis, timeline extraction, KB extraction/improve/sessions.
Override count via :data:`RATE_LIMIT_ANALYSIS_ENV_VAR` (restart to apply).
"""

# Lightweight AI endpoints.
RATE_LIMIT_LIGHT_DEFAULT: Final[int] = 10
RATE_LIMIT_LIGHT_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_LIGHT"

AI_LIGHT_LIMITER = _RateLimiterDep(
    Limiter(
        Rate(
            _resolve_rate_limit_count(
                RATE_LIMIT_LIGHT_ENV_VAR,
                RATE_LIMIT_LIGHT_DEFAULT,
            ),
            LONG_WINDOW_MS,
        ),
    ),
)
"""Per-user rate limit for lightweight AI endpoints — 10 requests/minute.

Applies to: name generation.
Override count via :data:`RATE_LIMIT_LIGHT_ENV_VAR` (restart to apply).
"""

# Unauthenticated provider model discovery.
RATE_LIMIT_SETUP_MODELS_DEFAULT: Final[int] = 10
RATE_LIMIT_SETUP_MODELS_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_SETUP_MODELS"

SETUP_MODELS_LIMITER = _RateLimiterDep(
    Limiter(
        Rate(
            _resolve_rate_limit_count(
                RATE_LIMIT_SETUP_MODELS_ENV_VAR,
                RATE_LIMIT_SETUP_MODELS_DEFAULT,
            ),
            LONG_WINDOW_MS,
        ),
    ),
)
"""IP-based rate limit for unauthenticated provider model discovery — 10
requests/minute.

Applies to: ``GET /setup/providers/{provider}/models`` (no auth).
The default ``RateLimiter`` key is client IP, which is the correct
behaviour for unauthenticated endpoints.
Override count via :data:`RATE_LIMIT_SETUP_MODELS_ENV_VAR` (restart to apply).
"""

# Prompt live test.
RATE_LIMIT_PROMPT_LIVE_TEST_DEFAULT: Final[int] = 5
RATE_LIMIT_PROMPT_LIVE_TEST_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_PROMPT_LIVE_TEST"

AI_PROMPT_LIVE_TEST_LIMITER = _RateLimiterDep(
    Limiter(
        Rate(
            _resolve_rate_limit_count(
                RATE_LIMIT_PROMPT_LIVE_TEST_ENV_VAR,
                RATE_LIMIT_PROMPT_LIVE_TEST_DEFAULT,
            ),
            LONG_WINDOW_MS,
        ),
    ),
)
"""Per-user rate limit for PROMPT-003 prompt live test — 5 requests/minute.

Applies to: ``POST /api/v1/prompts/{prompt_id:path}/live-test``.
Matches the CR-07 v3 §B.1 spec cap of 5/min for the optional live test.
Override count via :data:`RATE_LIMIT_PROMPT_LIVE_TEST_ENV_VAR` (restart to apply).
"""


# -- WebSocket limiter (raw pyrate_limiter, not FastAPI Dep) ----------------

RATE_LIMIT_WS_DEFAULT: Final[int] = 3
RATE_LIMIT_WS_ENV_VAR: Final[str] = "NARRARE_RATE_LIMIT_WS"

AI_WS_LIMITER = Limiter(
    Rate(
        _resolve_rate_limit_count(
            RATE_LIMIT_WS_ENV_VAR,
            RATE_LIMIT_WS_DEFAULT,
        ),
        LONG_WINDOW_MS,
    ),
)
"""Rate limiter for WebSocket writing sessions — 3 requests/minute.

Returns a raw :class:`pyrate_limiter.Limiter` (not a FastAPI dependency)
because it is used directly inside WebSocket handlers (a ``RateLimiter`` dep
cannot be injected into a WebSocket receive loop).

Override count via :data:`RATE_LIMIT_WS_ENV_VAR` (restart to apply).

Usage inside a WebSocket handler::

    if not AI_WS_LIMITER.try_acquire(ws_key, blocking=False):
        await websocket.send_json({"type": "error", "message": "Rate limited"})
        await websocket.close(code=4003, reason="Rate limited")
        return
"""
