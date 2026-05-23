"""Tests for WritingContextAssembler entity_connections promotion.

Covers:
1. Connected entities promoted from suggested to referenced tier
2. No promotion when entity_connections is None (backward compat)
3. No promotion when entity_connections is empty dict
4. Multi-hop: only first-degree promoted, not second-degree
5. Circular connections handled correctly
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


# ── Test 1: Connected entities promoted from suggested → referenced ────────


class TestConnectedPromotion:
    """First-degree connections of referenced entities land in Tier 3."""

    @pytest.mark.asyncio
    async def test_connected_character_promoted_to_tier3(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """King A referenced → Capital City (connected) promoted to Tier 3."""
        fm = _frontmatter(pov_character="king-a")
        entities = [
            _entity("king-a", "character", "König A", "The ruler."),
            _entity("capital-city", "location", "Hauptstadt B", "The capital."),
            _entity("unrelated", "character", "Stranger", "Nobody.", similarity=0.1),
        ]
        connections = {
            "king-a": {"capital-city", "royal-guard"},
            "capital-city": {"king-a", "market-district"},
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        # König A is directly referenced → Tier 3 characters
        assert "König A" in ctx.kb_characters
        # Hauptstadt B is connected to König A → promoted to Tier 3 locations
        assert "Hauptstadt B" in ctx.kb_locations
        # Stranger is unrelated → stays in Tier 4 suggested
        assert "Stranger" in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_connected_faction_promoted(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Referenced character's connected faction promoted to Tier 3."""
        fm = _frontmatter(characters=["char-1"])
        entities = [
            _entity("char-1", "character", "Alice", "A leader."),
            _entity("fac-1", "faction", "Rebels", "Freedom fighters."),
            _entity("loc-1", "location", "Outpost", "Remote base.", similarity=0.1),
        ]
        connections = {"char-1": {"fac-1"}}

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        assert "Alice" in ctx.kb_characters
        assert "Rebels" in ctx.kb_factions
        # Outpost has no connection → stays in suggested
        assert "Outpost" in ctx.kb_suggested


# ── Test 2 & 3: Backward compatibility ─────────────────────────────────────


class TestBackwardCompatibility:
    """entity_connections=None or empty dict → identical to pre-connection behavior."""

    @pytest.mark.asyncio
    async def test_none_connections_no_promotion(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """entity_connections=None → no promotion, behavior unchanged."""
        fm = _frontmatter(pov_character="char-1")
        entities = [
            _entity("char-1", "character", "Alice", "The hero."),
            _entity("loc-1", "location", "Castle", "A fortress."),
            _entity("fac-1", "faction", "Guild", "Traders."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=None,
        )

        # Only Alice in Tier 3; Castle and Guild stay in suggested
        assert "Alice" in ctx.kb_characters
        assert "Castle" in ctx.kb_suggested
        assert "Guild" in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_empty_dict_no_promotion(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """entity_connections={} → no promotion, behavior unchanged."""
        fm = _frontmatter(pov_character="char-1")
        entities = [
            _entity("char-1", "character", "Alice", "The hero."),
            _entity("loc-1", "location", "Castle", "A fortress."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections={},
        )

        assert "Alice" in ctx.kb_characters
        assert "Castle" in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_no_entity_connections_param_identical_to_none(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Calling without entity_connections same as entity_connections=None."""
        fm = _frontmatter(pov_character="char-1")
        entities = [
            _entity("char-1", "character", "Alice", "The hero."),
            _entity("loc-1", "location", "Castle", "A fortress."),
        ]

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
        )

        assert "Alice" in ctx.kb_characters
        assert "Castle" in ctx.kb_suggested


# ── Test 4: Multi-hop — only first-degree promoted ─────────────────────────


class TestMultiHop:
    """Only first-degree connections promoted, not second-degree."""

    @pytest.mark.asyncio
    async def test_second_degree_not_promoted(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """A → B → C: only B is promoted, C stays in suggested."""
        fm = _frontmatter(pov_character="char-a")
        entities = [
            _entity("char-a", "character", "Alice", "The hero."),
            _entity("loc-b", "location", "Bridge", "A river crossing."),
            _entity("fac-c", "faction", "Merchants", "Traders guild."),
        ]
        # A connected to B, B connected to C
        connections = {
            "char-a": {"loc-b"},
            "loc-b": {"fac-c"},
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        # A is referenced → Tier 3
        assert "Alice" in ctx.kb_characters
        # B is first-degree connection of A → promoted to Tier 3
        assert "Bridge" in ctx.kb_locations
        # C is second-degree (connected to B, not to A) → stays in suggested
        assert "Merchants" in ctx.kb_suggested


# ── Test 5: Circular connections ────────────────────────────────────────────


class TestCircularConnections:
    """Circular connections handled correctly without infinite loops."""

    @pytest.mark.asyncio
    async def test_mutual_connections(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """A connected to B, B connected to A — both land correctly."""
        fm = _frontmatter(pov_character="char-a")
        entities = [
            _entity("char-a", "character", "Alice", "The hero."),
            _entity("char-b", "character", "Bob", "The ally."),
            _entity("loc-1", "location", "Tower", "A spire.", similarity=0.1),
        ]
        connections = {
            "char-a": {"char-b"},
            "char-b": {"char-a"},
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        # Alice is directly referenced
        assert "Alice" in ctx.kb_characters
        # Bob is connected to Alice (first-degree) — but Alice is in ref_ids
        # so Bob would be connected_ids initially, then removed as it's a
        # referenced entity? No — Bob is NOT referenced (not in ref_ids, not
        # is_referenced). So Bob stays in connected → promoted to Tier 3.
        assert "Bob" in ctx.kb_characters
        # Tower is unrelated
        assert "Tower" in ctx.kb_suggested

    @pytest.mark.asyncio
    async def test_three_way_cycle(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """A→B→C→A cycle: only first-degree of referenced promoted."""
        fm = _frontmatter(pov_character="char-a")
        entities = [
            _entity("char-a", "character", "Alice", "The hero."),
            _entity("loc-b", "location", "Forge", "A smithy."),
            _entity("fac-c", "faction", "Guild", "Artisans."),
        ]
        connections = {
            "char-a": {"loc-b"},
            "loc-b": {"fac-c"},
            "fac-c": {"char-a"},
        }

        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=fm,
            kb_entities=entities,
            entity_connections=connections,
        )

        assert "Alice" in ctx.kb_characters
        assert "Forge" in ctx.kb_locations  # first-degree of Alice
        assert "Guild" in ctx.kb_suggested  # second-degree, not promoted
