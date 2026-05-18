"""Tests for writing/context_assembler.py — overflow, bypass, ranking, edge cases.

Split from test_context_assembler.py for RULE-04 compliance.

Covers:
1. Budget overflow — large chapter content truncated to fit
2. Pinned bypass — pinned items included regardless of budget
3. Relevance ranking — entities sorted by weighted score
4. Edge cases — empty input, custom token counter, frontmatter parsing
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import yaml

from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity, RecentChapter


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
    content: str = "A brave warrior.",
    similarity: float = 0.5,
    frequency: float = 0.5,
    recency: float = 0.5,
    is_pinned: bool = False,
    is_referenced: bool = False,
) -> KBEntity:
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
        similarity_score=similarity,
        frequency_score=frequency,
        recency_score=recency,
        is_pinned=is_pinned,
        is_referenced=is_referenced,
    )


def _chapter(
    title: str = "Chapter 1",
    full_text: str = "Once upon a time there was a brave warrior.",
    summary: str = "A warrior's introduction.",
    position: int = 1,
) -> RecentChapter:
    return RecentChapter(
        chapter_id=uuid4(),
        title=title,
        full_text=full_text,
        summary=summary,
        position=position,
    )


def _frontmatter(**fields: object) -> str:
    yaml_str = yaml.dump(dict(fields), default_flow_style=False)
    return f"---\n{yaml_str}---\n"


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    return WritingContextAssembler(total_budget=6000)


class TestBudgetOverflow:
    """Large chapter content truncated to fit budget."""

    @pytest.mark.asyncio
    async def test_large_content_is_truncated(self) -> None:
        tiny = WritingContextAssembler(total_budget=100)
        large_content = "word " * 500

        ctx = await tiny.assemble(chapter_content=large_content)
        words_in_result = ctx.chapter_content.split()
        assert len(words_in_result) < 500

    @pytest.mark.asyncio
    async def test_overflow_from_tier1_flows_to_tier2(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        chapters = [
            _chapter("Ch1", "Full text of chapter one here.", "Summary.", 1),
        ]

        ctx = await assembler.assemble(
            chapter_content="Short.",
            recent_chapters=chapters,
        )
        assert "Full text of chapter one here." in ctx.recent_chapters

    @pytest.mark.asyncio
    async def test_recent_chapters_uses_summaries_when_full_too_long(
        self,
    ) -> None:
        small = WritingContextAssembler(total_budget=200)
        long_text = " ".join(f"word{i}" for i in range(200))
        chapters = [
            _chapter("Ch1", long_text, "Short summary.", 1),
        ]

        ctx = await small.assemble(
            chapter_content="Content.",
            recent_chapters=chapters,
        )
        assert "Short summary." in ctx.recent_chapters


class TestPinnedBypass:
    """Pinned items included regardless of budget."""

    @pytest.mark.asyncio
    async def test_pinned_always_included_with_tiny_budget(self) -> None:
        tiny = WritingContextAssembler(total_budget=10)
        entities = [
            _entity("char-1", "character", "Alice", "A warrior.", is_pinned=True),
        ]

        ctx = await tiny.assemble(chapter_content="x", kb_entities=entities)
        assert ctx.kb_pinned != ""
        assert "Alice" in ctx.kb_pinned

    @pytest.mark.asyncio
    async def test_pinned_entities_not_in_suggested(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Pinned.", is_pinned=True),
            _entity("char-2", "character", "Bob", "Not pinned."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        assert "Alice" in ctx.kb_pinned
        assert "Alice" not in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_multiple_pinned_types(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "A warrior.", is_pinned=True),
            _entity("loc-1", "location", "Castle", "A fortress.", is_pinned=True),
            _entity("fac-1", "faction", "Rebels", "Fighters.", is_pinned=True),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        assert "Alice" in ctx.kb_pinned
        assert "Castle" in ctx.kb_pinned
        assert "Rebels" in ctx.kb_pinned


class TestRelevanceRanking:
    """Entities sorted by weighted relevance score."""

    @pytest.mark.asyncio
    async def test_higher_relevance_appears_first(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("low", "character", "Zara", "Low.", 0.1, 0.1, 0.1),
            _entity("high", "character", "Alice", "High.", 0.9, 0.9, 0.9),
            _entity("mid", "character", "Bob", "Mid.", 0.5, 0.5, 0.5),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        alice_pos = ctx.kb_suggested.find("Alice")
        zara_pos = ctx.kb_suggested.find("Zara")
        assert alice_pos < zara_pos

    def test_relevance_score_weighted_correctly(self) -> None:
        entity = _entity(
            "e1",
            "character",
            "Test",
            "Content.",
            similarity=1.0,
            frequency=0.0,
            recency=0.0,
        )
        assert entity.relevance_score == pytest.approx(0.5)

    def test_relevance_score_all_contributions(self) -> None:
        entity = _entity(
            "e1",
            "character",
            "Test",
            "Content.",
            similarity=0.8,
            frequency=0.6,
            recency=0.4,
        )
        assert entity.relevance_score == pytest.approx(0.66)

    def test_relevance_score_zero(self) -> None:
        entity = _entity(
            "e1",
            "character",
            "Test",
            "Content.",
            similarity=0.0,
            frequency=0.0,
            recency=0.0,
        )
        assert entity.relevance_score == 0.0


class TestEdgeCases:
    """Empty input, custom token counter, frontmatter parsing."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_defaults(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble()

        assert ctx.chapter_content == ""
        assert ctx.chapter_outline == ""
        assert ctx.recent_chapters == ""
        assert ctx.is_first_chapter is True
        assert ctx.is_sparse_kb is True
        assert ctx.language == "en"
        assert ctx.tone == "balanced"

    @pytest.mark.asyncio
    async def test_only_outline(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_outline="Alice meets Bob at the castle.",
        )
        assert ctx.chapter_outline == "Alice meets Bob at the castle."
        assert ctx.chapter_content == ""
        assert ctx.is_first_chapter is True

    @pytest.mark.asyncio
    async def test_custom_token_counter(self) -> None:
        call_count = 0

        def counter(text: str) -> int:
            nonlocal call_count
            call_count += 1
            return len(text.split())

        asm = WritingContextAssembler(token_counter=counter)
        await asm.assemble(chapter_content="Hello world.")
        assert call_count > 0

    @pytest.mark.asyncio
    async def test_frontmatter_references_extracted(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        fm = _frontmatter(pov_character="char-1", characters=["char-2", "char-3"])
        entities = [
            _entity("char-1", "character", "Alice", "The hero."),
            _entity("char-2", "character", "Bob", "The mentor."),
            _entity("char-3", "character", "Carol", "The villain."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
        )
        assert "Alice" in ctx.kb_characters
        assert "Bob" in ctx.kb_characters
        assert "Carol" in ctx.kb_characters
        assert ctx.kb_suggested == ""

    @pytest.mark.asyncio
    async def test_empty_frontmatter_no_references(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("char-2", "character", "Bob", "A mage."),
            _entity("loc-1", "location", "Castle", "A fortress."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter="",
            kb_entities=entities,
        )
        assert ctx.kb_characters == ""
        assert ctx.kb_locations == ""
        assert ctx.kb_suggested != ""

    @pytest.mark.asyncio
    async def test_recent_chapters_sorted_by_position(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        chapters = [
            _chapter("Old Chapter", "Old text.", "Old summary.", 1),
            _chapter("New Chapter", "New text.", "New summary.", 5),
            _chapter("Mid Chapter", "Mid text.", "Mid summary.", 3),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            recent_chapters=chapters,
        )
        new_pos = ctx.recent_chapters.find("New Chapter")
        old_pos = ctx.recent_chapters.find("Old Chapter")
        assert new_pos < old_pos

    @pytest.mark.asyncio
    async def test_metadata_passed_through(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            project_title="My Novel",
            genre="science fiction",
            language="de",
            tone="literary",
            word_target=5000,
            user_preferences="Short sentences.",
            avoidance_patterns="No cliffhangers.",
        )
        assert ctx.project_title == "My Novel"
        assert ctx.genre == "science fiction"
        assert ctx.language == "de"
        assert ctx.tone == "literary"
        assert ctx.word_target == 5000
        assert ctx.user_preferences == "Short sentences."
        assert ctx.avoidance_patterns == "No cliffhangers."

    @pytest.mark.asyncio
    async def test_to_prompt_variables_roundtrip(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            project_title="Test",
        )
        variables = ctx.to_prompt_variables()
        assert isinstance(variables, dict)
        assert variables["project_title"] == "Test"
        assert variables["chapter_content"] == "Content."
        assert "is_first_chapter" in variables
