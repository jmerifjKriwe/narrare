"""Tests for memory/preference_service.py — PreferenceService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.models import PreferenceProfile
from narrare_core.memory.preference_service import PreferenceService


def _mock_search_result(texts: list[str]) -> dict[str, list[dict[str, str]]]:
    """Build a mem0 search result payload from a list of memory texts."""
    return {"results": [{"memory": t} for t in texts]}


class TestPreferenceServiceGetPreferences:
    """Tests for PreferenceService.get_preferences()."""

    async def test_returns_empty_profile_when_no_results(self) -> None:
        """Empty mem0 returns an empty PreferenceProfile."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = PreferenceService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        profile = await service.get_preferences(user_id, project_id)

        assert isinstance(profile, PreferenceProfile)
        assert profile.user_id == user_id
        assert profile.project_id == project_id
        assert profile.event_count == 0
        assert profile.confidence == 0.0
        assert profile.style == {}
        assert profile.content == {}
        assert profile.constraints == []

    async def test_returns_populated_profile_from_mem0(self) -> None:
        """mem0 results populate style, content, and constraints."""
        mem0 = AsyncMock()
        # Three queries: style, content, constraints
        mem0.search.side_effect = [
            _mock_search_result(["Prefers short sentences", "Likes active voice"]),
            _mock_search_result(["Enjoys literary fiction"]),
            _mock_search_result(["Avoids graphic violence"]),
        ]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        assert profile.event_count == 4  # 2 + 1 + 1
        assert len(profile.style) == 2
        assert len(profile.content) == 1
        assert len(profile.constraints) == 1
        assert "Avoids graphic violence" in profile.constraints

    async def test_confidence_scales_with_memory_count(self) -> None:
        """Confidence = min(1.0, total_memories / 20.0)."""
        mem0 = AsyncMock()
        # 10 memories across 3 queries → confidence = 10/20 = 0.5
        ten_results = _mock_search_result([f"memory {i}" for i in range(10)])
        mem0.search.side_effect = [ten_results, {"results": []}, {"results": []}]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        assert profile.event_count == 10
        assert profile.confidence == pytest.approx(0.5)

    async def test_confidence_caps_at_one(self) -> None:
        """Confidence saturates at 1.0 for 20+ memories."""
        mem0 = AsyncMock()
        many = _mock_search_result([f"m{i}" for i in range(25)])
        mem0.search.side_effect = [many, {"results": []}, {"results": []}]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        assert profile.confidence == 1.0

    async def test_handles_mem0_exception_gracefully(self) -> None:
        """A failing dimension query returns partial results."""
        mem0 = AsyncMock()
        mem0.search.side_effect = [
            _mock_search_result(["Prefers formal tone"]),  # style OK
            RuntimeError("mem0 down"),  # content fails
            _mock_search_result(["No clichés"]),  # constraints OK
        ]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        # Got partial data from style and constraints
        assert len(profile.style) == 1
        assert len(profile.constraints) == 1
        assert profile.event_count == 2

    async def test_search_called_with_filters_parameter(self) -> None:
        """search() must pass user_id and agent_id via filters dict."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = PreferenceService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        await service.get_preferences(user_id, project_id)

        # Verify every search call uses filters with correct user_id/agent_id
        for call in mem0.search.await_args_list:
            call_kwargs = call[1]
            assert "filters" in call_kwargs
            assert call_kwargs["filters"]["user_id"] == str(user_id)
            assert call_kwargs["filters"]["agent_id"] == str(project_id)

    async def test_skips_empty_memory_text(self) -> None:
        """Empty memory text is skipped (continue at line 77)."""
        mem0 = AsyncMock()
        mem0.search.side_effect = [
            {"results": [{"memory": ""}, {"memory": "Valid style"}]},
            {"results": []},
            {"results": []},
        ]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        # Only the non-empty text was kept; event_count counts ALL results
        # (including skipped ones) so it's 2
        assert len(profile.style) == 1
        assert "Valid style" in profile.style.values()
        assert profile.event_count == 2
        assert profile.confidence == 0.1  # 2 / 20

    async def test_handles_memory_text_in_text_field(self) -> None:
        """Some mem0 results use 'text' key instead of 'memory'."""
        mem0 = AsyncMock()
        mem0.search.side_effect = [
            {"results": [{"text": "Likes metaphors"}]},
            {"results": []},
            {"results": []},
        ]
        service = PreferenceService(mem0_client=mem0)

        profile = await service.get_preferences(uuid4(), uuid4())

        assert len(profile.style) == 1
        assert "Likes metaphors" in profile.style.values()


class TestPreferenceServiceReset:
    """Tests for PreferenceService.reset()."""

    async def test_reset_calls_mem0_delete_all(self) -> None:
        """reset() calls mem0.delete_all() with correct user/project."""
        mem0 = AsyncMock()
        service = PreferenceService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        await service.reset(user_id, project_id)

        mem0.delete_all.assert_awaited_once_with(
            user_id=str(user_id),
            agent_id=str(project_id),
        )

    async def test_reset_handles_mem0_exception(self) -> None:
        """reset() does not raise when mem0 fails — logs warning."""
        mem0 = AsyncMock()
        mem0.delete_all.side_effect = RuntimeError("mem0 down")
        service = PreferenceService(mem0_client=mem0)

        # Should NOT raise
        await service.reset(uuid4(), uuid4())

        mem0.delete_all.assert_awaited_once()

    async def test_reset_with_null_memory_client(self) -> None:
        """reset() with NullMemoryClient completes without error."""
        null_client = NullMemoryClient()
        service = PreferenceService(mem0_client=null_client)

        # Should NOT raise — NullMemoryClient silently succeeds
        await service.reset(uuid4(), uuid4())
