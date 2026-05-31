"""Tests for kb_relationships field in WritingContext and assembler (FIND-009).

Covers:
1. WritingContext field default and assignment
2. to_prompt_variables() includes kb_relationships
3. to_metadata() includes relationship count
4. ContextMetadata includes kb_relationships_count
5. Assembler passes kb_relationships through
6. Assembler defaults kb_relationships to empty string
"""

from __future__ import annotations

import pytest

from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import ContextMetadata
from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# WritingContext — field
# ---------------------------------------------------------------------------


class TestWritingContextKBRelationships:
    """kb_relationships field on WritingContext."""

    def test_default_is_empty_string(self) -> None:
        ctx = WritingContext()
        assert ctx.kb_relationships == ""

    def test_assignment(self) -> None:
        ctx = WritingContext(
            kb_relationships="Aria → [ally of] → Marcus; Aria → [member_of] → Night Watch",
        )
        assert "ally of" in ctx.kb_relationships
        assert "Night Watch" in ctx.kb_relationships


# ---------------------------------------------------------------------------
# to_prompt_variables
# ---------------------------------------------------------------------------


class TestKBRelationshipsPromptVariables:
    """kb_relationships appears in to_prompt_variables()."""

    def test_includes_kb_relationships_key(self) -> None:
        ctx = WritingContext()
        variables = ctx.to_prompt_variables()
        assert "kb_relationships" in variables

    def test_default_value_is_empty_string(self) -> None:
        ctx = WritingContext()
        assert ctx.to_prompt_variables()["kb_relationships"] == ""

    def test_value_forwarded(self) -> None:
        rels = "Aria → [ally of] → Marcus"
        ctx = WritingContext(kb_relationships=rels)
        assert ctx.to_prompt_variables()["kb_relationships"] == rels


# ---------------------------------------------------------------------------
# to_metadata — relationship count
# ---------------------------------------------------------------------------


class TestKBRelationshipsMetadata:
    """kb_relationships_count in to_metadata()."""

    def test_empty_relationships_zero_count(self) -> None:
        ctx = WritingContext()
        meta = ctx.to_metadata()
        assert meta.kb_relationships_count == 0

    def test_count_based_on_arrow_separators(self) -> None:
        """Each '→' represents one relationship edge."""
        # "A → [ally of] → Marcus" has 2 arrows (source→label→target)
        # But the format is: "Aria → [ally of] → Marcus; Aria → [member_of] → Night Watch"
        # That's 4 arrows total. The count gives the number of '→' occurrences.
        ctx = WritingContext(
            kb_relationships="Aria → [ally of] → Marcus; Aria → [member_of] → Night Watch",
        )
        meta = ctx.to_metadata()
        # 4 arrow occurrences
        assert meta.kb_relationships_count == 4

    def test_single_relationship(self) -> None:
        ctx = WritingContext(
            kb_relationships="Aria → [ally of] → Marcus",
        )
        meta = ctx.to_metadata()
        assert meta.kb_relationships_count == 2


# ---------------------------------------------------------------------------
# ContextMetadata — field
# ---------------------------------------------------------------------------


class TestContextMetadataKBRelationships:
    """kb_relationships_count on ContextMetadata."""

    def test_default_is_zero(self) -> None:
        meta = ContextMetadata()
        assert meta.kb_relationships_count == 0

    def test_custom_value(self) -> None:
        meta = ContextMetadata(kb_relationships_count=5)
        assert meta.kb_relationships_count == 5

    def test_included_in_to_dict(self) -> None:
        meta = ContextMetadata(kb_relationships_count=3)
        d = meta.to_dict()
        assert "kb_relationships_count" in d
        assert d["kb_relationships_count"] == 3


# ---------------------------------------------------------------------------
# Assembler — pass-through
# ---------------------------------------------------------------------------


class TestAssemblerKBRelationships:
    """WritingContextAssembler forwards kb_relationships."""

    @pytest.mark.asyncio
    async def test_default_is_empty(self) -> None:
        assembler = WritingContextAssembler(total_budget=6000)
        ctx = await assembler.assemble(chapter_content="Content.")
        assert ctx.kb_relationships == ""

    @pytest.mark.asyncio
    async def test_relationships_forwarded(self) -> None:
        assembler = WritingContextAssembler(total_budget=6000)
        rels = "Aria → [ally of] → Marcus; Aria → [member_of] → Night Watch"
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_relationships=rels,
        )
        assert ctx.kb_relationships == rels

    @pytest.mark.asyncio
    async def test_relationships_available_in_prompt_variables(self) -> None:
        assembler = WritingContextAssembler(total_budget=6000)
        rels = "Marcus → [enemy of] → Lena"
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_relationships=rels,
        )
        variables = ctx.to_prompt_variables()
        assert variables["kb_relationships"] == rels

    @pytest.mark.asyncio
    async def test_relationships_count_in_metadata(self) -> None:
        assembler = WritingContextAssembler(total_budget=6000)
        rels = "Marcus → [enemy of] → Lena"
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_relationships=rels,
        )
        meta = ctx.to_metadata()
        assert meta.kb_relationships_count == 2
