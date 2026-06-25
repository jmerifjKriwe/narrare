"""Shared pytest fixtures for planning unit tests.

These fixtures are automatically discovered by pytest and available
to all test files in this directory.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from narrare.planning.timeline_extraction_service import TimelineExtractionService
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.planning._timeline_test_helpers import FakeComposer


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def model_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


@pytest.fixture
def composer() -> FakeComposer:
    """Fake PromptComposer for DI wiring (ADR-054 Mode 1).

    Mirrors the ``composer`` fixture used by the analysis-service tests. The
    extraction service routes its system prompt through ``compose_invocation``
    (which calls ``composer.build``); this fake returns a stub
    ``ComposedPrompt`` so the per-chapter agent receives a system prompt
    without touching real prompt assets.
    """
    return FakeComposer()


@pytest.fixture
def service_with_config(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    mock_event_repo: AsyncMock,
    model_config: ResolvedModelConfig,
    composer: FakeComposer,
) -> TimelineExtractionService:
    """Service with model config and event repo for extraction tests."""
    return TimelineExtractionService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_config=model_config,
        composer=composer,  # type: ignore[arg-type]
        event_repo=mock_event_repo,
    )


@pytest.fixture
def service_no_config(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
) -> TimelineExtractionService:
    """Service without model config — should raise ConfigurationError."""
    return TimelineExtractionService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_config=None,
    )
