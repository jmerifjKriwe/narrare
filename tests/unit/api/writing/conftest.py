"""Shared fixtures for writing service unit tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.contracts import GenerationRepositoryProtocol
from narrare.writing.service import WritingService
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.writing.pipeline import WritingPipeline


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock GenerationRepository."""
    repo = AsyncMock(spec=GenerationRepositoryProtocol)
    repo.create = AsyncMock(return_value=uuid.uuid4())
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    repo.get_stats_for_novel = AsyncMock(
        return_value={
            "total_generations": 5,
            "success_rate": 0.8,
            "avg_tokens": 1500.0,
            "avg_word_count": 2000.0,
            "most_used_model": "claude-sonnet-4-5-20251020",
        }
    )
    return repo


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    """Mock WritingPipeline."""
    pipeline = AsyncMock(spec=WritingPipeline)
    pipeline.stop = AsyncMock()
    return pipeline


@pytest.fixture
def mock_draft_processor() -> MagicMock:
    """Mock DraftProcessor."""
    processor = MagicMock(spec=["process"])
    processor.process = MagicMock(spec=[], side_effect=lambda text, **kwargs: text)
    return processor


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4000,
    )


@pytest.fixture
def service(
    mock_repo: AsyncMock,
    mock_pipeline: AsyncMock,
    mock_draft_processor: MagicMock,
    config: ResolvedModelConfig,
) -> WritingService:
    """WritingService with mocked dependencies (no tone service by default)."""
    return WritingService(
        repo=mock_repo,
        pipeline=mock_pipeline,
        draft_processor=mock_draft_processor,
        config=config,
    )
