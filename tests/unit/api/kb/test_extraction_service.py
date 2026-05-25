"""Unit tests for ExtractionService — core extraction flow.

Happy path, chapter-not-found, empty-content.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.llm.intents import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock — RULE-TEST-01)
# ---------------------------------------------------------------------------


class _FakeModelRegistry:
    """Fake ModelRegistry with configurable get_model."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


class _FakeComposer:
    """Fake PromptComposer returning configurable system prompt."""

    def __init__(self) -> None:
        self.build = AsyncMock(return_value=MagicMock(spec=object, system="Test system prompt."))


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
    registry: MagicMock,
    config: ResolvedModelConfig,
    chapter_repo: MagicMock,
    kb_repo: MagicMock,
    composer: MagicMock,
) -> ExtractionService:
    return ExtractionService(
        registry=registry,
        config=config,
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        composer=composer,
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


def _make_extraction_output(
    items: list[ExtractionItem] | None = None,
    notes: str = "",
) -> ExtractionOutput:
    if items is None:
        items = [
            ExtractionItem(
                item_type="new_entity",
                entity_type="location",
                name="Dark Forest",
                confidence=0.95,
                source_text="the dark forest",
            )
        ]
    return ExtractionOutput(results=items, analysis_notes=notes)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_returns_output(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Happy path: valid chapter content returns ExtractionOutput."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    expected_output = _make_extraction_output(
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
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """get_by_id receives chapter_id AND novel_id."""
    novel_id, chapter_id = uuid4(), uuid4()
    chapter = _make_chapter(chapter_id=chapter_id)
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
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
# Error: chapter not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_raises_when_chapter_not_found(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
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
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Empty content raises ValueError."""
    chapter = _make_chapter(content="   ", title="Empty")
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
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """None content raises ValueError."""
    chapter = _make_chapter(content=None, title="No Content")  # type: ignore[arg-type]
    mock_chapter_repo.get_by_id.return_value = chapter
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)
    with pytest.raises(ValueError, match="has no content"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )
