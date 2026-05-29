"""AgentRegistry — Protocol definition.

RULE-03: Contract (Protocol) before implementation.

The AgentRegistry caches NarrareAgent instances by (agent_type, model,
system_prompt) so that LLM providers can recognize identical requests
and leverage prompt caching (ADR-016 Phase 0).

Cache key: ``(agent_type.__qualname__, id(model), system_prompt or "")``
- ``id(model)`` is safe because Model instances from ModelRegistry are
  unique per ``(provider_name, model_id, credentials)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from narrare_core.agents.base import NarrareAgent


@runtime_checkable
class AgentRegistryProtocol(Protocol):
    """Protocol for agent instance caching.

    Caches NarrareAgent instances by (agent_type, model, system_prompt) so
    that providers can recognize identical requests and leverage prompt
    caching.

    Thread safety:
        All mutating operations are protected by an asyncio.Lock.
        Reads (fast-path cache hit) are safe without the lock in CPython.

    Lifecycle:
        - TTL-based cleanup: entries not accessed within ``ttl_seconds``
          are treated as expired and removed on the next cache miss.
        - LRU eviction: when the cache reaches ``max_size``, the least
          recently used entry is evicted to make room for new agents.
    """

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

        If a cached entry exists for the computed key and has not expired
        (within TTL), returns it immediately.  Otherwise creates a new
        agent instance, performing TTL cleanup and LRU eviction as needed.

        Args:
            agent_type: The NarrareAgent subclass to instantiate.
            model: LLM model instance (from ModelRegistry).
            deps_type: Dependencies type for the agent.
            output_type: Output specification for the agent.
            capabilities: Additional capabilities to inject.
            system_prompt: System prompt for the agent.
            **agent_kwargs: Extra keyword arguments forwarded to the
                agent constructor.

        Returns:
            A cached or freshly created NarrareAgent instance.
        """
        ...

    async def invalidate(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> bool:
        """Remove a specific agent from the cache.

        Args:
            agent_type: The agent type to invalidate.
            model: The model instance used in the cache key.
            system_prompt: The system prompt used in the cache key.

        Returns:
            True if the agent was found and removed, False otherwise.
        """
        ...

    async def clear(self) -> int:
        """Remove all agents from the cache.

        Returns:
            The number of agents that were in the cache before clearing.
        """
        ...

    @property
    def size(self) -> int:
        """Current number of cached agent instances."""
        ...
