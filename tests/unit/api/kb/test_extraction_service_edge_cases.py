"""Unit tests for ExtractionService — content edge cases.

Split from test_extraction_service.py per RULE-04 (file size limit).

Tests:
- Very long chapter content
- Unicode characters in content
- HTML entities in content
- Entity names with None values filtered in dedup
- Whitespace-only content raises ValueError
- Empty extraction results from agent
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt

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
            ),
        ]
    return ExtractionOutput(results=items, analysis_notes=notes)


# ---------------------------------------------------------------------------
# Very long content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_handles_very_long_content(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Very long chapter content (50k chars) is passed to the agent."""
    long_content = "The forest was dark. " * 2500  # ~50k chars
    chapter = _make_chapter(content=long_content, title="Long Chapter")
    mock_chapter_repo.get_by_id.return_value = chapter

    expected_output = _make_extraction_output(
        items=[
            ExtractionItem(
                item_type="new_entity",
                entity_type="location",
                name="Dark Forest",
                confidence=0.9,
                source_text="The forest was dark",
            ),
        ],
        notes="Extracted from long content.",
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

        assert len(result.results) == 1
        # Verify the full content was passed to the agent
        prompt_arg = mock_agent.run.call_args.kwargs["prompt"]
        assert len(prompt_arg) > 40000


# ---------------------------------------------------------------------------
# Special characters in content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_handles_unicode_content(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Chapter content with unicode characters is handled correctly."""
    unicode_content = "Hélène naïvely café — «Bonjour!» 🏰✨"
    chapter = _make_chapter(content=unicode_content, title="Unicode Chapter")
    mock_chapter_repo.get_by_id.return_value = chapter

    expected_output = _make_extraction_output(
        items=[
            ExtractionItem(
                item_type="new_entity",
                entity_type="location",
                name="Castle",
                confidence=0.85,
                source_text="🏰✨",
            ),
        ],
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

        assert len(result.results) == 1
        assert result.results[0].name == "Castle"
        # Verify unicode content was passed through
        prompt_arg = mock_agent.run.call_args.kwargs["prompt"]
        assert "Hélène" in prompt_arg
        assert "🏰" in prompt_arg


@pytest.mark.asyncio
async def test_extract_handles_html_entities_in_content(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Chapter content with HTML entities is passed through to the agent."""
    html_content = "She said &ldquo;Hello&rdquo; and walked to the <em>old tower</em>."
    chapter = _make_chapter(content=html_content, title="HTML Chapter")
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        prompt_arg = mock_agent.run.call_args.kwargs["prompt"]
        assert "&ldquo;" in prompt_arg
        assert "<em>" in prompt_arg


# ---------------------------------------------------------------------------
# Entity names with None values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_filters_none_entity_names(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """KB entries with None names are excluded from dedup list."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    # Simulate entries where some have None names
    entry_with_name = MagicMock(spec=["name"])
    entry_with_name.name = "Anna"
    entry_without_name = MagicMock(spec=["name"])
    entry_without_name.name = None
    entry_empty_name = MagicMock(spec=["name"])
    entry_empty_name.name = ""

    mock_kb_repo.list_entries.return_value = (
        [entry_with_name, entry_without_name, entry_empty_name],
        3,
    )

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        deps = mock_agent.run.call_args.kwargs["deps"]
        # None and empty names should be filtered out
        assert "Anna" in deps.existing_entity_names
        assert None not in deps.existing_entity_names
        assert "" not in deps.existing_entity_names


# ---------------------------------------------------------------------------
# Whitespace-only content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_raises_for_whitespace_only_content(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Chapter with only whitespace raises ValueError."""
    chapter = _make_chapter(content="   \n\t  \n  ", title="Whitespace Chapter")
    mock_chapter_repo.get_by_id.return_value = chapter

    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    with pytest.raises(ValueError, match="has no content"):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# ExtractionOutput with empty results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_empty_results_for_minimal_content(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Agent returning empty results list is handled correctly."""
    chapter = _make_chapter(content="A single word.")
    mock_chapter_repo.get_by_id.return_value = chapter

    empty_output = ExtractionOutput(results=[], analysis_notes="No entities found.")

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=empty_output)
        MockAgent.return_value = mock_agent

        service = make_service(
            mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer
        )
        result = await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        assert len(result.results) == 0
        assert result.analysis_notes == "No entities found."
