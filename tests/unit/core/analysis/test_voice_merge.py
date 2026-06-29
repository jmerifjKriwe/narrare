"""Tests for merge_character_voice — pure merge of agent output + metrics -> VoiceAnalysis.

Verifies ADR-055 Decision 1 persistence scope:
- Intrinsic qualitative fields are mapped into VoiceAnalysis.
- distinctiveness_notes is EXCLUDED (per-run comparison artifact).
- Deterministic metrics land in voice_analysis.voice_metrics.
- Missing/empty inputs degrade gracefully (RULE-11).
"""

from __future__ import annotations

from narrare_core.agents.character_voice_types import CharacterVoiceEntry
from narrare_core.analysis.voice_merge import merge_character_voice
from narrare_core.kb.schemas.character import VoiceAnalysis, VoiceMetrics

# ---------------------------------------------------------------------------
# Happy path — full qualitative + metrics
# ---------------------------------------------------------------------------


class TestMergeHappyPath:
    """merge_character_voice maps all intrinsic fields correctly."""

    def test_maps_all_qualitative_fields(self) -> None:
        entry = CharacterVoiceEntry(
            character_name="Elena",
            formality=0.8,
            vocabulary_level="complex",
            sentence_profile="varied",
            emotional_range="expressive",
            cultural_regional_markers="formal register, archaic idioms",
            voice_examples=["I dare say, this is remarkable.", "Indeed, quite so."],
            distinctiveness_notes="More formal than Marc.",
        )
        metrics = VoiceMetrics(
            avg_sentence_length=12.5,
            type_token_ratio=0.72,
        )

        result = merge_character_voice(entry, metrics)

        assert isinstance(result, VoiceAnalysis)
        assert result.formality == 0.8
        assert result.vocabulary_level == "complex"
        assert result.sentence_profile == "varied"
        assert result.emotional_range == "expressive"
        assert result.cultural_regional_markers == "formal register, archaic idioms"
        assert result.voice_examples == ["I dare say, this is remarkable.", "Indeed, quite so."]

    def test_metrics_land_in_voice_metrics(self) -> None:
        entry = CharacterVoiceEntry(character_name="Marc")
        metrics = VoiceMetrics(
            avg_sentence_length=5.2,
            sentence_length_std=1.1,
            type_token_ratio=0.55,
            avg_syllables_per_word=1.3,
            contraction_rate=0.15,
        )

        result = merge_character_voice(entry, metrics)

        assert result.voice_metrics is not None
        assert result.voice_metrics.avg_sentence_length == 5.2
        assert result.voice_metrics.sentence_length_std == 1.1
        assert result.voice_metrics.type_token_ratio == 0.55
        assert result.voice_metrics.avg_syllables_per_word == 1.3
        assert result.voice_metrics.contraction_rate == 0.15


# ---------------------------------------------------------------------------
# distinctiveness_notes exclusion (ADR-055 persistence scope)
# ---------------------------------------------------------------------------


class TestDistinctivenessNotesExcluded:
    """distinctiveness_notes is NOT persisted on VoiceAnalysis."""

    def test_distinctiveness_notes_not_in_result(self) -> None:
        entry = CharacterVoiceEntry(
            character_name="Elena",
            distinctiveness_notes="More formal than Marc.",
        )
        result = merge_character_voice(entry, VoiceMetrics())
        # VoiceAnalysis has no distinctiveness_notes field — it should not
        # appear anywhere in the result.
        assert not hasattr(result, "distinctiveness_notes")
        # extra="allow" means it COULD be set via model_copy, but the merge
        # function must not set it. Verify it's absent from the model dump.
        dumped = result.model_dump()
        assert "distinctiveness_notes" not in dumped

    def test_distinctiveness_notes_none_also_excluded(self) -> None:
        entry = CharacterVoiceEntry(
            character_name="Elena",
            distinctiveness_notes=None,
        )
        result = merge_character_voice(entry, None)
        dumped = result.model_dump()
        assert "distinctiveness_notes" not in dumped


# ---------------------------------------------------------------------------
# Graceful degradation (RULE-11)
# ---------------------------------------------------------------------------


class TestMergeGracefulDegradation:
    """Missing/empty inputs degrade gracefully."""

    def test_none_metrics_produces_none_voice_metrics(self) -> None:
        entry = CharacterVoiceEntry(character_name="Elena")
        result = merge_character_voice(entry, None)
        assert result.voice_metrics is None

    def test_empty_voice_examples_produces_none(self) -> None:
        entry = CharacterVoiceEntry(character_name="Elena", voice_examples=[])
        result = merge_character_voice(entry, None)
        assert result.voice_examples is None

    def test_none_cultural_markers_preserved(self) -> None:
        entry = CharacterVoiceEntry(
            character_name="Elena",
            cultural_regional_markers=None,
        )
        result = merge_character_voice(entry, None)
        assert result.cultural_regional_markers is None

    def test_default_entry_values_mapped(self) -> None:
        """A default-constructed entry maps to sensible VoiceAnalysis defaults."""
        entry = CharacterVoiceEntry()
        result = merge_character_voice(entry, None)
        assert result.formality == 0.5
        assert result.vocabulary_level == "moderate"
        assert result.sentence_profile == "medium"
        assert result.emotional_range == "moderate"
        assert result.voice_examples is None
        assert result.voice_metrics is None

    def test_empty_metrics_object_preserved(self) -> None:
        """An all-None VoiceMetrics is still set (not dropped to None)."""
        entry = CharacterVoiceEntry(character_name="Elena")
        metrics = VoiceMetrics()
        result = merge_character_voice(entry, metrics)
        assert result.voice_metrics is not None
        assert result.voice_metrics.avg_sentence_length is None


# ---------------------------------------------------------------------------
# Voice examples list copy (immutability)
# ---------------------------------------------------------------------------


class TestMergeImmutability:
    """The merge function does not mutate the input entry's voice_examples."""

    def test_voice_examples_copied(self) -> None:
        examples = ["Hello.", "Goodbye."]
        entry = CharacterVoiceEntry(
            character_name="Elena",
            voice_examples=examples,
        )
        result = merge_character_voice(entry, None)
        assert result.voice_examples == examples
        # Mutating the original list must not affect the result.
        examples.append("New quote.")
        assert "New quote." not in (result.voice_examples or [])
