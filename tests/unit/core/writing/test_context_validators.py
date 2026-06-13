"""Tests for writing/context_validators.py — voice profile freshness checks.

Covers uncovered lines 68-83: ``check_voice_profile_freshness``.
Tests character entities with stale/fresh/no-voice-profile metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.context_validators import check_voice_profile_freshness


def _stale_character(name: str = "Aria", max_age_days: int = 30) -> KBEntity:
    """Create a character entity with a stale voice profile."""
    stale_date = (datetime.now(UTC) - timedelta(days=max_age_days + 10)).isoformat()
    return KBEntity(
        entity_id=f"char-{name}",
        entity_type="character",
        name=name,
        content="A brave warrior.",
        updated_at=stale_date,
        metadata={
            "speech": {"dialect": "Northern", "vocabulary_quirks": "uses 'aye'"},
        },
    )


def _fresh_character(name: str = "Marcus") -> KBEntity:
    """Create a character entity with a fresh voice profile."""
    fresh_date = datetime.now(UTC).isoformat()
    return KBEntity(
        entity_id=f"char-{name}",
        entity_type="character",
        name=name,
        content="A wise sage.",
        updated_at=fresh_date,
        metadata={
            "speech": {"dialect": "Formal"},
        },
    )


def _character_no_metadata(name: str = "Unnamed") -> KBEntity:
    """Create a character entity without speech metadata."""
    return KBEntity(
        entity_id=f"char-{name}",
        entity_type="character",
        name=name,
        content="A mysterious figure.",
        updated_at="2020-01-01T00:00:00+00:00",
        metadata=None,
    )


def _character_no_speech(name: str = "Silent") -> KBEntity:
    """Create a character entity with metadata but no speech block."""
    return KBEntity(
        entity_id=f"char-{name}",
        entity_type="character",
        name=name,
        content="A quiet person.",
        updated_at="2020-01-01T00:00:00+00:00",
        metadata={"personality": {"traits": ["quiet"]}},
    )


def _location(name: str = "Forest") -> KBEntity:
    """Create a non-character entity."""
    return KBEntity(
        entity_id=f"loc-{name}",
        entity_type="location",
        name=name,
        content="A dark forest.",
    )


class TestCheckVoiceProfileFreshness:
    def test_stale_character_returns_warning(self) -> None:
        """Character with stale voice profile produces a warning."""
        entities = [_stale_character(max_age_days=30)]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert len(warnings) == 1
        assert "Aria" in warnings[0]
        assert "stale" in warnings[0].lower() or "30" in warnings[0]

    def test_fresh_character_returns_no_warning(self) -> None:
        """Character with fresh voice profile produces no warning."""
        entities = [_fresh_character()]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert warnings == []

    def test_character_no_metadata_returns_no_warning(self) -> None:
        """Character without metadata is skipped."""
        entities = [_character_no_metadata()]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert warnings == []

    def test_character_no_speech_data_returns_no_warning(self) -> None:
        """Character with metadata but no speech block is skipped."""
        entities = [_character_no_speech()]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert warnings == []

    def test_non_character_entities_ignored(self) -> None:
        """Only character entities are checked for voice profile freshness."""
        entities = [_location()]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert warnings == []

    def test_mixed_entities_only_warns_stale_characters(self) -> None:
        """Only stale characters produce warnings among mixed entities."""
        entities = [
            _stale_character("Aria", max_age_days=30),
            _fresh_character("Marcus"),
            _location("Forest"),
            _character_no_metadata("Unnamed"),
        ]
        warnings = check_voice_profile_freshness(entities, max_age_days=30)
        assert len(warnings) == 1
        assert "Aria" in warnings[0]

    def test_empty_entity_list_returns_no_warnings(self) -> None:
        """Empty entity list returns no warnings."""
        warnings = check_voice_profile_freshness([], max_age_days=30)
        assert warnings == []

    def test_character_with_irrelevant_metadata_no_speech_skipped(self) -> None:
        """Entity with metadata other than speech/personality is skipped (line 79)."""
        char = KBEntity(
            entity_id="char-silent",
            entity_type="character",
            name="Silent",
            content="A silent figure.",
            updated_at="2020-01-01T00:00:00+00:00",
            metadata={"irrelevant_key": "some_value"},
        )
        warnings = check_voice_profile_freshness([char], max_age_days=30)
        assert warnings == []
