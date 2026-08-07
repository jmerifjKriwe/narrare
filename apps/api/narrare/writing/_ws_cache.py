"""WebSocket session cache — re-export of the Core in-memory cache.

WebSocket interactive sessions reuse the TTL-capable
:class:`~narrare_core.cache.InMemorySessionCache` from ``core/cache``
(ADR-080, RULE-08: cache adapters live in ``core/cache``, not the writing
layer). The WS session store operates in **no-expiry mode**: the lifespan
constructs it with ``ttl_seconds=None`` (the default), so entries persist
for the process lifetime and are never evicted by TTL.

This module is a thin re-export — there is no longer a duplicate
implementation here. Keeping the re-export gives the writing layer a single
documented seam for the no-TTL choice without forcing every importer to
re-derive it.
"""

from __future__ import annotations

from narrare_core.cache import InMemorySessionCache

__all__ = ["InMemorySessionCache"]
