"""Tests for AgentRegistry — TTL-based caching and LRU eviction.

Covers:
1. Cache hit: same key → same instance
2. Cache miss: different agent_type / model / system_prompt
3. TTL expiry: expired entry → new instance
4. TTL refresh: access resets last_accessed
5. LRU eviction: max_size exceeded → oldest removed
6. LRU order: least recently used evicted first
7. invalidate(): hit and miss
8. clear(): with entries and empty
9. size property
10. Concurrent access: no race conditions / duplicates
11. Custom kwargs forwarded to agent constructor
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.contracts import AgentRegistryProtocol
from narrare_core.agents.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MinimalAgent(NarrareAgent[None, str]):
    """Minimal concrete NarrareAgent for testing."""

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=type(None),
            output_type=str,
            system_prompt=system_prompt,
        )


class _AnotherAgent(NarrareAgent[None, str]):
    """A second agent type (different qualname) for cache-miss tests."""

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=type(None),
            output_type=str,
            system_prompt=system_prompt,
        )


# ---------------------------------------------------------------------------
# A. Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """AgentRegistry satisfies AgentRegistryProtocol."""

    def test_is_instance_of_protocol(self) -> None:
        registry = AgentRegistry()
        assert isinstance(registry, AgentRegistryProtocol)


# ---------------------------------------------------------------------------
# B. Cache hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Same key returns the same instance (identity check)."""

    @pytest.mark.asyncio
    async def test_same_agent_type_model_prompt_returns_same_instance(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model, system_prompt="test")
        agent2 = await registry.get_or_create(_MinimalAgent, model, system_prompt="test")
        assert agent1 is agent2

    @pytest.mark.asyncio
    async def test_same_key_none_system_prompt(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model)
        agent2 = await registry.get_or_create(_MinimalAgent, model)
        assert agent1 is agent2

    @pytest.mark.asyncio
    async def test_none_system_prompt_same_as_explicit_none(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model)
        agent2 = await registry.get_or_create(_MinimalAgent, model, system_prompt=None)
        assert agent1 is agent2


# ---------------------------------------------------------------------------
# C. Cache miss
# ---------------------------------------------------------------------------


class TestCacheMiss:
    """Different keys produce different instances."""

    @pytest.mark.asyncio
    async def test_different_agent_type(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model)
        agent2 = await registry.get_or_create(_AnotherAgent, model)
        assert agent1 is not agent2

    @pytest.mark.asyncio
    async def test_different_model(self) -> None:
        registry = AgentRegistry()
        model_a = TestModel()
        model_b = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model_a)
        agent2 = await registry.get_or_create(_MinimalAgent, model_b)
        assert agent1 is not agent2

    @pytest.mark.asyncio
    async def test_different_system_prompt(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model, system_prompt="A")
        agent2 = await registry.get_or_create(_MinimalAgent, model, system_prompt="B")
        assert agent1 is not agent2


# ---------------------------------------------------------------------------
# D. TTL expiry
# ---------------------------------------------------------------------------


class TestTTLExpiry:
    """TTL-based cache invalidation."""

    @pytest.mark.asyncio
    async def test_expired_entry_creates_new_instance(self) -> None:
        registry = AgentRegistry(max_size=10, ttl_seconds=1.0)
        model = TestModel()

        agent1 = await registry.get_or_create(_MinimalAgent, model)

        # Expire all entries by winding back last_accessed
        for entry in registry._cache.values():
            entry.last_accessed = time.monotonic() - 100.0

        agent2 = await registry.get_or_create(_MinimalAgent, model)
        assert agent1 is not agent2

    @pytest.mark.asyncio
    async def test_access_refreshes_last_accessed(self) -> None:
        registry = AgentRegistry(max_size=10, ttl_seconds=60.0)
        model = TestModel()

        await registry.get_or_create(_MinimalAgent, model)
        key = next(iter(registry._cache.keys()))
        time_before = registry._cache[key].last_accessed

        # Small delay to ensure monotonic time advances
        await asyncio.sleep(0.01)

        await registry.get_or_create(_MinimalAgent, model)
        time_after = registry._cache[key].last_accessed
        assert time_after > time_before


# ---------------------------------------------------------------------------
# E. LRU eviction
# ---------------------------------------------------------------------------


class TestLRUEviction:
    """LRU eviction when max_size is exceeded."""

    @pytest.mark.asyncio
    async def test_exceeding_max_size_evicts_oldest(self) -> None:
        registry = AgentRegistry(max_size=2, ttl_seconds=60.0)
        model = TestModel()

        agent_a = await registry.get_or_create(_MinimalAgent, model, system_prompt="A")
        await registry.get_or_create(_MinimalAgent, model, system_prompt="B")
        assert registry.size == 2

        # Third entry evicts the oldest (A)
        await registry.get_or_create(_MinimalAgent, model, system_prompt="C")
        assert registry.size == 2

        # A was evicted → new instance
        agent_a2 = await registry.get_or_create(_MinimalAgent, model, system_prompt="A")
        assert agent_a2 is not agent_a

    @pytest.mark.asyncio
    async def test_lru_respects_access_order(self) -> None:
        registry = AgentRegistry(max_size=2, ttl_seconds=60.0)
        model = TestModel()

        # Create A then B
        await registry.get_or_create(_MinimalAgent, model, system_prompt="A")
        agent_b = await registry.get_or_create(_MinimalAgent, model, system_prompt="B")

        # Re-access A — refreshes its last_accessed
        await registry.get_or_create(_MinimalAgent, model, system_prompt="A")

        # Add C — should evict B (least recently used)
        await registry.get_or_create(_MinimalAgent, model, system_prompt="C")

        # B was evicted → new instance
        agent_b2 = await registry.get_or_create(_MinimalAgent, model, system_prompt="B")
        assert agent_b2 is not agent_b


# ---------------------------------------------------------------------------
# F. invalidate()
# ---------------------------------------------------------------------------


class TestInvalidate:
    """invalidate() removes specific agents."""

    @pytest.mark.asyncio
    async def test_existing_entry_returns_true(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        await registry.get_or_create(_MinimalAgent, model)
        assert registry.size == 1

        result = await registry.invalidate(_MinimalAgent, model)
        assert result is True
        assert registry.size == 0

    @pytest.mark.asyncio
    async def test_nonexistent_entry_returns_false(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        result = await registry.invalidate(_MinimalAgent, model)
        assert result is False

    @pytest.mark.asyncio
    async def test_with_system_prompt(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        await registry.get_or_create(_MinimalAgent, model, system_prompt="test")
        result = await registry.invalidate(_MinimalAgent, model, system_prompt="test")
        assert result is True
        assert registry.size == 0

    @pytest.mark.asyncio
    async def test_wrong_system_prompt_no_effect(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        await registry.get_or_create(_MinimalAgent, model, system_prompt="test")
        result = await registry.invalidate(_MinimalAgent, model, system_prompt="wrong")
        assert result is False
        assert registry.size == 1


# ---------------------------------------------------------------------------
# G. clear()
# ---------------------------------------------------------------------------


class TestClear:
    """clear() removes all agents."""

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        await registry.get_or_create(_MinimalAgent, model, system_prompt="A")
        await registry.get_or_create(_MinimalAgent, model, system_prompt="B")
        assert registry.size == 2

        count = await registry.clear()
        assert count == 2
        assert registry.size == 0

    @pytest.mark.asyncio
    async def test_empty_cache_returns_zero(self) -> None:
        registry = AgentRegistry()
        count = await registry.clear()
        assert count == 0


# ---------------------------------------------------------------------------
# H. size property
# ---------------------------------------------------------------------------


class TestSizeProperty:
    """size property reflects cache state."""

    @pytest.mark.asyncio
    async def test_tracks_entries(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        assert registry.size == 0

        await registry.get_or_create(_MinimalAgent, model)
        assert registry.size == 1

        await registry.get_or_create(_MinimalAgent, model, system_prompt="other")
        assert registry.size == 2

        await registry.clear()
        assert registry.size == 0


# ---------------------------------------------------------------------------
# I. Concurrent access
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    """Concurrent get_or_create produces no duplicates."""

    @pytest.mark.asyncio
    async def test_many_concurrent_calls_same_key(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agents = await asyncio.gather(
            *[registry.get_or_create(_MinimalAgent, model) for _ in range(20)]
        )

        # All calls must return the exact same instance
        first = agents[0]
        assert all(a is first for a in agents)
        assert registry.size == 1


# ---------------------------------------------------------------------------
# J. Custom kwargs
# ---------------------------------------------------------------------------


class TestCustomKwargs:
    """Extra kwargs are forwarded to the agent constructor."""

    @pytest.mark.asyncio
    async def test_system_prompt_forwarded(self) -> None:
        registry = AgentRegistry()
        model = TestModel()

        agent = await registry.get_or_create(_MinimalAgent, model, system_prompt="custom prompt")
        assert isinstance(agent, _MinimalAgent)

    @pytest.mark.asyncio
    async def test_kwargs_only_non_none_forwarded(self) -> None:
        """Only non-None kwargs are forwarded — simplified constructors work."""
        registry = AgentRegistry()
        model = TestModel()

        # _MinimalAgent only accepts model + system_prompt.
        # Passing None for deps_type/output_type should NOT raise.
        agent = await registry.get_or_create(
            _MinimalAgent,
            model,
            deps_type=None,
            output_type=None,
            system_prompt="test",
        )
        assert isinstance(agent, _MinimalAgent)
