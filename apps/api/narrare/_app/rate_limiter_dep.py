"""Custom FastAPI rate-limiter dependency using ``pyrate_limiter`` directly.

Replaces ``fastapi_limiter.depends.RateLimiter``, which is incompatible with
FastAPI 0.116+: its ``__call__`` iterates ``request.app.routes`` and reads
``route.path`` on every entry, but FastAPI 0.116+ inserts ``_IncludedRouter``
objects (from ``app.include_router``) into that list which have no ``.path``
attribute → ``AttributeError`` → HTTP 500 on every rate-limited route.

This module is a drop-in replacement with the same constructor signature and
call protocol. It derives the rate-limit key from the request identity and
``request.url.path`` and never iterates ``request.app.routes``.

It is also the home of :class:`SelfPruningLimiter` — the app-wide pyrate
limiter construction policy (no background sweeper thread; see the class
docstring) — used by both the FastAPI dependency and the raw WebSocket
limiter in ``rate_limits.py``.

See ``rate_limits.py`` for the module-level limiter instances.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status
from pyrate_limiter import AbstractBucket, InMemoryBucket, Limiter, Rate, SingleBucketFactory

from narrare_core.settings import get_core_settings

Identifier = Callable[[Request], str | Awaitable[str]]
"""Callable that derives the rate-limit bucket key from a request.

May be synchronous (returning ``str``) or asynchronous (returning an
awaitable ``str``). Async callables are awaited automatically.
"""


class SelfPruningLimiter(Limiter):
    """In-memory limiter without pyrate_limiter's background sweeper thread.

    pyrate-limiter 4.x's default ``Limiter(Rate(...))`` construction spawns a
    ``"PyrateLimiter's Leaker"`` daemon thread — each with its own asyncio
    event loop — **per instance**, at construction time (``SingleBucketFactory``
    defaults to ``schedule_leak=True``). With the module-level limiters in
    ``rate_limits.py`` and ``auth/router.py`` that cost 8 threads + 8 event
    loops + their fds per process, alive from import (so also in every test
    process).

    This subclass builds the same ``InMemoryBucket`` via
    ``SingleBucketFactory(schedule_leak=False)`` and instead prunes outdated
    items at acquire time by calling the bucket's own ``leak(now)`` — the
    exact method and clock the background sweeper would use. For the
    sliding-window admit decision this is semantically identical: stale items
    are never counted by ``InMemoryBucket.put`` (it bisects on item
    timestamps), so sweeping is purely memory hygiene. Acquire-time pruning
    keeps the bucket hard-bounded to roughly one rate window of admitted
    requests and costs one O(log n) bisect per acquire.

    Use this instead of a bare ``Limiter(Rate(...))`` for every in-memory
    limiter in Narrare. (Only ``try_acquire`` / ``try_acquire_async`` prune —
    which are the only entry points Narrare uses; pyrate's ``as_decorator``
    would not.)
    """

    def __init__(self, rate: Rate, buffer_ms: int = 50) -> None:
        """Build a single-bucket limiter for ``rate`` without a sweeper thread.

        Args:
            rate: The (count, window) rate to enforce.
            buffer_ms: Clock-drift buffer, forwarded to ``Limiter``.
        """
        bucket = InMemoryBucket([rate])
        self._bucket = bucket
        super().__init__(SingleBucketFactory(bucket, schedule_leak=False), buffer_ms=buffer_ms)

    def _prune(self) -> None:
        """Drop items older than the largest rate window (sweeper equivalent)."""
        now = self._bucket.now()
        # InMemoryBucket's clock (MonotonicClock) is sync — an awaitable here
        # would be a construction bug, not a runtime condition.
        assert isinstance(now, int)
        self._bucket.leak(now)

    def buckets(self) -> list[AbstractBucket]:
        """The single active bucket — no Leaker registry involved.

        Overrides ``Limiter.buckets()`` because pyrate's default routes
        through the sweeper's bucket registry (``BucketFactory.get_buckets``
        returns ``[]`` when the sweeper is disabled), which would silently
        break callers that enumerate buckets — notably the per-test bucket
        flush in ``tests/unit/conftest.py``.
        """
        return [self._bucket]

    def try_acquire(
        self,
        name: str = "pyrate",
        weight: int = 1,
        blocking: bool = True,
        timeout: int | float = -1,
    ) -> bool | Awaitable[bool]:
        """Prune expired items, then delegate to ``Limiter.try_acquire``."""
        self._prune()
        return super().try_acquire(name=name, weight=weight, blocking=blocking, timeout=timeout)

    async def try_acquire_async(
        self,
        name: str = "pyrate",
        weight: int = 1,
        blocking: bool = True,
        timeout: int | float = -1,
    ) -> bool:
        """Prune expired items, then delegate to ``Limiter.try_acquire_async``."""
        self._prune()
        return await super().try_acquire_async(
            name=name, weight=weight, blocking=blocking, timeout=timeout
        )


class RateLimiter:
    """FastAPI dependency for rate limiting using ``pyrate_limiter``.

    Drop-in replacement for ``fastapi_limiter.depends.RateLimiter``.

    Usage::

        MY_LIMITER = RateLimiter(SelfPruningLimiter(Rate(3, Duration.MINUTE)))

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
