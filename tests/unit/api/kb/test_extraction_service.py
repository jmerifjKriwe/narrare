"""Unit tests for ExtractionService — core extraction flow.

Happy path, chapter-not-found, empty-content.

CR-01 governance tests (prompt composition, typed error propagation)
live in test_extraction_service_governance.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.agents.extraction_types import ExtractionItem
from narrare_core.llm import ResolvedModelConfig

from ._extraction_helpers import (
    FakeChapterRepo,
    FakeComposer,
    FakeKBRepo,
    FakeModelRegistry,
    make_chapter,
    make_extraction_output,
    make_service,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def mock_registry() -> FakeModelRegistry:
    return FakeModelRegistry()


@pytest.fixture
def mock_composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def mock_chapter_repo() -> FakeChapterRepo:
    return FakeChapterRepo()


@pytest.fixture
def mock_kb_repo() -> FakeKBRepo:
    return FakeKBRepo()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_returns_output(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """Happy path: valid chapter content returns ExtractionOutput."""
    chapter = make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    expected_output = make_extraction_output(
        items=[
            ExtractionItem(
                item_type="new_entity",
                entity_type="location",
                name="Dark Forest",
                confidence=0.95,
                source_text="the dark forest",
            ),
            ExtractionItem(
                item_type="new_entity",
                entity_type="character",
                name="Anna",
                confidence=0.98,
                source_text="Anna walked into",
            ),
        ],
        notes="Found 2 entities.",
    )

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=expected_output)
        MockAgent.return_value = mock_agent
        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        result = await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        mock_chapter_repo.get_by_id.assert_awaited_once()
        assert len(result.results) == 2
        assert result.results[0].name == "Dark Forest"
        assert result.analysis_notes == "Found 2 entities."
        MockAgent.assert_called_once()
        assert mock_agent.run.call_args.kwargs["prompt"] == chapter.content


@pytest.mark.asyncio
async def test_extract_from_chapter_passes_ids(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """get_by_id receives chapter_id AND novel_id."""
    novel_id, chapter_id = uuid4(), uuid4()
    chapter = make_chapter(chapter_id=chapter_id)
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_extraction_output())
        MockAgent.return_value = mock_agent
        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        await service.extract_from_chapter(
            novel_id=novel_id,
            chapter_id=chapter_id,
            user_id=uuid4(),
        )
        mock_chapter_repo.get_by_id.assert_awaited_once_with(chapter_id, novel_id)


# ---------------------------------------------------------------------------
# Model resolution wiring — single prepare() resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_resolves_model_exactly_once_via_prepare(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """Regression: the historical duplicate ``get_model`` call is dead.

    Before the ``ModelRegistry.prepare`` migration the service resolved the
    model TWICE via two direct ``get_model`` calls and assembled
    ``model_settings`` separately. Now one ``prepare()`` call composes
    exactly one model resolution with the settings/limits triple, and the
    agent receives the model from that single resolution.
    """
    chapter = make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_extraction_output())
        MockAgent.return_value = mock_agent
        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    assert mock_registry.get_model.await_count == 1
    assert MockAgent.call_args.kwargs["model"] is mock_registry.get_model.return_value


# ---------------------------------------------------------------------------
# Error: chapter not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_raises_when_chapter_not_found(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """Chapter not found raises ValueError."""
    mock_chapter_repo.get_by_id.return_value = None
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)
    with pytest.raises(ValueError, match="not found"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=uuid4(),
            user_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Error: empty chapter content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_raises_when_content_empty(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """Empty content raises ValueError."""
    chapter = make_chapter(content="   ", title="Empty")
    mock_chapter_repo.get_by_id.return_value = chapter
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)
    with pytest.raises(ValueError, match="has no content"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_extract_from_chapter_raises_when_content_none(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """None content raises ValueError."""
    chapter = make_chapter(content=None, title="No Content")  # type: ignore[arg-type]
    mock_chapter_repo.get_by_id.return_value = chapter
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)
    with pytest.raises(ValueError, match="has no content"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )
