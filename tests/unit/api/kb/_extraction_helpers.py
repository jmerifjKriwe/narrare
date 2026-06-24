"""Shared fakes and helpers for ExtractionService unit tests.

Extracted from test_extraction_service.py per RULE-04 (file size limits).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from narrare.kb.extraction_service import ExtractionService
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig


# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry with configurable get_model."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


class FakeComposer:
    """Fake PromptComposer returning configurable system prompt."""

    def __init__(self) -> None:
        self.build = AsyncMock(
            return_value=ComposedPrompt(system="Test system prompt.", user="Test user.")
        )


class FakeChapterRepo:
    """Fake ChapterRepositoryProtocol."""

    def __init__(self) -> None:
        self.get_by_id = AsyncMock()


class FakeKBRepo:
    """Fake KBRepositoryProtocol."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(return_value=([], 0))


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_service(
    registry: FakeModelRegistry | object,
    config: ResolvedModelConfig,
    chapter_repo: FakeChapterRepo | object,
    kb_repo: FakeKBRepo | object,
    composer: FakeComposer | object,
) -> ExtractionService:
    """Build an ExtractionService with the given (mocked) dependencies."""
    return ExtractionService(
        registry=registry,  # type: ignore[arg-type]
        config=config,
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
        composer=composer,  # type: ignore[arg-type]
    )


def make_chapter(
    chapter_id: UUID | None = None,
    content: str = "Anna walked into the dark forest. The trees whispered.",
    title: str = "Chapter 1",
) -> MagicMock:
    """Create a mock chapter with spec (RULE-TEST-01)."""
    chapter = MagicMock(spec=["id", "content", "title"])
    chapter.id = chapter_id or uuid4()
    chapter.content = content
    chapter.title = title
    return chapter


def make_extraction_output(
    items: list[ExtractionItem] | None = None,
    notes: str = "",
) -> ExtractionOutput:
    """Create a sample ExtractionOutput with sensible defaults."""
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
