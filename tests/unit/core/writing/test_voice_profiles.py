"""Tests for character voice profile extraction logic.

Covers:
1. extract_voice_profiles() — empty, partial, full metadata, freshness
2. WritingContext — character_voice_profiles field + to_prompt_variables()
3. PromptContext — character_voice_profiles field + as_variables()

End-to-end assembler tests live in test_voice_profiles_assembly.py (RULE-04).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from narrare_core.prompts.context import PromptContext
from narrare_core.writing._voice_profiles import extract_voice_profiles
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.models import WritingContext

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
    updated_at: str | None = None,
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
        updated_at=updated_at,
        metadata=metadata,
    )


@pytest.fixture()
def context() -> WritingContext:
    """Default WritingContext for variable mapping tests."""
    return WritingContext(
        chapter_content="Test content.",
        chapter_frontmatter="",
        chapter_outline="Test outline.",
        character_voice_profiles="**Alice**: dialect: Southern; typical phrases: y'all, reckon",
        project_title="Test",
        genre="fantasy",
    )


# ---------------------------------------------------------------------------
# Test: extract_voice_profiles
# ---------------------------------------------------------------------------


class TestExtractVoiceProfiles:
    """extract_voice_profiles() edge cases and happy path."""

    def test_extract_voice_profiles_empty(self) -> None:
        """No characters → empty string."""
        entities: list[KBEntity] = []
        result, _warnings = extract_voice_profiles(entities)
        assert result == "" and _warnings == []

    def test_extract_voice_profiles_no_metadata(self) -> None:
        """Characters without metadata → empty string."""
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("char-2", "character", "Bob", "A mage."),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert result == "" and _warnings == []

    def test_extract_voice_profiles_with_speech_metadata(self) -> None:
        """Characters with speech metadata → formatted profile."""
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
                        "typical_phrases": ["y'all", "reckon", "bless your heart"],
                        "body_language": "drawls while leaning",
                    },
                    "personality": {
                        "traits": ["warm", "diplomatic", "patient"],
                    },
                },
            ),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert "dialect: Southern" in result
        assert "vocabulary: archaic forms" in result
        assert "typical phrases" in result
        assert "y'all" in result
        assert "body language" in result
        assert "personality traits" in result

    def test_extract_voice_profiles_mixed_entities(self) -> None:
        """Mix of characters/locations → only characters extracted."""
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
            _entity("loc-1", "location", "Castle", "An ancient fortress."),
            _entity("fac-1", "faction", "Rebels", "Freedom fighters."),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert "Castle" not in result
        assert "Rebels" not in result

    def test_extract_voice_profiles_partial_speech(self) -> None:
        """Character with only dialect → partial profile."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "speech": {"dialect": "Cockney"},
                },
            ),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert "dialect: Cockney" in result
        assert "vocabulary" not in result

    def test_extract_voice_profiles_non_dict_metadata(self) -> None:
        """Character with metadata that has wrong types → gracefully ignored."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "speech": "not a dict",
                    "personality": {"traits": "not a list"},
                },
            ),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert result == "" and _warnings == []

    def test_extract_voice_profiles_multiple_characters(self) -> None:
        """Multiple characters with speech metadata → all included."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "speech": {"dialect": "Southern", "vocabulary_quirks": "archaic"},
                },
            ),
            _entity(
                "char-2",
                "character",
                "Bob",
                "A mage.",
                metadata={
                    "speech": {"dialect": "Northern", "vocabulary_quirks": "formal"},
                },
            ),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert "**Bob**" in result
        assert "dialect: Southern" in result
        assert "dialect: Northern" in result

    def test_extract_voice_profiles_personality_only(self) -> None:
        """Character with only personality traits → personality profile."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                metadata={
                    "personality": {
                        "traits": ["brave", "impulsive", "loyal"],
                    },
                },
            ),
        ]
        result, _warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert "personality traits" in result
        assert "brave, impulsive, loyal" in result

    # ------------------------------------------------------------------
    # Freshness tests
    # ------------------------------------------------------------------

    def test_extract_voice_profiles_updated_at_none_no_warnings(self) -> None:
        """updated_at=None returns no warnings."""
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                updated_at=None,
                metadata={"speech": {"dialect": "Southern"}},
            ),
        ]
        result, warnings = extract_voice_profiles(entities)
        assert "**Alice**" in result
        assert warnings == []

    def test_extract_voice_profiles_old_updated_at_produces_warning(self) -> None:
        """updated_at older than max_age_days produces a warning."""
        old_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                updated_at=old_date,
                metadata={"speech": {"dialect": "Southern"}},
            ),
        ]
        result, warnings = extract_voice_profiles(entities, max_age_days=30)
        assert "**Alice**" in result
        assert len(warnings) == 1
        assert "Voice profile for 'Alice'" in warnings[0]

    def test_extract_voice_profiles_fresh_updated_at_no_warning(self) -> None:
        """Recent updated_at produces no warnings."""
        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        entities = [
            _entity(
                "char-1",
                "character",
                "Alice",
                "A warrior.",
                updated_at=recent,
                metadata={"speech": {"dialect": "Southern"}},
            ),
        ]
        result, warnings = extract_voice_profiles(entities, max_age_days=30)
        assert "**Alice**" in result
        assert warnings == []


# ---------------------------------------------------------------------------
# Test: WritingContext
# ---------------------------------------------------------------------------


class TestWritingContextVoiceProfiles:
    """character_voice_profiles field in WritingContext."""

    def test_writing_context_voice_profiles_in_variables(
        self,
        context: WritingContext,
    ) -> None:
        """to_prompt_variables() includes character_voice_profiles."""
        variables = context.to_prompt_variables()
        assert "character_voice_profiles" in variables
        assert variables["character_voice_profiles"] == context.character_voice_profiles

    def test_writing_context_voice_profiles_defaults_empty(self) -> None:
        """Default character_voice_profiles is empty string."""
        ctx = WritingContext()
        assert ctx.character_voice_profiles == ""
        variables = ctx.to_prompt_variables()
        assert variables["character_voice_profiles"] == ""


# ---------------------------------------------------------------------------
# Test: PromptContext
# ---------------------------------------------------------------------------


class TestPromptContextVoiceProfiles:
    """character_voice_profiles field in PromptContext."""

    def test_prompt_context_voice_profiles_in_variables(self) -> None:
        """as_variables() includes character_voice_profiles."""
        pc = PromptContext(character_voice_profiles="**Alice**: dialect: Southern")
        variables = pc.as_variables()
        assert "character_voice_profiles" in variables
        assert variables["character_voice_profiles"] == "**Alice**: dialect: Southern"

    def test_prompt_context_voice_profiles_defaults_empty(self) -> None:
        """Default character_voice_profiles is empty string."""
        pc = PromptContext()
        assert pc.character_voice_profiles == ""
        variables = pc.as_variables()
        assert variables["character_voice_profiles"] == ""
