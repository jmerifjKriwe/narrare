"""Unit tests for ContextAssembler — chapter text joining, KB extraction, genre.

Tests context assembly from chapters, KB entries, and novel metadata
into BetaReaderDeps for the beta reader agent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.analysis.context_assembler import ContextAssembler
from narrare.analysis.errors import ChapterNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chapter(
    chapter_id: UUID | None = None,
    title: str = "Test Chapter",
    content: str = "Test content with some words.",
    word_count: int = 5,
    position: int = 0,
    summary: str = "",
) -> SimpleNamespace:
    """Create a simple chapter-like object for testing.

    Uses SimpleNamespace to avoid SQLAlchemy model initialization issues.
    """
    return SimpleNamespace(
        id=chapter_id or uuid4(),
        novel_id=uuid4(),
        title=title,
        content=content,
        summary=summary,
        position=position,
        word_count=word_count,
    )


def _make_kb_entry(
    name: str = "Test",
    entity_type: str = "character",
    body: str = "A test entry",
) -> SimpleNamespace:
    """Create a simple KB entry-like object for testing."""
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        entity_type=entity_type,
        body=body,
    )


def _make_novel(genre: str = "Fantasy") -> SimpleNamespace:
    """Create a simple novel-like object for testing."""
    return SimpleNamespace(id=uuid4(), genre=genre)


def _make_assembler(
    chapters: list[SimpleNamespace] | None = None,
    kb_entries: list[SimpleNamespace] | None = None,
    novel_genre: str = "Fantasy",
) -> ContextAssembler:
    """Create a ContextAssembler with mocked dependencies."""
    chapter_repo = AsyncMock()
    chapter_repo.list_by_novel = AsyncMock(return_value=chapters or [])

    kb_entries_list = kb_entries or []
    kb_repo = AsyncMock()
    kb_repo.list_entries = AsyncMock(return_value=(kb_entries_list, len(kb_entries_list)))

    novel = _make_novel(novel_genre)
    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=novel)

    return ContextAssembler(
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        novel_repo=novel_repo,
    )


# ---------------------------------------------------------------------------
# Chapter text joining
# ---------------------------------------------------------------------------


class TestChapterTextJoining:
    """Multiple chapters are joined with separator."""

    async def test_single_chapter_text(self) -> None:
        """Single chapter text is included as-is."""
        ch = _make_chapter(content="Hello world")
        assembler = _make_assembler(chapters=[ch])

        deps = await assembler.build_context(novel_id=ch.novel_id, chapter_ids=[ch.id])

        assert deps.chapter_text == "Hello world"

    async def test_multiple_chapters_joined(self) -> None:
        """Multiple chapters are joined with --- separator."""
        ch1 = _make_chapter(content="Chapter one", position=0)
        ch2 = _make_chapter(content="Chapter two", position=1)
        assembler = _make_assembler(chapters=[ch1, ch2])

        deps = await assembler.build_context(novel_id=ch1.novel_id, chapter_ids=[ch1.id, ch2.id])

        assert deps.chapter_text == "Chapter one\n\n---\n\nChapter two"


# ---------------------------------------------------------------------------
# Word count calculation
# ---------------------------------------------------------------------------


class TestWordCountCalculation:
    """Word count is summed across all target chapters."""

    async def test_word_count_summed(self) -> None:
        """Word count reflects sum of all chapter word_counts."""
        ch1 = _make_chapter(word_count=2000, position=0)
        ch2 = _make_chapter(word_count=1500, position=1)
        assembler = _make_assembler(chapters=[ch1, ch2])

        deps = await assembler.build_context(novel_id=ch1.novel_id, chapter_ids=[ch1.id, ch2.id])

        assert deps.word_count == 3500


# ---------------------------------------------------------------------------
# Previous chapter summaries
# ---------------------------------------------------------------------------


class TestPreviousChapterSummaries:
    """Summaries of chapters before the targets are included."""

    async def test_previous_summaries_included(self) -> None:
        """Chapters before the target have their summaries included."""
        prev = _make_chapter(summary="Previous summary", position=0)
        target = _make_chapter(position=1)
        assembler = _make_assembler(chapters=[prev, target])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert "Previous summary" in deps.previous_chapter_summaries

    async def test_later_chapters_excluded(self) -> None:
        """Chapters after the target are not included as previous."""
        target = _make_chapter(position=0)
        after = _make_chapter(summary="After summary", position=1)
        assembler = _make_assembler(chapters=[target, after])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert "After summary" not in deps.previous_chapter_summaries

    async def test_max_three_previous(self) -> None:
        """At most 3 previous chapters are included."""
        chapters = [_make_chapter(summary=f"Ch{i}", position=i) for i in range(5)]
        target = _make_chapter(position=5)
        chapters.append(target)
        assembler = _make_assembler(chapters=chapters)

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert len(deps.previous_chapter_summaries) == 3


# ---------------------------------------------------------------------------
# KB entry extraction
# ---------------------------------------------------------------------------


class TestKBEntryExtraction:
    """Characters and locations are extracted from KB."""

    async def test_characters_extracted(self) -> None:
        """Character KB entries are included in kb_characters."""
        char = _make_kb_entry(name="Alice", entity_type="character", body="Protagonist")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[char])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert len(deps.kb_characters) == 1
        assert deps.kb_characters[0]["name"] == "Alice"

    async def test_locations_extracted(self) -> None:
        """Location KB entries are included in kb_locations."""
        loc = _make_kb_entry(name="Castle", entity_type="location", body="Main setting")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[loc])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert len(deps.kb_locations) == 1
        assert deps.kb_locations[0]["name"] == "Castle"

    async def test_other_entity_types_ignored(self) -> None:
        """Non-character, non-location entries are ignored."""
        concept = _make_kb_entry(name="Magic", entity_type="concept")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[concept])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert len(deps.kb_characters) == 0
        assert len(deps.kb_locations) == 0


# ---------------------------------------------------------------------------
# Genre resolution
# ---------------------------------------------------------------------------


class TestGenreResolution:
    """Genre is fetched from the novel metadata."""

    async def test_genre_from_novel(self) -> None:
        """Genre matches the novel's genre field."""
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], novel_genre="Sci-Fi")

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert deps.genre == "Sci-Fi"


# ---------------------------------------------------------------------------
# Chapter not found
# ---------------------------------------------------------------------------


class TestChapterNotFound:
    """Missing chapter IDs raise ChapterNotFoundError."""

    async def test_missing_chapter_raises(self) -> None:
        """Requesting a non-existent chapter raises error."""
        assembler = _make_assembler(chapters=[])

        with pytest.raises(ChapterNotFoundError):
            await assembler.build_context(novel_id=uuid4(), chapter_ids=[uuid4()])
