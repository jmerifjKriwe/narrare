"""Tests for writing stats service."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock as Mock
from uuid import uuid4

import pytest

from narrare.writing.schemas import GenerationStatsResponse
from narrare.writing.stats_service import StatsService


class TestStatsService:
    """Tests for StatsService."""

    @pytest.fixture
    def mock_repo(self) -> Mock:
        repo = Mock()
        repo.get_stats_for_novel = AsyncMock(
            return_value={
                "total_generations": 10,
                "success_rate": 0.9,
                "avg_tokens": 1500.0,
                "avg_word_count": 500.0,
                "most_used_model": "claude-sonnet-4-5-20251020",
            }
        )
        return repo

    @pytest.fixture
    def service(self, mock_repo: Mock) -> StatsService:
        return StatsService(repo=mock_repo)

    async def test_get_stats_returns_response(self, service: StatsService, mock_repo: Mock) -> None:
        """Test get_stats returns properly formatted response."""
        novel_id = uuid4()

        result = await service.get_stats(novel_id)

        mock_repo.get_stats_for_novel.assert_called_once_with(novel_id)
        assert isinstance(result, GenerationStatsResponse)
        assert result.total_generations == 10
        assert result.success_rate == 0.9
        assert result.avg_tokens == 1500.0

    async def test_get_stats_with_zero_generations(self, mock_repo: Mock) -> None:
        """Test get_stats handles zero generations."""
        mock_repo.get_stats_for_novel = AsyncMock(
            return_value={
                "total_generations": 0,
                "success_rate": 0.0,
                "avg_tokens": 0.0,
                "avg_word_count": 0.0,
                "most_used_model": None,
            }
        )
        service = StatsService(repo=mock_repo)
        novel_id = uuid4()

        result = await service.get_stats(novel_id)

        assert result.total_generations == 0
        assert result.success_rate == 0.0
        assert result.most_used_model is None
