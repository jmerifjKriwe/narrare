"""Unit tests for ExtractionService — error propagation.

Split from test_extraction_service.py per RULE-04 (file size limit).

Tests:
- ExtractionAgent RuntimeError propagation
- ExtractionAgent UnexpectedModelBehavior propagation
- Model registry error propagation
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt

from ._extraction_helpers import FakePrepareMixin

# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock — RULE-TEST-01)
# ---------------------------------------------------------------------------


class _FakeModelRegistry(FakePrepareMixin):
    """Fake ModelRegistry with configurable get_model + prepare."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


class _FakeComposer:
    """Fake PromptComposer returning configurable system prompt."""

    def __init__(self) -> None:
        self.build = AsyncMock(
            return_value=ComposedPrompt(system="Test system prompt.", user="Test user.")
        )


class _FakeChapterRepo:
    """Fake ChapterRepositoryProtocol."""

    def __init__(self) -> None:
        self.get_by_id = AsyncMock()


class _FakeKBRepo:
    """Fake KBRepositoryProtocol."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(return_value=([], 0))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def mock_registry() -> _FakeModelRegistry:
    return _FakeModelRegistry()


@pytest.fixture
def mock_composer() -> _FakeComposer:
    return _FakeComposer()


@pytest.fixture
def mock_chapter_repo() -> _FakeChapterRepo:
    return _FakeChapterRepo()


@pytest.fixture
def mock_kb_repo() -> _FakeKBRepo:
    return _FakeKBRepo()


def make_service(
    registry: Any,
    config: ResolvedModelConfig,
    chapter_repo: Any,
    kb_repo: Any,
    composer: Any,
) -> ExtractionService:
    from ._extraction_helpers import permissive_novel_gate

    return ExtractionService(
        registry=registry,
        config=config,
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        composer=composer,
        novel_repo=permissive_novel_gate(),
    )


def _make_chapter(
    chapter_id: UUID | None = None,
    content: str = "Anna walked into the dark forest. The trees whispered.",
    title: str = "Chapter 1",
) -> MagicMock:
    chapter = MagicMock(spec=["id", "content", "title"])
    chapter.id = chapter_id or uuid4()
    chapter.content = content
    chapter.title = title
    return chapter


# ---------------------------------------------------------------------------
# Agent error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_propagates_agent_runtime_error(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """When ExtractionAgent.run() raises RuntimeError, it propagates."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM provider unavailable"))
        MockAgent.return_value = mock_agent

        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )

        with pytest.raises(RuntimeError, match="LLM provider unavailable"):
            await service.extract_from_chapter(
                novel_id=uuid4(),
                chapter_id=chapter.id,
                user_id=uuid4(),
            )


@pytest.mark.asyncio
async def test_extract_propagates_agent_model_error(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """When ExtractionAgent.run() raises UnexpectedModelBehavior, it propagates."""
    from pydantic_ai import UnexpectedModelBehavior

    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(
            side_effect=UnexpectedModelBehavior("Model returned invalid JSON")
        )
        MockAgent.return_value = mock_agent

        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )

        with pytest.raises(UnexpectedModelBehavior, match="invalid JSON"):
            await service.extract_from_chapter(
                novel_id=uuid4(),
                chapter_id=chapter.id,
                user_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# Model registry error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_propagates_registry_error(
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """When ModelRegistry.get_model() fails, the error propagates."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    failing_registry = _FakeModelRegistry()
    failing_registry.get_model = AsyncMock(side_effect=RuntimeError("No model available"))

    service = make_service(failing_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    with pytest.raises(RuntimeError, match="No model available"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )
