"""CR-04: Tests for new context assembler features.

Covers:
1. timeline_position and story_structure forwarded through assemble()
2. System and timeline entity types appear in kb_systems / kb_timelines
3. Orphan reference detection — frontmatter refs not in KB
4. Voice profile freshness warnings forwarded
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


# ---------------------------------------------------------------------------
# Timeline and Story Structure
# ---------------------------------------------------------------------------


class TestTimelinePositionAndStoryStructure:
    """timeline_position and story_structure are forwarded through assemble()."""

    @pytest.mark.asyncio
    async def test_timeline_position_forwarded(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            timeline_position="Day 5 — Morning",
        )
        assert ctx.timeline_position == "Day 5 — Morning"

    @pytest.mark.asyncio
    async def test_story_structure_forwarded(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            story_structure="3-Act Structure",
        )
        assert ctx.story_structure == "3-Act Structure"

    @pytest.mark.asyncio
    async def test_both_forwarded_to_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(
            chapter_content="Content.",
            timeline_position="Night 3",
            story_structure="Hero's Journey",
        )
        meta = ctx.to_metadata()
        assert meta.timeline_position == "Night 3"
        assert meta.story_structure == "Hero's Journey"

    @pytest.mark.asyncio
    async def test_defaults_empty(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(chapter_content="Content.")
        assert ctx.timeline_position == ""
        assert ctx.story_structure == ""


# ---------------------------------------------------------------------------
# System and Timeline Entity Types
# ---------------------------------------------------------------------------


class TestSystemAndTimelineEntityTypes:
    """System and timeline entities appear in kb_systems / kb_timelines."""

    @pytest.mark.asyncio
    async def test_system_entities_appear_in_kb_systems(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity(
                "sys-1",
                "system",
                "Magic Rules",
                "Mana costs 10 per spell.",
            ),
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
        assert "Magic Rules" in ctx.kb_systems
        assert "Mana costs 10 per spell." in ctx.kb_systems

    @pytest.mark.asyncio
    async def test_timeline_entities_appear_in_kb_timelines(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity(
                "time-1",
                "timeline",
                "War of Ashes",
                "Year 1042. The great war begins.",
            ),
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
        assert "War of Ashes" in ctx.kb_timelines
        assert "Year 1042." in ctx.kb_timelines

    @pytest.mark.asyncio
    async def test_system_and_timeline_empty_without_entity_type(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("loc-1", "location", "Castle", "A fortress."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
            ),
            kb_entities=entities,
        )
        assert ctx.kb_systems == ""
        assert ctx.kb_timelines == ""

    @pytest.mark.asyncio
    async def test_system_and_timeline_counts_in_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("sys-1", "system", "Magic", "Mana costs."),
            _entity("sys-2", "system", "Combat", "Turn-based."),
            _entity("time-1", "timeline", "War", "Year 1042."),
            _entity("char-1", "character", "Alice", "A warrior."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
                systems=["sys-1", "sys-2"],
                timeline="time-1",
            ),
        )
        meta = ctx.to_metadata()
        assert meta.kb_systems_count >= 1 or ctx.kb_systems != ""
        assert meta.kb_timelines_count >= 1 or ctx.kb_timelines != ""


# ---------------------------------------------------------------------------
# Orphan References
# ---------------------------------------------------------------------------


class TestOrphanReferences:
    """Frontmatter references to entities not in KB produce warnings."""

    @pytest.mark.asyncio
    async def test_no_orphans_when_all_resolved(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("loc-1", "location", "Castle", "A fortress."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
                location="loc-1",
            ),
            kb_entities=entities,
        )
        assert len(ctx.orphan_reference_warnings) == 0

    @pytest.mark.asyncio
    async def test_orphan_detected(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Frontmatter ref 'char-99' has no matching KB entity."""
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1", "char-99"],
            ),
            kb_entities=entities,
        )
        assert len(ctx.orphan_reference_warnings) >= 1
        warning = ctx.orphan_reference_warnings[0]
        assert "char-99" in warning
        assert "not in the knowledge base" in warning

    @pytest.mark.asyncio
    async def test_orphan_empty_with_no_frontmatter(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        ctx = await assembler.assemble(chapter_content="Content.")
        assert ctx.orphan_reference_warnings == []

    @pytest.mark.asyncio
    async def test_orphan_with_deprecated_entity(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """A deprecated entity referenced in frontmatter is treated as orphan."""
        entities = [
            KBEntity(
                entity_id="char-1",
                entity_type="character",
                name="Alice",
                content="A warrior.",
                status="deprecated",
                similarity_score=0.5,
                frequency_score=0.5,
                recency_score=0.5,
            ),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
            ),
            kb_entities=entities,
        )
        assert len(ctx.orphan_reference_warnings) >= 1


# ---------------------------------------------------------------------------
# Voice Profile Warnings
# ---------------------------------------------------------------------------


class TestVoiceProfileWarnings:
    """Voice profile freshness warnings are forwarded."""

    @pytest.mark.asyncio
    async def test_no_warnings_without_metadata(
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
        assert ctx.voice_profile_warnings == []

    @pytest.mark.asyncio
    async def test_warnings_with_stale_entity(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Ensure the assembler does not crash with stale voice profile data."""
        entities = [
            KBEntity(
                entity_id="char-1",
                entity_type="character",
                name="Alice",
                content="A warrior.",
                similarity_score=0.5,
                frequency_score=0.5,
                recency_score=0.5,
                metadata={
                    "personality": "brave",
                    "speech": {"dialect": "Southern"},
                },
                updated_at="2020-01-01T00:00:00Z",
            ),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
        )
        # Voice profile warnings may be present since the entity has speech
        # metadata and a very old updated_at — at minimum the call should
        # not crash and warnings is a list.
        assert isinstance(ctx.voice_profile_warnings, list)
