"""Tests for voice_analysis rendering and the speech-block freshness signal.

Split out of ``test_voice_extraction.py`` to satisfy RULE-04 (test hard limit
= 400 lines). No logic change — every assertion is preserved verbatim.

Covers (ADR-055 required cases 4-7):
4. voice_analysis descriptive group rendered into the speech summary.
5. Raw ``voice_metrics`` NEVER reach generation.
6. Characters WITHOUT voice_analysis render identically (no regression).
7. ``has_speech_block`` treats a voice_analysis-only speech dict as present.
"""

from __future__ import annotations

from typing import Any

from narrare_core.profiles._voice_extraction import (
    build_character_voice_profile,
    get_speech_data,
    has_speech_block,
)

# ---------------------------------------------------------------------------
# voice_analysis rendering (ADR-055 — descriptive rendered, metrics excluded)
# ---------------------------------------------------------------------------


def _full_voice_analysis_metadata() -> dict[str, Any]:
    """Metadata with a complete machine-derived voice_analysis block."""
    return {
        "speech": {
            "voice_analysis": {
                "formality": 0.9,
                "vocabulary_level": "complex",
                "sentence_profile": "varied",
                "emotional_range": "expressive",
                "cultural_regional_markers": "Edwardian upper class",
                "voice_examples": ["Indeed, how fascinating.", "Rather."],
                "voice_metrics": {
                    "avg_sentence_length": 18.5,
                    "type_token_ratio": 0.72,
                    "verbal_tic_frequency": {"indeed": 0.12},
                    "punctuation_profile": {";": 0.3},
                },
            },
        },
    }


class TestVoiceAnalysisRendering:
    """get_speech_data renders the descriptive group (ADR-055 required cases
    4 & 5): descriptive fields rendered, metrics excluded."""

    def test_renders_descriptive_fields(self) -> None:
        """Required case 4: descriptive group rendered into the summary."""
        result = get_speech_data(_full_voice_analysis_metadata())
        assert "voice: formal" in result
        assert "vocabulary level: complex" in result
        assert "sentence profile: varied" in result
        assert "emotional range: expressive" in result
        assert "markers: Edwardian upper class" in result
        assert "voice examples:" in result
        assert "Indeed, how fascinating." in result
        assert "Rather." in result

    def test_does_not_render_voice_metrics(self) -> None:
        """Required case 5: raw metrics NEVER reach generation."""
        result = get_speech_data(_full_voice_analysis_metadata())
        # The metric numbers must be absent.
        assert "18.5" not in result
        assert "0.72" not in result
        assert "0.12" not in result
        # The metric block key/field names must be absent.
        assert "avg_sentence_length" not in result
        assert "type_token_ratio" not in result
        assert "verbal_tic_frequency" not in result
        assert "punctuation_profile" not in result
        assert "voice_metrics" not in result

    def test_formality_thresholds_map_to_register(self) -> None:
        """formality float (0.0-1.0) → prompt-friendly register descriptor."""
        for formality, expected in [
            (0.1, "voice: casual"),
            (0.33, "voice: casual"),
            (0.4, "voice: balanced"),
            (0.5, "voice: balanced"),
            (0.66, "voice: balanced"),
            (0.67, "voice: formal"),
            (0.9, "voice: formal"),
        ]:
            metadata: dict[str, Any] = {
                "speech": {"voice_analysis": {"formality": formality}},
            }
            assert expected in get_speech_data(metadata), (
                f"formality={formality} should render '{expected}'"
            )

    def test_renders_human_fields_plus_voice_analysis(self) -> None:
        """Human-authored fields and machine descriptive group coexist."""
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {"formality": 0.2, "vocabulary_level": "simple"},
            },
        }
        result = get_speech_data(metadata)
        assert "dialect: Southern" in result
        assert "voice: casual" in result
        assert "vocabulary level: simple" in result

    def test_empty_voice_analysis_renders_nothing(self) -> None:
        """voice_analysis present but all-None / empty → graceful, no crash
        (RULE-11), no stray rendering."""
        metadata: dict[str, Any] = {
            "speech": {"voice_analysis": {}},
        }
        assert get_speech_data(metadata) == ""

    def test_metric_only_voice_analysis_renders_nothing(self) -> None:
        """A voice_analysis carrying ONLY metrics (no descriptive fields) must
        render nothing — metrics never reach generation."""
        metadata: dict[str, Any] = {
            "speech": {
                "voice_analysis": {
                    "voice_metrics": {"avg_sentence_length": 12.0},
                },
            },
        }
        assert get_speech_data(metadata) == ""


class TestGetSpeechDataRegression:
    """Required case 6: characters WITHOUT voice_analysis render identically
    to today (no regression on the generation path)."""

    def test_human_fields_only_unchanged_string(self) -> None:
        """Exact-string regression guard matching current behaviour."""
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "vocabulary_quirks": "archaic forms",
                "typical_phrases": ["y'all", "reckon"],
                "body_language": "drawls while leaning",
            },
            "personality": {"traits": ["warm", "diplomatic"]},
        }
        assert get_speech_data(metadata) == (
            "dialect: Southern; vocabulary: archaic forms; "
            "typical phrases: y'all, reckon; "
            "body language: drawls while leaning; "
            "personality traits: warm, diplomatic"
        )


# ---------------------------------------------------------------------------
# has_speech_block (freshness signal — required case 7)
# ---------------------------------------------------------------------------


class TestHasSpeechBlock:
    """has_speech_block behaviour, including voice_analysis-only characters
    (required case 7). Decision: NO change needed — ``bool(speech_raw)`` already
    returns True when the speech dict carries a voice_analysis sub-dict, so a
    machine-derived voice counts as a voice block for freshness tracking."""

    def test_false_on_non_dict(self) -> None:
        assert has_speech_block(None) is False
        assert has_speech_block("nope") is False

    def test_false_on_empty_metadata(self) -> None:
        assert has_speech_block({}) is False

    def test_false_when_no_speech_key(self) -> None:
        assert has_speech_block({"personality": {"traits": ["brave"]}}) is False

    def test_false_when_speech_empty(self) -> None:
        assert has_speech_block({"speech": {}}) is False

    def test_true_for_human_speech_fields(self) -> None:
        assert has_speech_block({"speech": {"dialect": "Southern"}}) is True

    def test_true_for_voice_analysis_only(self) -> None:
        """Required case 7: a character with machine-derived voice_analysis but
        empty human fields counts as having a voice block for freshness."""
        assert has_speech_block({"speech": {"voice_analysis": {"formality": 0.5}}}) is True

    def test_builds_profile_for_voice_analysis_only(self) -> None:
        """End-to-end: voice_analysis-only character yields a profile (its
        descriptive group renders), so freshness tracking is meaningful."""
        metadata: dict[str, Any] = {
            "speech": {"voice_analysis": {"formality": 0.8}},
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert "voice: formal" in result.speech_summary
