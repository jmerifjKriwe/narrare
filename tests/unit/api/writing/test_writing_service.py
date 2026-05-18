"""Unit tests for WritingService — mocked dependencies.

Tests verify service business logic without touching the database,
LLM gateway, or prompt composer.  All dependencies are mocked.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.schemas import (
    GenerateRequest,
    GenerationModeEnum,
)
from narrare.writing.service import WritingService
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.shared.errors import ConflictError, ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ResolvedModelConfig:
    """Create a default ResolvedModelConfig for tests."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4000,
    )


def _make_request(**overrides: Any) -> GenerateRequest:
    """Create a GenerateRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "mode": GenerationModeEnum.FULL_DRAFT,
        "prompt": "Write a dramatic scene",
        "outline": None,
        "auto_continue": False,
    }
    defaults.update(overrides)
    return GenerateRequest(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock GenerationRepository."""
    repo = AsyncMock()
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
    pipeline = AsyncMock()
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
    return _make_config()


@pytest.fixture
def service(
    mock_repo: AsyncMock,
    mock_pipeline: AsyncMock,
    mock_draft_processor: MagicMock,
    config: ResolvedModelConfig,
) -> WritingService:
    """WritingService with mocked dependencies."""
    return WritingService(
        repo=mock_repo,
        pipeline=mock_pipeline,
        draft_processor=mock_draft_processor,
        config=config,
    )


# ---------------------------------------------------------------------------
# start_generation
# ---------------------------------------------------------------------------


class TestStartGeneration:
    async def test_start_generation_with_valid_input(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() creates a request and returns GenerateResponse."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = _make_request()

        response = await service.start_generation(
            chapter_id,
            novel_id,
            user_id,
            request,
        )

        assert response.status == "pending"
        assert response.mode == "full_draft"
        assert isinstance(response.request_id, uuid.UUID)
        mock_repo.create.assert_called_once()

    async def test_start_generation_with_concurrent_request_raises_conflict(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() raises ConflictError when a request is active."""
        mock_repo.get_active_for_chapter.return_value = MagicMock(spec=["id"])

        with pytest.raises(ConflictError):
            await service.start_generation(
                uuid.uuid4(),
                uuid.uuid4(),
                str(uuid.uuid4()),
                _make_request(),
            )

    async def test_start_generation_without_input_raises_validation(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() raises ValidationError without prompt/outline/auto."""
        request = GenerateRequest(
            mode=GenerationModeEnum.FULL_DRAFT,
            prompt=None,
            outline=None,
            auto_continue=False,
            word_target=None,
            tone="balanced",
            language="en",
        )

        with pytest.raises(ValidationError):
            await service.start_generation(
                uuid.uuid4(),
                uuid.uuid4(),
                str(uuid.uuid4()),
                request,
            )

    async def test_start_generation_with_outline_only(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() accepts outline as sole input."""
        request = _make_request(prompt=None, outline="Chapter outline here")
        response = await service.start_generation(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            request,
        )
        assert response.status == "pending"

    async def test_start_generation_with_auto_continue(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() accepts auto_continue as sole input."""
        request = _make_request(prompt=None, auto_continue=True)
        response = await service.start_generation(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            request,
        )
        assert response.status == "pending"
