"""T1a: Value-side optional block labels for Tier-5 KB variables.

Covers the ``optional_block`` value wrapping
(:func:`narrare_core.writing._helpers.optional_block`) applied at the
three kb emission points in
:mod:`narrare_core.writing.context_assembler`:

* ``kb_systems`` → label ``"Systems"``
* ``kb_timelines`` → label ``"Timelines"``
* ``kb_pinned`` → label ``"Pinned context (always included)"``

Per variable:
1. empty tier → value is exactly ``""`` (byte-identical template
   rendering for KB-empty novels)
2. populated tier → value starts with ``"\\n\\n<Label>:\\n"`` followed by
   the tier text
3. labels add no ``### `` markers → ``to_metadata()`` entry counts are
   unchanged by the wrap
"""

from __future__ import annotations

import pytest
import yaml

from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity


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


def _frontmatter(**fields: object) -> str:
    """Build YAML frontmatter string from keyword arguments."""
    yaml_str = yaml.dump(dict(fields), default_flow_style=False)
    return f"---\n{yaml_str}---\n"


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget."""
    return WritingContextAssembler(total_budget=6000)


class TestOptionalBlockLabels:
    """kb_systems / kb_timelines / kb_pinned carry value-side labels.

    Populated tiers start with ``"\\n\\n<Label>:\\n"`` followed by the
    tier text; empty tiers render exactly ``""``.  Labels add no ``### ``
    markers so ``to_metadata()`` entry counts are unchanged.
    """

    @pytest.mark.asyncio
    async def test_kb_systems_populated_starts_with_label(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("sys-1", "system", "Magic Rules", "Mana costs 10 per spell."),
            _entity("char-1", "character", "Alice", "A warrior."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
                system="sys-1",
            ),
            kb_entities=entities,
        )
        assert ctx.kb_systems.startswith("\n\nSystems:\n")
        assert "### System: Magic Rules" in ctx.kb_systems
        assert "Mana costs 10 per spell." in ctx.kb_systems

    @pytest.mark.asyncio
    async def test_kb_timelines_populated_starts_with_label(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("time-1", "timeline", "War of Ashes", "Year 1042. The great war begins."),
            _entity("char-1", "character", "Alice", "A warrior."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
                timeline="time-1",
            ),
            kb_entities=entities,
        )
        assert ctx.kb_timelines.startswith("\n\nTimelines:\n")
        assert "### Timeline: War of Ashes" in ctx.kb_timelines
        assert "Year 1042." in ctx.kb_timelines

    @pytest.mark.asyncio
    async def test_kb_pinned_populated_starts_with_label(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("pin-1", "character", "Alice", "A warrior.", is_pinned=True),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        assert ctx.kb_pinned.startswith("\n\nPinned context (always included):\n")
        assert "### Character: Alice" in ctx.kb_pinned
        assert "A warrior." in ctx.kb_pinned

    @pytest.mark.asyncio
    async def test_kb_pinned_empty_without_pinned_entities(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        assert ctx.kb_pinned == ""

    @pytest.mark.asyncio
    async def test_metadata_counts_unchanged_by_labels(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Labels contribute no ``### `` markers — counts equal tier sizes."""
        entities = [
            _entity("sys-1", "system", "Magic Rules", "Mana costs 10 per spell."),
            _entity("sys-2", "system", "Combat", "Turn-based."),
            _entity("time-1", "timeline", "War of Ashes", "Year 1042."),
            _entity("pin-1", "character", "Alice", "A warrior.", is_pinned=True),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                systems=["sys-1", "sys-2"],
                timeline="time-1",
            ),
            kb_entities=entities,
        )
        meta = ctx.to_metadata()
        assert meta.kb_systems_count == 2
        assert meta.kb_timelines_count == 1
        assert meta.kb_pinned_count == 1
        # The labels themselves must not appear as heading markers.
        assert "### Systems" not in ctx.kb_systems
        assert "### Timelines" not in ctx.kb_timelines
        assert "### Pinned" not in ctx.kb_pinned
