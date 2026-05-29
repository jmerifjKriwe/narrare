"""Tests for writing/context_assembler.py — wiki metadata and budget.

Unit tests (no I/O, no DB) for the assembler's wiki-aware context
assembly.  Verifies that the assembler correctly:
1. Tracks wiki fresh/stale counts in ContextMetadata
2. Adjusts budget allocation when wiki_optimized=True
3. Includes role_in_story and key_attributes in wiki output format
"""

from __future__ import annotations

import pytest

from narrare_core.wiki.types import WikiSummaryData, WikiSummaryStatus
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
    content: str = "A brave warrior from the northern mountains.",
    is_referenced: bool = False,
    is_pinned: bool = False,
) -> KBEntity:
    """Build a KBEntity with sensible defaults for wiki assembler tests."""
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
        is_referenced=is_referenced,
        is_pinned=is_pinned,
    )


def _wiki(
    entity_id: str = "ent-1",
    narrative_summary: str = "Wiki summary for entity.",
    role_in_story: str | None = None,
    key_attributes: list[str] | None = None,
    status: WikiSummaryStatus = WikiSummaryStatus.FRESH,
) -> WikiSummaryData:
    """Build a WikiSummaryData with sensible defaults."""
    return WikiSummaryData(
        entity_id=entity_id,
        novel_id="novel-1",
        narrative_summary=narrative_summary,
        role_in_story=role_in_story,
        key_attributes=key_attributes or [],
        status=status,
    )


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget."""
    return WritingContextAssembler(total_budget=6000)


# ---------------------------------------------------------------------------
# Tests — Metadata tracking
# ---------------------------------------------------------------------------


class TestWikiMetadataTracking:
    """Assembler tracks wiki counts in WritingContext and ContextMetadata."""

    @pytest.mark.asyncio
    async def test_assemble_tracks_wiki_counts_in_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice.", is_referenced=True),
            _entity("char-2", "character", "Bob", "Raw Bob.", is_referenced=True),
            _entity("loc-1", "location", "Castle", "Raw castle.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1", narrative_summary="Fresh Alice.", status=WikiSummaryStatus.FRESH
            ),
            "char-2": _wiki(
                "char-2", narrative_summary="Stale Bob.", status=WikiSummaryStatus.STALE
            ),
            # loc-1 has no wiki -> no count
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert ctx.wiki_summaries_count == 1  # Only Alice is fresh
        assert ctx.wiki_summaries_stale == 1  # Bob is stale

        # Also check to_metadata() propagates these
        meta = ctx.to_metadata()
        assert meta.wiki_summaries_count == 1
        assert meta.wiki_summaries_stale == 1

    @pytest.mark.asyncio
    async def test_assemble_mixed_fresh_and_stale(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Some fresh, some stale -> correct counts and content per entity."""
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice.", is_referenced=True),
            _entity("char-2", "character", "Bob", "Raw Bob.", is_referenced=True),
            _entity("char-3", "character", "Carol", "Raw Carol.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1", narrative_summary="Wiki Alice.", status=WikiSummaryStatus.FRESH
            ),
            "char-2": _wiki(
                "char-2", narrative_summary="Wiki Bob.", status=WikiSummaryStatus.STALE
            ),
            "char-3": _wiki(
                "char-3", narrative_summary="Wiki Carol.", status=WikiSummaryStatus.FRESH
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert ctx.wiki_summaries_count == 2  # Alice + Carol
        assert ctx.wiki_summaries_stale == 1  # Bob
        # Fresh entities use wiki
        assert "Wiki Alice." in ctx.kb_characters
        assert "Wiki Carol." in ctx.kb_characters
        # Stale entity uses raw
        assert "Raw Bob." in ctx.kb_characters
        assert "Wiki Bob." not in ctx.kb_characters


# ---------------------------------------------------------------------------
# Tests — Backward compatibility
# ---------------------------------------------------------------------------


class TestWikiBackwardCompatibility:
    """Calling assemble() without wiki_summaries works identically to before."""

    @pytest.mark.asyncio
    async def test_assemble_wiki_backward_compatible(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Existing calls without wiki_summaries produce same results."""
        entities = [
            _entity("char-1", "character", "Alice", "A warrior.", is_referenced=True),
            _entity("loc-1", "location", "Castle", "A fortress.", is_referenced=True),
            _entity("fac-1", "faction", "Rebels", "Fighters.", is_referenced=True),
            _entity("char-2", "character", "Bob", "A mage."),
        ]

        ctx = await assembler.assemble(
            chapter_content="The chapter.",
            kb_entities=entities,
            project_title="Test Novel",
        )

        # All standard assertions still hold
        assert "Alice" in ctx.kb_characters
        assert "Castle" in ctx.kb_locations
        assert "Rebels" in ctx.kb_factions
        assert ctx.wiki_summaries_count == 0
        assert ctx.wiki_summaries_stale == 0
        assert ctx.project_title == "Test Novel"


# ---------------------------------------------------------------------------
# Tests — Budget allocation
# ---------------------------------------------------------------------------


class TestWikiOptimizedBudget:
    """When wiki_summaries provided, budget allocation gives more to immediate."""

    @pytest.mark.asyncio
    async def test_assemble_wiki_optimized_budget(self) -> None:
        """wiki_optimized=True shifts 5% from kb_referenced to immediate."""
        from narrare_core.writing.budget import TokenBudgetManager

        manager = TokenBudgetManager(total_budget=6000)

        # Without wiki optimization
        normal = manager.allocate(wiki_optimized=False)
        normal_immediate = normal["immediate"].token_limit
        normal_kb = normal["kb_referenced"].token_limit

        # With wiki optimization
        wiki = manager.allocate(wiki_optimized=True)
        wiki_immediate = wiki["immediate"].token_limit
        wiki_kb = wiki["kb_referenced"].token_limit

        # Immediate should be larger with wiki optimization
        assert wiki_immediate > normal_immediate
        # KB referenced should be smaller with wiki optimization
        assert wiki_kb < normal_kb

        # Verify the assembler passes wiki_optimized correctly
        assembler = WritingContextAssembler(total_budget=6000)
        entities = [
            _entity("char-1", "character", "Alice", "A warrior.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki("char-1", status=WikiSummaryStatus.FRESH),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )
        # The context should be assembled successfully with wiki-optimized budget
        assert ctx.wiki_summaries_count == 1


# ---------------------------------------------------------------------------
# Tests — Wiki format includes role and attributes
# ---------------------------------------------------------------------------


class TestWikiFormatInOutput:
    """Verify formatted wiki text includes role_in_story and key_attributes."""

    @pytest.mark.asyncio
    async def test_wiki_format_includes_role_and_attributes(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw content.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="A fierce warrior.",
                role_in_story="Protagonist",
                key_attributes=["brave", "loyal"],
                status=WikiSummaryStatus.FRESH,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert "A fierce warrior." in ctx.kb_characters
        assert "Role: Protagonist" in ctx.kb_characters
        assert "Attributes: brave, loyal" in ctx.kb_characters
        # Raw content should NOT appear
        assert "Raw content." not in ctx.kb_characters
