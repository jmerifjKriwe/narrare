"""Unit tests for ExtractionService — dedup & graceful degradation.

Tests:
- Existing entity names passed to ExtractionAgent for dedup
- KB repo failure → graceful degradation (empty dedup, extraction continues)
- System prompt built via PromptComposer with KB_EXTRACT intent
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.llm import LLMIntent, ResolvedModelConfig
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


def _make_chapter(
    content: str = "Anna walked into the dark forest.",
    title: str = "Chapter 1",
) -> MagicMock:
    """Create a mock chapter object."""
    chapter = MagicMock(spec=["id", "content", "title"])
    chapter.id = uuid4()
    chapter.content = content
    chapter.title = title
    return chapter


def _make_service(
    registry: MagicMock,
    config: ResolvedModelConfig,
    chapter_repo: MagicMock,
    kb_repo: MagicMock,
    composer: MagicMock,
) -> ExtractionService:
    """Create an ExtractionService with test dependencies."""
    from ._extraction_helpers import permissive_novel_gate

    return ExtractionService(
        registry=registry,
        config=config,
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        composer=composer,
        novel_repo=permissive_novel_gate(),
    )


# ---------------------------------------------------------------------------
# Dedup: existing entity names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_passes_existing_entity_names_for_dedup(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """Existing KB entries are passed to ExtractionAgent as dedup names."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    mock_entry_1 = MagicMock(spec=["name"])
    mock_entry_1.name = "Anna"
    mock_entry_2 = MagicMock(spec=["name"])
    mock_entry_2.name = "The Tower"
    mock_kb_repo.list_entries.return_value = ([mock_entry_1, mock_entry_2], 2)

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = _make_service(
            mock_registry,
            config,
            mock_chapter_repo,
            mock_kb_repo,
            mock_composer,
        )

        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        mock_kb_repo.list_entries.assert_awaited_once()
        mock_agent.run.assert_awaited_once()
        deps = mock_agent.run.call_args.kwargs["deps"]
        assert "Anna" in deps.existing_entity_names
        assert "The Tower" in deps.existing_entity_names


# ---------------------------------------------------------------------------
# Graceful degradation: KB repo failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_proceeds_when_kb_repo_fails(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """KB repo failure → empty dedup list, extraction continues."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter
    mock_kb_repo.list_entries.side_effect = RuntimeError("DB connection lost")

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = _make_service(
            mock_registry,
            config,
            mock_chapter_repo,
            mock_kb_repo,
            mock_composer,
        )

        result = await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        assert result is not None
        assert len(result.results) == 1
        deps = mock_agent.run.call_args.kwargs["deps"]
        assert deps.existing_entity_names == []


# ---------------------------------------------------------------------------
# System prompt: PromptComposer usage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_uses_composer_for_system_prompt(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """PromptComposer.build() is called with KB_EXTRACT intent."""
    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = _make_service(
            mock_registry,
            config,
            mock_chapter_repo,
            mock_kb_repo,
            mock_composer,
        )

        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        mock_composer.build.assert_awaited_once()
        intent_arg = mock_composer.build.call_args.args[0]
        assert intent_arg == LLMIntent.KB_EXTRACT


@pytest.mark.asyncio
async def test_extract_propagates_prompt_resolution_error(
    mock_registry: MagicMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: MagicMock,
    mock_kb_repo: MagicMock,
    mock_composer: MagicMock,
) -> None:
    """When PromptComposer cannot resolve the bundled prompt, fail visibly."""
    from narrare_core.shared.errors import PromptNotFoundError

    chapter = _make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter
    mock_composer.build.side_effect = PromptNotFoundError(
        category="kb",
        language="en",
        mode="extract",
    )

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=_make_extraction_output())
        MockAgent.return_value = mock_agent

        service = _make_service(
            mock_registry,
            config,
            mock_chapter_repo,
            mock_kb_repo,
            mock_composer,
        )

        with pytest.raises(PromptNotFoundError):
            await service.extract_from_chapter(
                novel_id=uuid4(),
                chapter_id=chapter.id,
                user_id=uuid4(),
            )

        MockAgent.assert_not_called()


def _make_extraction_output(
    items: list[ExtractionItem] | None = None,
    notes: str = "",
) -> ExtractionOutput:
    """Create a test ExtractionOutput."""
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
