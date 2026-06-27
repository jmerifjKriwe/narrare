"""Unit tests for enriched CharacterMetadata schema with nested groups.

Tests cover:
- CharacterMetadata with flat fields (backward compat)
- CharacterMetadata with nested group fields
- Nested group models have extra="allow"
- Extra fields preserved on both metadata and nested groups
- Validation constraints maintained
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from narrare_core.kb.schemas import (
    AppearanceFields,
    BackgroundFields,
    CharacterMetadata,
    DevelopmentFields,
    PersonalityFields,
    RelationshipFields,
    SpeechPatterns,
    VoiceAnalysis,
    VoiceMetrics,
)


class TestAppearanceFields:
    """Tests for the AppearanceFields nested group model."""

    def test_all_optional(self) -> None:
        fields = AppearanceFields()
        assert fields.height is None
        assert fields.build is None

    def test_with_data(self) -> None:
        fields = AppearanceFields(
            height="6'0\"",
            build="athletic",
            hair_color="brown",
            eye_color="green",
        )
        assert fields.height == "6'0\""
        assert fields.hair_color == "brown"

    def test_extra_fields_preserved(self) -> None:
        fields: Any = AppearanceFields(**cast("Any", {"height": "5'8\"", "tattoo": "dragon"}))
        assert fields.tattoo == "dragon"

    def test_model_config_extra_allow(self) -> None:
        assert AppearanceFields.model_config.get("extra") == "allow"


class TestPersonalityFields:
    """Tests for the PersonalityFields nested group model."""

    def test_all_optional(self) -> None:
        fields = PersonalityFields()
        assert fields.traits is None
        assert fields.quirks is None

    def test_with_data(self) -> None:
        fields = PersonalityFields(
            traits=["brave", "curious"],
            strengths=["determination"],
            weaknesses=["stubbornness"],
        )
        assert fields.traits == ["brave", "curious"]
        assert fields.strengths == ["determination"]

    def test_extra_fields_preserved(self) -> None:
        fields: Any = PersonalityFields(**cast("Any", {"mbti": "INTJ", "traits": ["analytical"]}))
        assert fields.mbti == "INTJ"


class TestBackgroundFields:
    """Tests for the BackgroundFields nested group model."""

    def test_all_optional(self) -> None:
        fields = BackgroundFields()
        assert fields.family is None
        assert fields.key_events is None

    def test_with_data(self) -> None:
        fields = BackgroundFields(
            family="Noble family",
            upbringing="Strict",
            key_events=["Left home", "Met mentor"],
        )
        assert fields.family == "Noble family"
        assert fields.key_events is not None
        assert len(fields.key_events) == 2


class TestSpeechPatterns:
    """Tests for the SpeechPatterns nested group model."""

    def test_all_optional(self) -> None:
        fields = SpeechPatterns()
        assert fields.dialect is None
        assert fields.typical_phrases is None
        assert fields.voice_analysis is None

    def test_with_data(self) -> None:
        fields = SpeechPatterns(
            typical_phrases=["Indeed", "Fascinating"],
            dialect="Upper class",
        )
        assert fields.typical_phrases is not None
        assert "Indeed" in fields.typical_phrases

    def test_voice_analysis_field_optional(self) -> None:
        """voice_analysis defaults to None (migration-free additive field)."""
        fields = SpeechPatterns(dialect="Southern")
        assert fields.voice_analysis is None

    def test_with_only_voice_analysis(self) -> None:
        """SpeechPatterns with only machine-derived voice_analysis (no human
        fields) round-trips. Required case: ADR-055 Decision 1."""
        fields = SpeechPatterns(
            voice_analysis=VoiceAnalysis(
                formality=0.8,
                vocabulary_level="complex",
            ),
        )
        assert fields.typical_phrases is None
        assert fields.dialect is None
        assert fields.voice_analysis is not None
        assert fields.voice_analysis.formality == 0.8
        assert fields.voice_analysis.vocabulary_level == "complex"

    def test_voice_analysis_round_trip(self) -> None:
        """Full speech block (human + machine) survives serialize→deserialize."""
        original = SpeechPatterns(
            typical_phrases=["Indeed"],
            dialect="Upper class",
            voice_analysis=VoiceAnalysis(
                formality=0.9,
                vocabulary_level="complex",
                sentence_profile="varied",
                emotional_range="expressive",
                cultural_regional_markers="Edwardian upper class",
                voice_examples=["Indeed, how fascinating."],
                voice_metrics=VoiceMetrics(
                    avg_sentence_length=18.5,
                    type_token_ratio=0.72,
                    verbal_tic_frequency={"indeed": 0.12},
                ),
            ),
        )
        dumped = original.model_dump()
        restored = SpeechPatterns.model_validate(dumped)
        assert restored.dialect == "Upper class"
        assert restored.voice_analysis is not None
        assert restored.voice_analysis.formality == 0.9
        assert restored.voice_analysis.voice_metrics is not None
        assert restored.voice_analysis.voice_metrics.avg_sentence_length == 18.5
        assert restored.voice_analysis.voice_metrics.verbal_tic_frequency == {"indeed": 0.12}

    def test_backward_compat_existing_row_without_voice_analysis(self) -> None:
        """Existing rows (no voice_analysis key) deserialize unchanged —
        migration-free claim verified (required case 2)."""
        existing_row: dict[str, Any] = {
            "typical_phrases": ["y'all", "reckon"],
            "dialect": "Southern",
            "vocabulary_quirks": "archaic forms",
            "body_language": "drawls while leaning",
        }
        restored = SpeechPatterns.model_validate(existing_row)
        assert restored.dialect == "Southern"
        assert restored.vocabulary_quirks == "archaic forms"
        assert restored.typical_phrases == ["y'all", "reckon"]
        assert restored.body_language == "drawls while leaning"
        # The additive field is absent → None (no validation error).
        assert restored.voice_analysis is None


class TestVoiceMetrics:
    """Tests for the VoiceMetrics deterministic-metric sub-model (ADR-055)."""

    def test_all_none_default(self) -> None:
        """All metric fields default to None (existing rows deserialize
        unchanged — migration-free claim, required case 1)."""
        metrics = VoiceMetrics()
        assert metrics.avg_sentence_length is None
        assert metrics.sentence_length_std is None
        assert metrics.type_token_ratio is None
        assert metrics.avg_syllables_per_word is None
        assert metrics.contraction_rate is None
        assert metrics.verbal_tic_frequency is None
        assert metrics.punctuation_profile is None

    def test_model_config_extra_allow(self) -> None:
        """Metrics block is forward-extensible without migration."""
        assert VoiceMetrics.model_config.get("extra") == "allow"

    def test_extra_fields_preserved(self) -> None:
        """extra='allow' lets future ANAL-009/WRITE-010 metrics extend the
        block without a schema migration."""
        metrics: Any = VoiceMetrics(
            **cast("Any", {"avg_sentence_length": 12.3, "future_metric": 0.5})
        )
        assert metrics.avg_sentence_length == 12.3
        assert metrics.future_metric == 0.5

    def test_round_trip(self) -> None:
        """Serialize→deserialize preserves all fields (required case 1)."""
        original = VoiceMetrics(
            avg_sentence_length=15.2,
            sentence_length_std=4.1,
            type_token_ratio=0.68,
            avg_syllables_per_word=1.4,
            contraction_rate=0.22,
            verbal_tic_frequency={"indeed": 0.11, "rather": 0.07},
            punctuation_profile={";": 0.3, "—": 0.15},
        )
        restored = VoiceMetrics.model_validate(original.model_dump())
        assert restored.avg_sentence_length == 15.2
        assert restored.verbal_tic_frequency == {"indeed": 0.11, "rather": 0.07}
        assert restored.punctuation_profile == {";": 0.3, "—": 0.15}


class TestVoiceAnalysis:
    """Tests for the VoiceAnalysis machine-derived sub-model (ADR-055)."""

    def test_all_none_default(self) -> None:
        """All descriptive + metric fields default to None (required case 1)."""
        analysis = VoiceAnalysis()
        assert analysis.formality is None
        assert analysis.vocabulary_level is None
        assert analysis.sentence_profile is None
        assert analysis.emotional_range is None
        assert analysis.cultural_regional_markers is None
        assert analysis.voice_examples is None
        assert analysis.voice_metrics is None

    def test_model_config_extra_allow(self) -> None:
        assert VoiceAnalysis.model_config.get("extra") == "allow"

    def test_round_trip(self) -> None:
        """Serialize→deserialize preserves descriptive + metric groups
        (required case 1)."""
        original = VoiceAnalysis(
            formality=0.35,
            vocabulary_level="moderate",
            sentence_profile="medium",
            emotional_range="moderate",
            cultural_regional_markers="Pacific Northwest",
            voice_examples=["Yeah, no, totally.", "I mean, right?"],
            voice_metrics=VoiceMetrics(avg_sentence_length=8.1),
        )
        restored = VoiceAnalysis.model_validate(original.model_dump())
        assert restored.formality == 0.35
        assert restored.vocabulary_level == "moderate"
        assert restored.voice_examples == ["Yeah, no, totally.", "I mean, right?"]
        assert restored.voice_metrics is not None
        assert restored.voice_metrics.avg_sentence_length == 8.1

    def test_metric_group_optional(self) -> None:
        """Descriptive-only analysis (no metrics) round-trips cleanly."""
        analysis = VoiceAnalysis(formality=0.5, vocabulary_level="moderate")
        assert analysis.voice_metrics is None
        restored = VoiceAnalysis.model_validate(analysis.model_dump())
        assert restored.voice_metrics is None
        assert restored.vocabulary_level == "moderate"


class TestRelationshipFields:
    """Tests for the RelationshipFields nested group model."""

    def test_all_optional(self) -> None:
        fields = RelationshipFields()
        assert fields.allies is None

    def test_with_data(self) -> None:
        fields = RelationshipFields(
            allies=["Alice", "Bob"],
            rivals=["Malice"],
            notes="Secretly related",
        )
        assert fields.notes == "Secretly related"


class TestDevelopmentFields:
    """Tests for the DevelopmentFields nested group model."""

    def test_all_optional(self) -> None:
        fields = DevelopmentFields()
        assert fields.starting_point is None

    def test_with_data(self) -> None:
        fields = DevelopmentFields(
            starting_point="Farm boy",
            key_turning_points=["Leaves home", "Defeats villain"],
            planned_arc="Hero's journey",
        )
        assert fields.planned_arc == "Hero's journey"


class TestCharacterMetadataEnriched:
    """Tests for CharacterMetadata with nested groups."""

    def test_flat_fields_only(self) -> None:
        """Backward compat: flat fields still work."""
        meta = CharacterMetadata(
            age=30,
            role="protagonist",
            aliases=["Hero"],
        )
        assert meta.age == 30
        assert meta.role == "protagonist"

    def test_with_nested_groups(self) -> None:
        meta = CharacterMetadata(
            age=25,
            appearance=AppearanceFields(
                height="5'10\"",
                hair_color="blonde",
            ),
            personality=PersonalityFields(
                traits=["bold"],
                motivations="To find the truth",
            ),
            background=BackgroundFields(
                family="Merchant family",
                upbringing="Privileged",
            ),
        )
        assert meta.age == 25
        assert meta.appearance is not None
        assert meta.appearance.height == "5'10\""
        assert meta.personality is not None
        assert meta.personality.motivations == "To find the truth"
        assert meta.background is not None
        assert meta.background.family == "Merchant family"

    def test_nested_groups_optional(self) -> None:
        """Nested groups should be None when not provided."""
        meta = CharacterMetadata(age=30)
        assert meta.appearance is None
        assert meta.personality is None
        assert meta.background is None
        assert meta.speech is None
        assert meta.relationships is None
        assert meta.development is None

    def test_all_groups(self) -> None:
        """All six nested groups should work together."""
        meta = CharacterMetadata(
            appearance=AppearanceFields(height="6'0\""),
            personality=PersonalityFields(traits=["kind"]),
            background=BackgroundFields(education="Self-taught"),
            speech=SpeechPatterns(dialect="Southern"),
            relationships=RelationshipFields(allies=["Friend"]),
            development=DevelopmentFields(current_state="Mid-journey"),
        )
        assert meta.appearance is not None
        assert meta.personality is not None
        assert meta.background is not None
        assert meta.speech is not None
        assert meta.relationships is not None
        assert meta.development is not None

    def test_extra_fields_on_metadata(self) -> None:
        """Extra fields should be preserved (inherited from KBEntryMetadata)."""
        meta: Any = CharacterMetadata(**cast("Any", {"age": 30, "custom_flag": True}))
        assert meta.custom_flag is True

    def test_extra_fields_in_group(self) -> None:
        """Extra fields within nested groups should be preserved."""
        meta: Any = CharacterMetadata(
            appearance=AppearanceFields(
                **cast("Any", {"height": "5'5\"", "extra_attribute": "custom"})
            ),
        )
        assert meta.appearance is not None
        assert meta.appearance.extra_attribute == "custom"

    def test_validation_maintained(self) -> None:
        """Type validation should still work for flat fields."""
        with pytest.raises(ValidationError, match="age"):
            CharacterMetadata.model_validate({"age": "not a number"})

    def test_empty_metadata(self) -> None:
        """Empty metadata should pass validation."""
        meta = CharacterMetadata()
        assert meta.age is None
        assert meta.role is None

    def test_model_dump_includes_groups(self) -> None:
        """Serialisation should include nested groups."""
        meta = CharacterMetadata(
            appearance=AppearanceFields(height="6'2\""),
        )
        dumped = meta.model_dump()
        assert dumped["appearance"] is not None
        assert dumped["appearance"]["height"] == "6'2\""
