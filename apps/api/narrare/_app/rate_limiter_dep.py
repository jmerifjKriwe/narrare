"""Custom FastAPI rate-limiter dependency using ``pyrate_limiter`` directly.

Replaces ``fastapi_limiter.depends.RateLimiter``, which is incompatible with
FastAPI 0.116+: its ``__call__`` iterates ``request.app.routes`` and reads
``route.path`` on every entry, but FastAPI 0.116+ inserts ``_IncludedRouter``
objects (from ``app.include_router``) into that list which have no ``.path``
attribute → ``AttributeError`` → HTTP 500 on every rate-limited route.

This module is a drop-in replacement with the same constructor signature and
call protocol. It derives the rate-limit key from the request identity and
``request.url.path`` and never iterates ``request.app.routes``.

It mirrors the pattern already used for WebSocket rate limiting
(``AI_WS_LIMITER`` in ``rate_limits.py``), which has used a raw
``pyrate_limiter.Limiter`` directly since AR-05-02 (in-memory, no Redis).

See ``rate_limits.py`` for the module-level limiter instances.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Response, status

from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pyrate_limiter import Limiter

Identifier = Callable[[Request], str | Awaitable[str]]
"""Callable that derives the rate-limit bucket key from a request.

May be synchronous (returning ``str``) or asynchronous (returning an
awaitable ``str``). Async callables are awaited automatically.
"""


class RateLimiter:
    """FastAPI dependency for rate limiting using ``pyrate_limiter``.

    Drop-in replacement for ``fastapi_limiter.depends.RateLimiter``.

    Usage::

        from pyrate_limiter import Duration, Limiter, Rate
        MY_LIMITER = RateLimiter(Limiter(Rate(3, Duration.MINUTE)))

        @router.post("/endpoint", dependencies=[Depends(MY_LIMITER)])
        async def my_endpoint(): ...

    The limiter instance MUST be module-level (shared across requests) so
    rate-limit state accumulates. A factory function would create a new
    ``Limiter`` per request — rate limits would never trigger. See
    ``rate_limits.py`` for the established module-level pattern.
    """

    def __init__(
        self,
        limiter: Limiter,
        identifier: Identifier | None = None,
        blocking: bool = False,
    ) -> None:
        """Initialize the dependency.

        Args:
            limiter: A ``pyrate_limiter.Limiter`` (typically module-level).
            identifier: Optional callable that derives the rate-limit bucket
                key from the request. Defaults to ``"{client_ip}:{path}"``.
            blocking: If ``True``, ``try_acquire_async`` blocks until a slot
                is free instead of returning ``False``. Defaults to ``False``
                (raise 429 when the limit is exceeded).
        """
        self.limiter = limiter
        self._custom_identifier = identifier
        self.blocking = blocking

    async def __call__(self, request: Request, response: Response) -> None:
        """Check the rate limit for the current request.

        Args:
            request: The incoming FastAPI request.
            response: The outgoing FastAPI response (signature compatibility
                with the original ``fastapi_limiter`` dependency).

        Raises:
            HTTPException: With status 429 if the rate limit is exceeded and
                ``blocking`` is ``False``.
        """
        # E2E test mode: disable all rate limiting (prevents false 429 failures).
        # NARRARE_E2E_TEST is owned by CoreSettings (ADR-071 §3) — read via
        # get_core_settings(), not os.environ.
        if get_core_settings().e2e_test:
            return None

        del response  # signature compatibility only; unused.
        rate_key = await self._identifier(request)
        acquired = await self.limiter.try_acquire_async(rate_key, blocking=self.blocking)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests",
            )

    async def _identifier(self, request: Request) -> str:
        """Generate the rate-limit bucket key.

        Uses the custom identifier if provided (awaiting it if async),
        otherwise ``"{client_ip}:{path}"`` where the client IP is taken from
        ``X-Forwarded-For`` (first hop), falling back to
        ``request.client.host``, then ``127.0.0.1``.

        Note:
            With the default in-memory ``Limiter(Rate(...))`` (single shared
            bucket per AR-05-02), this key is informational only —
            ``SingleBucketFactory`` ignores the key, so all requests through
            one ``Limiter`` instance share a single counter. Rate-limit
            isolation between endpoint groups is therefore achieved by using
            **separate ``RateLimiter`` instances** (see ``rate_limits.py``),
            not by the key. The key is still produced so that a future
            multi-bucket or Redis backend could key on it without code
            changes here.
        """
        if self._custom_identifier is not None:
            result = self._custom_identifier(request)
            if isinstance(result, Awaitable):
                return await result
            return result

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        elif request.client:
            ip = request.client.host
        else:
            ip = "127.0.0.1"
        return f"{ip}:{request.url.path}"
