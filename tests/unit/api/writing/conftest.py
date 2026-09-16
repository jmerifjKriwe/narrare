"""Shared fixtures for writing service unit tests."""

from __future__ import annotations

import uuid
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from narrare.writing.contracts import GenerationRepositoryProtocol
from narrare.writing.service import WritingService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.writing.pipeline import WritingPipeline


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock GenerationRepository."""
    repo = AsyncMock(spec=GenerationRepositoryProtocol)
    repo.create = AsyncMock(return_value=uuid.uuid4())
    repo.create_if_no_active = AsyncMock(return_value=uuid.uuid4())
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
def mock_chapter_repo() -> AsyncMock:
    """Mock ChapterRepository — gate-open for non-ownership tests.

    The returned chapter binds to ANY addressed novel (``mock.ANY``) so the
    S6 ``verify_chapter_access`` gate passes for whatever random
    ``(chapter_id, novel_id)`` pair a behavior test draws.  The ownership
    matrix itself lives in ``test_generation_access_matrix.py`` with real
    fakes.
    """
    from tests.factories import make_chapter

    repo = AsyncMock(spec=["get"])
    repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    return repo


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    """Mock NovelRepository — every novel belongs to the caller (gate-open)."""
    from tests.factories import make_novel

    repo = AsyncMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=make_novel())
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
    mock_chapter_repo: AsyncMock,
    mock_novel_repo: AsyncMock,
) -> WritingService:
    """WritingService with mocked dependencies (no tone service by default)."""
    from tests.unit.api.writing._writing_factories import make_static_runtime_factory

    return WritingService(
        repo=mock_repo,
        # ADR-086 L37: the service composes its runtime at first use; the
        # fake chain pins a fixed runtime (render- and outcome-inert —
        # same config/pipeline the eager factory passed).
        runtime_factory=make_static_runtime_factory(mock_pipeline, config),
        draft_processor=mock_draft_processor,
        chapter_repo=mock_chapter_repo,
        novel_repo=mock_novel_repo,
    )
