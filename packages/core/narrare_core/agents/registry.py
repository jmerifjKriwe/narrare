"""AgentRegistry — Singleton cache for NarrareAgent instances.

Caches agents by ``(agent_type.__qualname__, id(model), system_prompt or "")``
so LLM providers can recognize identical requests and leverage prompt
caching (ADR-016 Phase 0).

Thread safety:
    asyncio.Lock protects all mutations.  Fast-path reads (dict.get)
    are safe in CPython without the lock.

Defaults:
    max_size=50, ttl_seconds=300.0 (matches Anthropic cache TTL).

See contracts.py for the Protocol definition (RULE-03).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from narrare_core.agents.base import NarrareAgent


@dataclass
class _CacheEntry:
    """Internal cache entry tracking an agent instance and access times.

    Attributes:
        agent: The cached NarrareAgent instance.
        created_at: Monotonic timestamp when the entry was created.
        last_accessed: Monotonic timestamp of the last access (used for
            TTL checks and LRU ordering).
    """

    agent: NarrareAgent[Any, Any]
    created_at: float
    last_accessed: float


class AgentRegistry:
    """Cache for NarrareAgent instances with TTL-based cleanup and LRU eviction.

    Cache key: ``(agent_type.__qualname__, id(model), system_prompt or "")``

    - ``id(model)`` is safe because Model instances from ModelRegistry are
      unique per ``(provider_name, model_id, credentials)``.
    - Only non-None kwargs are forwarded to the agent constructor, so
      each agent subclass can define its own constructor signature.

    Usage::

        registry = AgentRegistry(max_size=50, ttl_seconds=300.0)
        agent = await registry.get_or_create(
            ChapterSummaryAgent, model, system_prompt="..."
        )
        # Second call with same key returns the cached instance
        agent2 = await registry.get_or_create(
            ChapterSummaryAgent, model, system_prompt="..."
        )
        assert agent is agent2
    """

    def __init__(
        self,
        *,
        max_size: int = 50,
        ttl_seconds: float = 300.0,
    ) -> None:
        self._cache: dict[tuple[str, int, str], _CacheEntry] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    def _cache_key(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        system_prompt: str | None,
    ) -> tuple[str, int, str]:
        """Compute the cache key for a given agent configuration."""
        return (agent_type.__qualname__, id(model), system_prompt or "")

    async def get_or_create(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        deps_type: type[Any] | None = None,
        output_type: Any | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
        **agent_kwargs: Any,
    ) -> NarrareAgent[Any, Any]:
        """Get a cached agent or create and cache a new one.

        Fast path: check cache without lock (dict reads are safe in CPython).
        Slow path: acquire lock, double-check, cleanup, create.
        """
        key = self._cache_key(agent_type, model, system_prompt)
        now = time.monotonic()

        # Fast path — no lock needed for dict reads in CPython
        entry = self._cache.get(key)
        if entry is not None and (now - entry.last_accessed) < self._ttl_seconds:
            entry.last_accessed = now
            return entry.agent

        # Slow path — create / recreate under lock
        async with self._lock:
            # Double-check after acquiring lock
            now = time.monotonic()
            entry = self._cache.get(key)
            if entry is not None and (now - entry.last_accessed) < self._ttl_seconds:
                entry.last_accessed = now
                return entry.agent

            # Remove expired entries + LRU eviction
            await self._cleanup_locked()

            # Build kwargs — only forward non-None values so agent
            # subclasses with simplified constructors aren't broken.
            kwargs: dict[str, Any] = {"model": model}
            if deps_type is not None:
                kwargs["deps_type"] = deps_type
            if output_type is not None:
                kwargs["output_type"] = output_type
            if capabilities is not None:
                kwargs["capabilities"] = capabilities
            if system_prompt is not None:
                kwargs["system_prompt"] = system_prompt
            kwargs.update(agent_kwargs)

            agent = agent_type(**kwargs)
            self._cache[key] = _CacheEntry(
                agent=agent,
                created_at=now,
                last_accessed=now,
            )
            return agent

    async def _cleanup_locked(self) -> None:
        """Remove expired entries and LRU-evict if at capacity.

        Must be called while holding ``self._lock``.
        """
        now = time.monotonic()

        # Phase 1: remove expired entries
        expired = [
            k for k, v in self._cache.items() if (now - v.last_accessed) >= self._ttl_seconds
        ]
        for k in expired:
            del self._cache[k]

        # Phase 2: LRU eviction if still at capacity
        while len(self._cache) >= self._max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k].last_accessed)
            del self._cache[oldest]

    async def invalidate(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> bool:
        """Remove a specific agent from the cache.

        Returns True if the agent was found and removed, False otherwise.
        """
        key = self._cache_key(agent_type, model, system_prompt)
        async with self._lock:
            return self._cache.pop(key, None) is not None

    async def clear(self) -> int:
        """Remove all cached agents and return the count removed."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    @property
    def size(self) -> int:
        """Current number of cached agent instances."""
        return len(self._cache)
