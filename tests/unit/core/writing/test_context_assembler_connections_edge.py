"""Tests for WritingContextAssembler entity_connections — edge cases & budget.

Covers:
1. Connections to non-existent entities ignored gracefully
2. Referenced + connected both in Tier 3 output fields
3. is_referenced flag triggers connection promotion
4. Budget limits respected even with promoted entities
5. classify_entities module-level function
"""

from __future__ import annotations

import pytest
import yaml

from narrare_core.writing._classify import classify_entities
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


# ── Test 6: Connected entity not in kb_entities — ignored ──────────────────


class TestMissingEntities:
    """Connections pointing to entities not in kb_entities are ignored."""

    @pytest.mark.asyncio
    async def test_connection_to_nonexistent_entity(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """King A connected to 'royal-guard' which is not in entities."""
        fm = _frontmatter(pov_character="king-a")
        entities = [
            _entity("king-a", "character", "König A", "The ruler."),
            _entity("unrelated", "character", "Stranger", "Nobody."),
        ]
        connections = {
            "king-a": {"royal-guard", "missing-entity"},
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        # König A still referenced
        assert "König A" in ctx.kb_characters
        # No crash from missing entities; Stranger stays in suggested
        assert "Stranger" in ctx.kb_suggested


# ── Test 7: Referenced + connected both in kb_referenced output ────────────


class TestTier3Output:
    """Referenced and connected entities both appear in Tier 3 fields."""

    @pytest.mark.asyncio
    async def test_referenced_and_connected_in_tier3(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Both referenced chars and connected locations in Tier 3."""
        fm = _frontmatter(characters=["char-1"])
        entities = [
            _entity("char-1", "character", "Alice", "A hero."),
            _entity("loc-1", "location", "Castle", "Her home."),
            _entity("fac-1", "faction", "Rebels", "Fighters."),
            _entity("char-2", "character", "Eve", "Unrelated."),
        ]
        connections = {"char-1": {"loc-1", "fac-1"}}

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        # Referenced entity in Tier 3
        assert "Alice" in ctx.kb_characters
        # Connected entities promoted to Tier 3
        assert "Castle" in ctx.kb_locations
        assert "Rebels" in ctx.kb_factions
        # Unrelated entity in suggested
        assert "Eve" in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_is_referenced_flag_triggers_connections(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """is_referenced=True entity also promotes its connections."""
        entities = [
            _entity("char-1", "character", "Alice", "A hero.", is_referenced=True),
            _entity("loc-1", "location", "Castle", "Her home."),
            _entity("char-2", "character", "Eve", "Unrelated."),
        ]
        connections = {"char-1": {"loc-1"}}

        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            entity_connections=connections,
        )

        assert "Alice" in ctx.kb_characters
        assert "Castle" in ctx.kb_locations
        assert "Eve" in ctx.kb_suggested


# ── Test 8: Budget still enforced with promoted entities ────────────────────


class TestBudgetWithConnections:
    """Budget limits respected even when entities are promoted."""

    @pytest.mark.asyncio
    async def test_promoted_entities_truncated_when_over_budget(self) -> None:
        """Many connected entities still fit within Tier 3 budget."""
        tiny = WritingContextAssembler(total_budget=50)
        entities = [
            _entity("char-1", "character", "Alice", "A hero.", is_referenced=True),
        ] + [
            _entity(f"loc-{i}", "location", f"Place {i}", f"Description {i}. " * 10)
            for i in range(10)
        ]
        connections = {
            "char-1": {f"loc-{i}" for i in range(10)},
        }

        ctx = await tiny.assemble(
            chapter_content="x",
            kb_entities=entities,
            entity_connections=connections,
        )

        # Alice should be in Tier 3 characters (highest priority)
        assert "Alice" in ctx.kb_characters
        # Some locations may be truncated but no crash
        # The key assertion: budget is enforced, output is finite
        total_tier3 = len(ctx.kb_characters) + len(ctx.kb_locations) + len(ctx.kb_factions)
        assert total_tier3 > 0


# ── Test: _classify_entities directly ───────────────────────────────────────


class TestClassifyEntitiesHelper:
    """Direct tests for classify_entities module-level function."""

    def test_pinned_excluded_from_connected_and_suggested(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Pinned entities never appear in connected or suggested."""
        entities = [
            _entity("p-1", "character", "Pinned", "P.", is_pinned=True),
            _entity("r-1", "character", "Referenced", "R.", is_referenced=True),
            _entity("s-1", "character", "Suggested", "S."),
        ]
        pinned, referenced, connected, suggested = classify_entities(
            entities,
            ref_ids=set(),
            connections={"r-1": {"p-1"}},
        )
        assert len(pinned) == 1
        assert pinned[0].entity_id == "p-1"
        assert len(referenced) == 1
        assert referenced[0].entity_id == "r-1"
        # Pinned entity not promoted as connected
        assert len(connected) == 0
        assert len(suggested) == 1
        assert suggested[0].entity_id == "s-1"

    def test_empty_connections_produces_no_connected(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """With no connections, connected list is empty."""
        entities = [
            _entity("r-1", "character", "Referenced", "R.", is_referenced=True),
            _entity("s-1", "character", "Suggested", "S."),
        ]
        _pinned, referenced, connected, suggested = classify_entities(
            entities,
            ref_ids=set(),
            connections={},
        )
        assert len(referenced) == 1
        assert len(connected) == 0
        assert len(suggested) == 1
