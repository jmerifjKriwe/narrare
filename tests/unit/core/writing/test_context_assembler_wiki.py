"""Tests for writing/context_assembler.py — wiki summary integration (core).

Unit tests (no I/O, no DB) for the assembler's wiki-aware context
assembly.  Verifies that the assembler correctly:
1. Prefers fresh wiki summaries over raw entity content in Tier 3
2. Falls back to raw content for stale/pending wiki summaries
3. Falls back to raw content when no wiki summaries are provided
4. Maintains backward compatibility (no wiki_summaries parameter)
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
# Tests — Fresh wiki summaries preferred
# ---------------------------------------------------------------------------


class TestWikiFreshPreferred:
    """When FRESH wiki summaries exist, Tier 3 uses them over raw content."""

    @pytest.mark.asyncio
    async def test_assemble_prefers_wiki_summary_when_fresh(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity(
                "char-1", "character", "Alice", "Raw Alice content is long.", is_referenced=True
            ),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Compressed Alice wiki.",
                role_in_story="Protagonist",
                status=WikiSummaryStatus.FRESH,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        # Wiki summary should appear in kb_characters, not raw content
        assert "Compressed Alice wiki." in ctx.kb_characters
        assert "Raw Alice content is long." not in ctx.kb_characters
        assert ctx.wiki_summaries_count == 1
        assert ctx.wiki_summaries_stale == 0

    @pytest.mark.asyncio
    async def test_fresh_wiki_for_location(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("loc-1", "location", "Castle", "A massive fortress.", is_referenced=True),
        ]
        wikis = {
            "loc-1": _wiki(
                "loc-1",
                narrative_summary="An ancient stronghold.",
                status=WikiSummaryStatus.FRESH,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert "An ancient stronghold." in ctx.kb_locations
        assert "A massive fortress." not in ctx.kb_locations

    @pytest.mark.asyncio
    async def test_fresh_wiki_for_faction(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("fac-1", "faction", "Rebels", "Freedom fighters united.", is_referenced=True),
        ]
        wikis = {
            "fac-1": _wiki(
                "fac-1",
                narrative_summary="A resistance group.",
                status=WikiSummaryStatus.FRESH,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert "A resistance group." in ctx.kb_factions
        assert "Freedom fighters united." not in ctx.kb_factions


# ---------------------------------------------------------------------------
# Tests — Stale / Pending fallback
# ---------------------------------------------------------------------------


class TestWikiStaleFallback:
    """When wiki is STALE or PENDING, raw content is used instead."""

    @pytest.mark.asyncio
    async def test_assemble_falls_back_to_raw_when_stale(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice content.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Stale wiki for Alice.",
                status=WikiSummaryStatus.STALE,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert "Raw Alice content." in ctx.kb_characters
        assert "Stale wiki for Alice." not in ctx.kb_characters
        assert ctx.wiki_summaries_count == 0
        assert ctx.wiki_summaries_stale == 1

    @pytest.mark.asyncio
    async def test_assemble_falls_back_to_raw_when_pending(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice content.", is_referenced=True),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Pending wiki for Alice.",
                status=WikiSummaryStatus.PENDING,
            ),
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries=wikis,
        )

        assert "Raw Alice content." in ctx.kb_characters
        assert "Pending wiki for Alice." not in ctx.kb_characters
        assert ctx.wiki_summaries_count == 0
        assert ctx.wiki_summaries_stale == 1


# ---------------------------------------------------------------------------
# Tests — No wiki at all
# ---------------------------------------------------------------------------


class TestWikiNoSummaries:
    """When no wiki_summaries provided, raw content used — backward compatible."""

    @pytest.mark.asyncio
    async def test_assemble_falls_back_to_raw_when_no_wiki(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice content.", is_referenced=True),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            # No wiki_summaries parameter at all
        )

        assert "Raw Alice content." in ctx.kb_characters
        assert ctx.wiki_summaries_count == 0
        assert ctx.wiki_summaries_stale == 0

    @pytest.mark.asyncio
    async def test_empty_wiki_summaries_dict_same_as_none(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice content.", is_referenced=True),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            wiki_summaries={},  # Empty dict
        )

        assert "Raw Alice content." in ctx.kb_characters
        assert ctx.wiki_summaries_count == 0
        assert ctx.wiki_summaries_stale == 0
