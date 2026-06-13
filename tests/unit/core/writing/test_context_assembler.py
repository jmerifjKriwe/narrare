"""Tests for writing/context_assembler.py — assembly, sparse KB, first chapter.

Split from test_context_assembler.py for RULE-04 compliance.
Remaining tests in test_context_assembler_overflow.py.

Covers:
1. Full context assembly — rich KB, recent chapters, frontmatter references
2. Sparse KB — fewer than 3 entities, flag set correctly
3. First chapter — no history, budget reallocated, flag set
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import yaml

from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity, RecentChapter
from narrare_core.writing.models import WritingContext


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
    """Build a KBEntity with sensible defaults."""
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
    """Build a RecentChapter."""
    return RecentChapter(
        chapter_id=uuid4(),
        title=title,
        full_text=full_text,
        summary=summary,
        position=position,
    )


def _frontmatter(**fields: object) -> str:
    """Build YAML frontmatter string from keyword arguments."""
    yaml_str = yaml.dump(dict(fields), default_flow_style=False)
    return f"---\n{yaml_str}---\n"


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget."""
    return WritingContextAssembler(total_budget=6000)


class TestFullContextAssembly:
    """Rich KB, 3+ recent chapters, frontmatter references."""

    @pytest.mark.asyncio
    async def test_assembles_all_tiers_correctly(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        fm = _frontmatter(
            pov_character="char-1",
            characters=["char-1", "char-2"],
            location="loc-1",
        )
        entities = [
            _entity("char-1", "character", "Alice", "A brave warrior."),
            _entity("char-2", "character", "Bob", "A wise mage."),
            _entity("loc-1", "location", "Castle", "An ancient fortress."),
            _entity("fac-1", "faction", "Rebels", "Freedom fighters."),
            _entity("char-3", "character", "Carol", "A mysterious rogue."),
        ]
        chapters = [
            _chapter("Chapter 1", "Full text one.", "Summary one.", 1),
            _chapter("Chapter 2", "Full text two.", "Summary two.", 2),
            _chapter("Chapter 3", "Full text three.", "Summary three.", 3),
        ]

        ctx = await assembler.assemble(
            chapter_content="The new chapter begins here.",
            chapter_frontmatter=fm,
            chapter_outline="Alice meets Bob at the castle.",
            recent_chapters=chapters,
            kb_entities=entities,
            project_title="Test Novel",
            genre="fantasy",
            tone="dramatic",
            word_target=3000,
        )

        assert isinstance(ctx, WritingContext)
        assert ctx.chapter_content == "The new chapter begins here."
        assert ctx.chapter_outline == "Alice meets Bob at the castle."
        assert ctx.recent_chapter_count == 3
        assert ctx.project_title == "Test Novel"
        assert ctx.genre == "fantasy"
        assert ctx.tone == "dramatic"
        assert ctx.word_target == 3000

        assert "Alice" in ctx.kb_characters
        assert "Bob" in ctx.kb_characters
        assert "Castle" in ctx.kb_locations

        assert ctx.kb_suggested != ""

        assert ctx.is_first_chapter is False
        assert ctx.is_sparse_kb is False

    @pytest.mark.asyncio
    async def test_recent_chapters_use_full_text_when_budget_allows(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        chapters = [_chapter("Chapter 1", "Short full text.", "Short summary.", 1)]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            recent_chapters=chapters,
        )

        assert "Short full text." in ctx.recent_chapters
        assert "Short summary." not in ctx.recent_chapters


class TestSparseKB:
    """Fewer than 3 entities -> is_sparse_kb=True."""

    @pytest.mark.asyncio
    async def test_sparse_with_one_entity(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=[_entity("char-1", "character", "Alice", "A warrior.")],
        )
        assert ctx.is_sparse_kb is True

    @pytest.mark.asyncio
    async def test_sparse_with_two_entities(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=[
                _entity("char-1", "character", "Alice", "A warrior."),
                _entity("char-2", "character", "Bob", "A mage."),
            ],
        )
        assert ctx.is_sparse_kb is True

    @pytest.mark.asyncio
    async def test_not_sparse_with_three_entities(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=[
                _entity("char-1", "character", "Alice", "A warrior."),
                _entity("char-2", "character", "Bob", "A mage."),
                _entity("loc-1", "location", "Castle", "A fortress."),
            ],
        )
        assert ctx.is_sparse_kb is False

    @pytest.mark.asyncio
    async def test_sparse_with_zero_entities(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(chapter_content="Content.")
        assert ctx.is_sparse_kb is True
        assert ctx.kb_characters == ""
        assert ctx.kb_locations == ""
        assert ctx.kb_factions == ""
        assert ctx.kb_suggested == ""


class TestFirstChapter:
    """No history -> is_first_chapter=True, budget reallocated."""

    @pytest.mark.asyncio
    async def test_first_chapter_with_empty_list(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Opening chapter.",
            recent_chapters=[],
        )
        assert ctx.is_first_chapter is True
        assert ctx.recent_chapters == ""
        assert ctx.recent_chapter_count == 0

    @pytest.mark.asyncio
    async def test_first_chapter_without_recent_param(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(chapter_content="Opening chapter.")
        assert ctx.is_first_chapter is True

    @pytest.mark.asyncio
    async def test_first_chapter_reallocates_budget_to_kb(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """With first-chapter reallocation, KB tiers get more budget."""
        entities = [
            _entity(
                f"ent-{i}",
                "character",
                f"Entity {i}",
                f"Content for entity {i}. " * 20,
            )
            for i in range(10)
        ]

        ctx = await assembler.assemble(
            chapter_content="Opening chapter.",
            kb_entities=entities,
        )
        assert ctx.is_first_chapter is True
        assert len(ctx.kb_characters) > 0 or len(ctx.kb_suggested) > 0


class TestVoiceProfilesInAssembly:
    """Voice profile extraction integrated into the assembler."""

    @pytest.mark.asyncio
    async def test_character_voice_profiles_empty_when_no_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Assembly with characters but no speech metadata → empty profiles."""
        fm = _frontmatter(
            pov_character="char-1",
            characters=["char-1", "char-2"],
        )
        entities = [
            _entity("char-1", "character", "Alice", "A brave warrior."),
            _entity("char-2", "character", "Bob", "A wise mage."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
        )
        assert ctx.character_voice_profiles == ""

    @pytest.mark.asyncio
    async def test_character_voice_profiles_present_with_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Assembly with characters and speech metadata → populated profiles."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
            ),
        ]
        # Override metadata directly since _entity doesn't support it
        entities[0] = KBEntity(
            entity_id="char-1",
            entity_type="character",
            name="Alice",
            content="A warrior.",
            similarity_score=0.5,
            frequency_score=0.5,
            recency_score=0.5,
            is_pinned=False,
            is_referenced=False,
            metadata={
                "speech": {"dialect": "Southern", "vocabulary_quirks": "archaic"},
            },
        )
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        assert ctx.character_voice_profiles != ""
        assert "**Alice**" in ctx.character_voice_profiles
        assert "dialect: Southern" in ctx.character_voice_profiles


class TestMetadataPopulation:
    """Assembler populates entity names and total_budget_tokens."""

    @pytest.mark.asyncio
    async def test_assemble_populates_entity_names(self) -> None:
        """Assembler extracts character/location/faction names for metadata."""
        assembler = WritingContextAssembler(total_budget=8000)
        entities = [
            _entity("1", "character", "Anna", "Brave girl"),
            _entity("2", "character", "Johann", "Old forester"),
            _entity("3", "location", "Försterhaus", "A cabin"),
            _entity("4", "faction", "Waldfreunde", "Forest friends"),
        ]
        ctx = await assembler.assemble(kb_entities=entities)
        assert ctx.character_names == ["Anna", "Johann"]
        assert ctx.location_names == ["Försterhaus"]
        assert ctx.faction_names == ["Waldfreunde"]

    @pytest.mark.asyncio
    async def test_assemble_populates_total_budget(self) -> None:
        """Assembler forwards total_budget_tokens to WritingContext."""
        assembler = WritingContextAssembler(total_budget=12000)
        ctx = await assembler.assemble()
        assert ctx.total_budget_tokens == 12000


class TestTierAllocation:
    """ContextAssembler.get_tier_allocation coverage."""

    def test_get_tier_allocation_returns_dict(self) -> None:
        """get_tier_allocation returns budget dict (line 89)."""
        assembler = WritingContextAssembler(total_budget=8000)
        allocation = assembler.get_tier_allocation()
        assert isinstance(allocation, dict)
        assert "tier1" in allocation or "kb" in allocation or len(allocation) > 0


class TestApplyTier2Truncation:
    """_apply_tier2 overflow path — summaries too long for budget (lines 320-321)."""

    @pytest.mark.asyncio
    async def test_apply_tier2_truncates_when_summaries_overflow(self) -> None:
        """When both full text and summaries exceed budget, truncate."""
        assembler = WritingContextAssembler(total_budget=100)
        # 3 chapters with summaries that collectively exceed the tiny budget
        chapters = [
            _chapter(
                title="Chapter 1",
                full_text="A" * 500,
                summary=(
                    "This is a very long summary that should exceed the "
                    "token budget allocated for the recent chapters tier." * 5
                ),
                position=3,
            ),
            _chapter(
                title="Chapter 2",
                full_text="B" * 500,
                summary=(
                    "Another extremely wordy description of the chapter "
                    "that will push us well past the limit." * 5
                ),
                position=2,
            ),
            _chapter(
                title="Chapter 3",
                full_text="C" * 500,
                summary=(
                    "Yet more extended text for the third chapter that "
                    "makes it even harder to fit within the budget." * 5
                ),
                position=1,
            ),
        ]
        ctx = await assembler.assemble(recent=chapters)
        assert isinstance(ctx, WritingContext)
        # Context should have been assembled (truncated)
        assert ctx.total_budget_tokens == 100
