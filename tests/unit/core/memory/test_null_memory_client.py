"""Tests for memory/mem0_client.py — NullMemoryClient."""

from __future__ import annotations

from narrare_core.memory.mem0_client import NullMemoryClient


class TestNullMemoryClient:
    """Every method returns empty results without error."""

    async def test_add_returns_empty_results(self) -> None:
        client = NullMemoryClient()
        result = await client.add(messages="some data", user_id="user-1")
        assert result == {"results": [], "relations": []}

    async def test_search_returns_empty_results(self) -> None:
        client = NullMemoryClient()
        result = await client.search(query="test", filters={"user_id": "user-1"})
        assert result == {"results": []}

    async def test_get_all_returns_empty_results(self) -> None:
        client = NullMemoryClient()
        result = await client.get_all(filters={"user_id": "user-1"})
        assert result == {"results": []}

    async def test_delete_returns_empty_results(self) -> None:
        client = NullMemoryClient()
        result = await client.delete(memory_id="mem-1")
        assert result == {"results": []}

    async def test_delete_all_returns_empty_results(self) -> None:
        client = NullMemoryClient()
        result = await client.delete_all(user_id="user-1")
        assert result == {"results": []}

    async def test_add_with_messages_list(self) -> None:
        """add() accepts messages as list of dicts (mem0 2.0.x format)."""
        client = NullMemoryClient()
        result = await client.add(
            messages=[{"role": "user", "content": "hello"}],
            user_id="user-1",
            agent_id="project-1",
            metadata={"key": "value"},
        )
        assert result == {"results": [], "relations": []}

    async def test_methods_accept_any_kwargs(self) -> None:
        """Ensure all methods accept arbitrary keyword arguments via **kwargs."""
        client = NullMemoryClient()

        result = await client.add(messages="test", custom_param="value", another=42)
        assert "results" in result

        result = await client.search(query="test", limit=10)
        assert "results" in result

        result = await client.get_all(user_id="user-1")
        assert "results" in result

        result = await client.delete(memory_id="mem-1")
        assert "results" in result

        result = await client.delete_all(user_id="user-1")
        assert "results" in result
