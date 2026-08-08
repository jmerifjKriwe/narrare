"""TTL-capable in-process session cache implementing SessionCacheProtocol.

This is the Redis-free cache adapter for single-user deployment (ADR-080).
It is dict-backed with **real TTL expiration** via lazy expiry-on-access
plus an opportunistic sweep on writes, so the store cannot grow unbounded
with stale entries.

Process-locality & durability (ADR-080)
---------------------------------------
This cache is **process-local**: entries live in the API process memory and
do **not** survive a restart, and they are not shared across processes.
This is the explicitly accepted durability trade-off for single-user,
self-hosted deployment (ADR-029 VM-first). It is acceptable because the
consumers (writing sessions, KB creation sessions, beta-reader caches,
KB-improve/consistency/worldbuilding caches) are best-effort or
re-creatable: a lost session is re-attachable, and caches simply repopulate.

Re-introduction path (ADR-080)
------------------------------
If Narrare moves to multi-user / multi-worker deployment, a Redis-backed
(or equivalent) cache can be re-plugged into the **same**
:class:`SessionCacheProtocol` (defined in
``narrare_core.writing.session_manager``) without touching the 5 DI factories
or the cache *wrapper* classes — they all consume the cache via the
Protocol. The single seam is the instantiation site; see ADR-080's
"Re-introduction path".

See:
    :class:`narrare_core.writing.session_manager.SessionCacheProtocol`
    (RULE-08 — cache adapters live in ``core/cache/``; this module imports
    no Redis.)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)

#: A monotonic-clock callable returning the current time in seconds.
Clock = Callable[[], float]


class _Entry(NamedTuple):
    """A cached value paired with its absolute expiry timestamp.

    ``expiry`` is an absolute ``time.monotonic``-style timestamp; ``None``
    means the entry never expires.
    """

    value: str
    expiry: float | None


class InMemorySessionCache:
    """In-memory, TTL-capable session cache.

    Implements :class:`SessionCacheProtocol` from
    ``core/writing/session_manager.py``.  The public method shape mirrors
    the Protocol so a DI factory can swap in any conforming cache backend
    in a single line.

    TTL is honoured for real (unlike the legacy writing-layer stub that
    ignored it).  Expiration is lazy and opportunistic:

    * **Lazy on access** — :meth:`get` of an expired key returns ``None``
      and evicts the entry immediately.
    * **Opportunistic sweep on write** — :meth:`set` first purges any
      entries whose TTL has already elapsed, so expired entries that are
      never read again cannot accumulate and the store cannot grow
      unbounded.  No background task is required, avoiding event-loop
      lifecycle complexity.

    TTL is the **primary bound** on growth.  ``max_entries`` is an opt-in
    **safety net** for writers that never pass a TTL (e.g. the WebSocket
    session store): once the store reaches the cap, the next write evicts
    the oldest-inserted entry.  The cap is enforced on the write path
    (after the expiry sweep), and eviction follows insertion order —
    Python dicts preserve it, so the first key in iteration order is the
    oldest inserted.

    Args:
        clock:
            Monotonic-clock callable used for expiry math, defaulting to
            :func:`time.monotonic`. Injected primarily for deterministic
            testing — production code should leave the default.
        max_entries:
            Optional hard cap on the number of cached entries.  When a
            write leaves the store at/over this size, the oldest-inserted
            entry is evicted (LRU proxy via insertion order) and the
            eviction is logged.  ``None`` (default) keeps the current
            unbounded behaviour — TTL expiry alone bounds the store.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        max_entries: int | None = None,
    ) -> None:
        self._store: dict[str, _Entry] = {}
        self._clock: Clock = time.monotonic if clock is None else clock
        self._max_entries: int | None = max_entries

    # ------------------------------------------------------------------
    # Public API — SessionCacheProtocol
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        """Get a cached value.

        Returns the value as a string, or ``None`` when the key does not
        exist or has expired.  An expired entry is evicted on access.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._is_expired(entry, self._now()):
            del self._store[key]
            logger.debug("in_memory_cache_entry_expired", key=key)
            return None
        return entry.value

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a cached value with an optional TTL.

        When *ttl_seconds* is ``None`` the key persists for the lifetime of
        the process (no expiry) — this is the mode used by the WebSocket
        session store.  Before storing, any already-expired entries are
        swept so the store stays bounded; when a ``max_entries`` cap is
        configured, exceeding it evicts the oldest-inserted entry.
        """
        now = self._now()
        self._purge_expired(now)

        expiry: float | None = None if ttl_seconds is None else now + ttl_seconds
        self._store[key] = _Entry(value, expiry)

        if self._max_entries is not None and len(self._store) > self._max_entries:
            self._evict_lru()

    async def delete(self, key: str) -> None:
        """Delete a cached value.

        Succeeds silently even when *key* does not exist.
        """
        self._store.pop(key, None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _now(self) -> float:
        """Current time from the configured clock."""
        return self._clock()

    @staticmethod
    def _is_expired(entry: _Entry, now: float) -> bool:
        """True when the entry has a TTL that has elapsed by *now*."""
        return entry.expiry is not None and now >= entry.expiry

    def _purge_expired(self, now: float) -> None:
        """Remove every entry whose TTL has elapsed.

        Entries without a TTL are never purged here.
        """
        expired = [key for key, entry in self._store.items() if self._is_expired(entry, now)]
        if not expired:
            return
        for key in expired:
            del self._store[key]
        logger.debug("in_memory_cache_purged", count=len(expired))

    def _evict_lru(self) -> None:
        """Evict the oldest-inserted entry when the size cap is exceeded.

        Called only after a write leaves the store over ``max_entries``.
        Python dicts preserve insertion order, so the first key in
        iteration order is the oldest inserted — the LRU proxy.  The
        eviction is logged (RULE-11 — no silent data loss).
        """
        oldest = next(iter(self._store))
        del self._store[oldest]
        logger.info(
            "in_memory_cache_evicted_lru",
            key=oldest,
            max_entries=self._max_entries,
        )
