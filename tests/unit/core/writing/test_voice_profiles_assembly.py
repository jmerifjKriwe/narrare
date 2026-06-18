"""End-to-end voice profile tests through WritingContextAssembler.

Extracted from ``test_voice_profiles.py`` for RULE-04 compliance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from narrare_core.profiles._voice_extraction import build_character_voice_profile
from narrare_core.profiles.assembly import ProfileAssembler
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.models import WritingContext

if TYPE_CHECKING:
    from narrare_core.profiles.contracts import VoiceProfileProvider
    from narrare_core.profiles.models import CharacterVoiceProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    metadata: dict[str, Any] | None = None,
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
        metadata=metadata,
    )


class _EntityVoiceProvider:
    """Test provider that exposes KBEntity voice data through the contract."""

    def __init__(self, entities: list[KBEntity]) -> None:
        self._entities = entities

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        del project_id
        voices: list[CharacterVoiceProfile] = []
        for entity in self._entities:
            if entity.entity_type != "character":
                continue
            profile = build_character_voice_profile(
                entity_id=entity.entity_id,
                name=entity.name,
                metadata=entity.metadata,
                updated_at=entity.updated_at,
                max_age_days=max_age_days,
            )
            if profile is not None:
                voices.append(profile)
        return voices


def _consumer_for_entities(entities: list[KBEntity]) -> ProfileAssembler:
    """Build the VoiceProfileConsumer used by assembler tests."""
    provider: VoiceProfileProvider = _EntityVoiceProvider(entities)
    return ProfileAssembler(provider=provider)


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget."""
    return WritingContextAssembler(total_budget=6000)


# ---------------------------------------------------------------------------
# Tests: End-to-end through assembler
# ---------------------------------------------------------------------------


class TestAssemblerEndToEnd:
    """End-to-end voice profile extraction through assembler.assemble()."""

    @pytest.mark.asyncio
    async def test_assembler_includes_voice_profiles(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Full assembly with character speech metadata → voice profiles included."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "speech": {
                        "dialect": "Southern",
                        "vocabulary_quirks": "archaic forms",
                        "typical_phrases": ["y'all", "reckon"],
                    },
                    "personality": {
                        "traits": ["warm", "diplomatic"],
                    },
                },
            ),
            _entity(
                "char-2",
                "character",
                "Bob",
                "A mage.",
                metadata={
                    "speech": {
                        "dialect": "Northern",
                        "vocabulary_quirks": "formal speech",
                    },
                },
            ),
            _entity("loc-1", "location", "Castle", "An ancient fortress."),
        ]

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            chapter_frontmatter=(
                "---\npov_character: char-1\ncharacters:\n  - char-1\n  - char-2\n---\n"
            ),
            chapter_outline="Alice and Bob meet.",
            kb_entities=entities,
            voice_profile_consumer=_consumer_for_entities(entities),
            project_title="Test",
            genre="fantasy",
        )

        assert isinstance(ctx, WritingContext)
        assert ctx.character_voice_profiles != ""

        profiles = ctx.character_voice_profiles
        assert "**Alice**" in profiles
        assert "**Bob**" in profiles
        assert "dialect: Southern" in profiles
        assert "dialect: Northern" in profiles
        assert "vocabulary: archaic forms" in profiles
        assert "typical phrases" in profiles
        assert "personality traits" in profiles

    @pytest.mark.asyncio
    async def test_assembler_empty_when_no_characters(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Assembly with no character entities → empty voice profiles."""
        entities = [
            _entity("loc-1", "location", "Castle", "An ancient fortress."),
            _entity("fac-1", "faction", "Rebels", "Freedom fighters."),
        ]

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            kb_entities=entities,
            voice_profile_consumer=_consumer_for_entities(entities),
            project_title="Test",
            genre="fantasy",
        )

        assert ctx.character_voice_profiles == ""

    @pytest.mark.asyncio
    async def test_assembler_empty_when_no_speech_metadata(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Assembly with characters but no metadata → empty voice profiles."""
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("char-2", "character", "Bob", "A mage."),
        ]

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            kb_entities=entities,
            voice_profile_consumer=_consumer_for_entities(entities),
            project_title="Test",
            genre="fantasy",
        )

        assert ctx.character_voice_profiles == ""

    @pytest.mark.asyncio
    async def test_assembler_with_avoidance_patterns(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Voice profiles coexist with other context fields."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "speech": {"dialect": "Southern"},
                },
            ),
        ]

        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="The chapter begins.",
            kb_entities=entities,
            voice_profile_consumer=_consumer_for_entities(entities),
            project_title="Test",
            genre="fantasy",
            avoidance_patterns="No cliches.",
            user_preferences="Write in third person.",
        )

        assert "**Alice**" in ctx.character_voice_profiles
        assert ctx.avoidance_patterns == "No cliches."
        assert ctx.user_preferences == "Write in third person."
