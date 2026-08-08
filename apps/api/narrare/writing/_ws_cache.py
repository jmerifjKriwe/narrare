"""WebSocket session cache — re-export of the Core in-memory cache.

WebSocket interactive sessions reuse the TTL-capable
:class:`~narrare_core.cache.InMemorySessionCache` from ``core/cache``
(ADR-080, RULE-08: cache adapters live in ``core/cache``, not the writing
layer). The store is bounded in two ways:

- **TTL-bounded** — ``SessionManager`` persists every session with a
  30-minute TTL (``session_ttl_seconds=30 * 60``) and refreshes it on each
  write, so sessions expire if unused.
- **Explicitly evicted** — ``SessionManager.end_session`` deletes the
  cached entry on an explicit ``end_session`` message. Transport
  disconnects do NOT delete (ADR-052: reattach survives until the TTL
  expires).
- **Size-capped (safety net)** — the lifespan constructs the singleton
  with ``max_entries=10_000`` so the store cannot grow unbounded even for
  entries written without a TTL.

Note: ``InMemorySessionCache`` has no ``ttl_seconds`` constructor
parameter — its constructor takes ``max_entries`` and ``clock`` only.
TTL is passed per-write by ``SessionManager``.

This module is a thin re-export — there is no longer a duplicate
implementation here. Keeping the re-export gives the writing layer a single
documented seam for the WS cache without forcing every importer to
re-derive it.
"""

from __future__ import annotations

from narrare_core.cache import InMemorySessionCache

__all__ = ["InMemorySessionCache"]
