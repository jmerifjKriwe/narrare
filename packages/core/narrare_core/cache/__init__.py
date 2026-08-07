"""Cache abstraction layer.

Provides cache backends implementing
:class:`~narrare_core.writing.session_manager.SessionCacheProtocol` for
session state and other short-lived values.

The Redis-free, single-user default is
:class:`InMemorySessionCache` (ADR-080): a TTL-capable, in-process cache.
The legacy Redis-backed implementation was removed in migration Step 2b; a
Redis (or equivalent) implementation can be re-plugged into the same
Protocol when multi-user deployment arrives (see ADR-080).

See: docs/_shared/CONSTRAINTS.md (RULE-08 — cache adapters live in
``core/cache/``).
"""

from narrare_core.cache.in_memory import InMemorySessionCache

__all__ = [
    "InMemorySessionCache",
]
