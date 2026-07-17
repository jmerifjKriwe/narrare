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
    """Create a simple KB entry-like object for testing.

    Carries every field the canonical ``kb_entry_to_kb_entity`` mapper reads
    (ADR-067) so the :class:`KBContextProvider` renders the entry through the
    ADR-050 envelope rather than degrading to empty.
    """
    from datetime import UTC, datetime

    return SimpleNamespace(
        id=uuid4(),
        name=name,
        entity_type=entity_type,
        body=body,
        updated_at=datetime.now(tz=UTC),
        metadata_={},
        status="draft",
        source="manual",
        review_status="approved",
    )


def _make_novel(genre: str = "Fantasy") -> SimpleNamespace:
    """Create a simple novel-like object for testing."""
    return SimpleNamespace(id=uuid4(), genre=genre)


def _make_assembler(
    chapters: list[SimpleNamespace] | None = None,
    kb_entries: list[SimpleNamespace] | None = None,
    novel_genre: str = "Fantasy",
) -> ContextAssembler:
    """Create a ContextAssembler with mocked dependencies.

    KB context is routed through a real :class:`KBContextProvider` wrapping a
    mocked ``KBRepository`` (the canonical ADR-067 path). ``kb_entries`` are
    seeded into the mocked repo so the provider renders them through the
    ADR-050 envelope.
    """
    chapter_repo = AsyncMock()
    chapter_repo.list_by_novel = AsyncMock(return_value=chapters or [])

    kb_entries_list = kb_entries or []
    kb_repo = AsyncMock()
    kb_repo.list_entries = AsyncMock(return_value=(kb_entries_list, len(kb_entries_list)))

    novel = _make_novel(novel_genre)
    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=novel)
    novel_repo.get = AsyncMock(return_value=novel)

    # Canonical KB-context provider (ADR-067) wrapping the mocked KB repo.
    from narrare.kb._context_provider import KBContextProvider

    kb_context_provider = KBContextProvider(kb_repo=kb_repo, relationship_repo=None)

    return ContextAssembler(
        chapter_repo=chapter_repo,
        kb_context_provider=kb_context_provider,
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

    async def test_fallback_content_truncated_to_limit(self) -> None:
        """Chapter without summary falls back to truncated content.

        When a previous chapter has no stored summary, its content is
        truncated to kb_summary_truncation chars (default 200). This is
        a different use case from KB entity bodies and keeps its behavior.
        """
        long_content = "B" * 500
        prev = _make_chapter(summary="", content=long_content, position=0)
        target = _make_chapter(position=1)
        assembler = _make_assembler(chapters=[prev, target])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert len(deps.previous_chapter_summaries) == 1
        assert deps.previous_chapter_summaries[0] == "B" * 200


# ---------------------------------------------------------------------------
# KB entry extraction
# ---------------------------------------------------------------------------


class TestKBEntryExtraction:
    """Characters and locations are rendered through the canonical KB envelope."""

    async def test_characters_extracted(self) -> None:
        """Character KB entries render into kb_characters (envelope text)."""
        char = _make_kb_entry(name="Alice", entity_type="character", body="Protagonist")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[char])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert "Alice" in deps.kb_characters
        assert "### Character: Alice" in deps.kb_characters

    async def test_locations_extracted(self) -> None:
        """Location KB entries render into kb_locations (envelope text)."""
        loc = _make_kb_entry(name="Castle", entity_type="location", body="Main setting")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[loc])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert "Castle" in deps.kb_locations
        assert "### Location: Castle" in deps.kb_locations

    async def test_other_entity_types_ignored(self) -> None:
        """Non-character, non-location entries render to empty slots."""
        concept = _make_kb_entry(name="Magic", entity_type="concept")
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[concept])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert deps.kb_characters == ""
        assert deps.kb_locations == ""


# ---------------------------------------------------------------------------
# KB body pass-through (no pre-truncation)
# ---------------------------------------------------------------------------


class TestKBBodyPassThrough:
    """KB entity bodies are rendered in full for downstream budget truncation.

    The token-aware truncation still happens in ``AnalysisContextAssembler``
    (``build_budgeted_prompt``). The provider renders the full body into the
    envelope ``.text``; pre-truncating here would starve the budget system of
    data it could otherwise fit within the KB-context tier.
    """

    async def test_long_body_not_truncated(self) -> None:
        """Entity body longer than kb_summary_truncation is rendered in full."""
        long_body = "A" * 500  # 500 chars, well over the 200-char default
        char = _make_kb_entry(name="Alice", entity_type="character", body=long_body)
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[char])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert long_body in deps.kb_characters

    async def test_short_body_returned_as_is(self) -> None:
        """Entity body shorter than kb_summary_truncation is rendered unchanged."""
        short_body = "A brief biography."
        char = _make_kb_entry(name="Bob", entity_type="character", body=short_body)
        target = _make_chapter()
        assembler = _make_assembler(chapters=[target], kb_entries=[char])

        deps = await assembler.build_context(novel_id=target.novel_id, chapter_ids=[target.id])

        assert short_body in deps.kb_characters


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
