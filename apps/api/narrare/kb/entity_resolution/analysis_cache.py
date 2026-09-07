"""Analysis cache for the KB entity resolution layer (ADR-085 P3).

Extracted from ``analysis_service.py`` per RULE-04 when the P4 dismissal
filter needed room in the service file. Caching mirrors the
``kb/consistency_cache.py`` pattern — injected ``SessionCacheProtocol``
backend, 10-minute TTL, novel-scoped key, tolerant reads — with one
deviation: the entries hash is stored in an envelope next to the payload
instead of being appended to the key.

Root cause: a fresh hash suffix per KB mutation would strand one TTL key
per mutation and make an explicit ``invalidate`` impossible to enumerate
(a hash-suffixed key for a *previous* entry set cannot be derived after
the mutation). The envelope binds the cached payload to the entry set
with the same staleness safety while ``delete_all`` remains a real
single-key invalidation for the KB-mutation hooks.

The payload stored here is the UNFILTERED detection result — rejected
suggestions (spec §7) are applied at read time by the analysis service,
so a rejection also covers results cached before it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, cast

import structlog

if TYPE_CHECKING:
    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_SECONDS: Final[int] = 600
_DEFAULT_KEY_PREFIX: Final[str] = "kb:resolution:"


class ResolutionAnalysisCache:
    """Cache for resolution analysis results (in-memory backend per ADR-080).

    Single key per novel (``kb:resolution:{novel_id}``) holding a
    ``{"entries_hash": str, "payload": str}`` envelope; a lookup is a hit
    only when the stored hash matches the caller's current entries hash.

    Args:
        cache: Injected cache backend via ``SessionCacheProtocol``.
        ttl: Cache TTL in seconds.
        key_prefix: Cache key prefix for namespace isolation.
    """

    def __init__(
        self,
        cache: SessionCacheProtocol,
        *,
        ttl: int = _DEFAULT_TTL_SECONDS,
        key_prefix: str = _DEFAULT_KEY_PREFIX,
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._key_prefix = key_prefix

    def _key(self, novel_id: str) -> str:
        return f"{self._key_prefix}{novel_id}"

    async def get(self, novel_id: str, entries_hash: str) -> str | None:
        """Return the cached payload iff it was stored for ``entries_hash``.

        Backend failures and malformed envelopes degrade to a miss
        (fails open — recomputation is always correct, RULE-11).
        """
        try:
            raw = await self._cache.get(self._key(novel_id))
            envelope = cast(
                "dict[str, object] | None",
                json.loads(raw) if raw is not None else None,
            )
        except Exception:
            logger.warning("resolution_cache_unavailable", novel_id=novel_id)
            return None
        if not isinstance(envelope, dict) or envelope.get("entries_hash") != entries_hash:
            return None
        payload = envelope.get("payload")
        if not isinstance(payload, str):
            logger.warning("resolution_cache_malformed", novel_id=novel_id)
            return None
        logger.debug("resolution_cache_hit", novel_id=novel_id)
        return payload

    async def set(self, novel_id: str, value: str, entries_hash: str) -> None:
        """Cache the analysis payload bound to ``entries_hash`` with the TTL."""
        envelope = json.dumps({"entries_hash": entries_hash, "payload": value})
        await self._cache.set(self._key(novel_id), envelope, ttl_seconds=self._ttl)
        logger.debug("resolution_cache_set", novel_id=novel_id)

    async def delete_all(self, novel_id: str) -> None:
        """Invalidate the cached analysis for a novel (KB-mutation hook point)."""
        await self._cache.delete(self._key(novel_id))
        logger.debug("resolution_cache_invalidated", novel_id=novel_id)
