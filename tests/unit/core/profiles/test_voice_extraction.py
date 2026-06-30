"""Tests for voice extraction logic.

Covers:
1. get_speech_data — empty, partial, full metadata
2. _extract_speech_parts — non-dict, speech dict, personality dict
3. build_character_voice_profile — all paths
4. _add_str_field, _add_list_field — edge cases

Voice-analysis rendering tests live in ``test_voice_analysis_rendering.py``.
"""

from __future__ import annotations

from typing import Any

from narrare_core.profiles._voice_extraction import (
    _add_list_field,
    _add_str_field,
    _extract_speech_parts,
    build_character_voice_profile,
    get_speech_data,
)

# ---------------------------------------------------------------------------
# _add_str_field
# ---------------------------------------------------------------------------


class TestAddStrField:
    """_add_str_field helper edge cases."""

    def test_appends_when_string_present(self) -> None:
        parts: list[str] = []
        _add_str_field({"key": "value"}, "key", "Label", parts)
        assert parts == ["Label: value"]

    def test_skips_empty_string(self) -> None:
        parts: list[str] = []
        _add_str_field({"key": ""}, "key", "Label", parts)
        assert parts == []

    def test_skips_non_string(self) -> None:
        parts: list[str] = []
        _add_str_field({"key": 42}, "key", "Label", parts)  # type: ignore[dict-item]
        assert parts == []

    def test_skips_missing_key(self) -> None:
        parts: list[str] = []
        _add_str_field({}, "key", "Label", parts)
        assert parts == []


# ---------------------------------------------------------------------------
# _add_list_field
# ---------------------------------------------------------------------------


class TestAddListField:
    """_add_list_field helper edge cases."""

    def test_appends_list_items(self) -> None:
        parts: list[str] = []
        _add_list_field({"key": ["a", "b"]}, "key", "Items", parts)
        assert parts == ["Items: a, b"]

    def test_truncates_to_max_items(self) -> None:
        parts: list[str] = []
        _add_list_field({"key": [1, 2, 3, 4, 5, 6]}, "key", "Items", parts, max_items=3)
        assert parts == ["Items: 1, 2, 3"]

    def test_skips_empty_list(self) -> None:
        parts: list[str] = []
        _add_list_field({"key": []}, "key", "Items", parts)
        assert parts == []

    def test_skips_non_list(self) -> None:
        parts: list[str] = []
        _add_list_field({"key": "not a list"}, "key", "Items", parts)  # type: ignore[dict-item]
        assert parts == []


# ---------------------------------------------------------------------------
# _extract_speech_parts
# ---------------------------------------------------------------------------


class TestExtractSpeechParts:
    """_extract_speech_parts with various metadata shapes."""

    def test_empty_on_non_dict(self) -> None:
        assert _extract_speech_parts("not a dict") == []
        assert _extract_speech_parts(None) == []
        assert _extract_speech_parts(42) == []

    def test_extracts_speech_fields(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "vocabulary_quirks": "archaic forms",
                "typical_phrases": ["y'all", "reckon"],
                "body_language": "drawls while leaning",
            },
        }
        parts = _extract_speech_parts(metadata)
        assert "dialect: Southern" in parts
        assert "vocabulary: archaic forms" in parts
        assert "typical phrases: y'all, reckon" in parts
        assert "body language: drawls while leaning" in parts

    def test_extracts_personality_traits(self) -> None:
        metadata: dict[str, Any] = {
            "personality": {
                "traits": ["warm", "diplomatic", "patient"],
            },
        }
        parts = _extract_speech_parts(metadata)
        assert "personality traits: warm, diplomatic, patient" in parts

    def test_ignores_non_dict_speech(self) -> None:
        metadata: dict[str, Any] = {
            "speech": "not a dict",
        }
        parts = _extract_speech_parts(metadata)
        assert parts == []

    def test_ignores_non_list_traits(self) -> None:
        metadata: dict[str, Any] = {
            "personality": {"traits": "not a list"},
        }
        parts = _extract_speech_parts(metadata)
        assert parts == []

    def test_extracts_both_speech_and_personality(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {"dialect": "Southern"},
            "personality": {"traits": ["brave"]},
        }
        parts = _extract_speech_parts(metadata)
        assert len(parts) == 2


# ---------------------------------------------------------------------------
# get_speech_data
# ---------------------------------------------------------------------------


class TestGetSpeechData:
    """get_speech_data top-level extraction."""

    def test_empty_on_none(self) -> None:
        assert get_speech_data(None) == ""

    def test_empty_on_empty_dict(self) -> None:
        assert get_speech_data({}) == ""

    def test_empty_on_non_dict(self) -> None:
        assert get_speech_data("string") == ""

    def test_returns_semicolon_joined(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {"dialect": "Southern"},
            "personality": {"traits": ["brave"]},
        }
        result = get_speech_data(metadata)
        assert "dialect: Southern" in result
        assert "personality traits: brave" in result
        assert "; " in result

    def test_partial_metadata(self) -> None:
        """Only personality, no speech."""
        metadata: dict[str, Any] = {
            "personality": {"traits": ["sly"]},
        }
        result = get_speech_data(metadata)
        assert "personality traits: sly" in result


# ---------------------------------------------------------------------------
# build_character_voice_profile
# ---------------------------------------------------------------------------


class TestBuildCharacterVoiceProfile:
    """build_character_voice_profile integration tests."""

    def test_returns_none_when_no_speech_data(self) -> None:
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata=None,
        )
        assert result is None

    def test_returns_none_when_metadata_has_no_speech(self) -> None:
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata={"other": "data"},
        )
        assert result is None

    def test_returns_profile_with_speech_data(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {"dialect": "Southern"},
        }
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata=metadata,
        )
        assert result is not None
        assert result.character_id == "c1"
        assert result.name == "Alice"
        assert "dialect: Southern" in result.speech_summary
        assert result.is_fresh is True

    def test_fresh_when_no_updated_at(self) -> None:
        metadata: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata=metadata,
            updated_at=None,
        )
        assert result is not None
        assert result.is_fresh is True

    def test_stale_when_old_updated_at(self) -> None:
        from datetime import UTC, datetime, timedelta

        old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        metadata: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata=metadata,
            updated_at=old,
            max_age_days=30,
        )
        assert result is not None
        assert result.is_fresh is False

    def test_fresh_when_recent_updated_at(self) -> None:
        from datetime import UTC, datetime, timedelta

        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        metadata: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        result = build_character_voice_profile(
            entity_id="c1",
            name="Alice",
            metadata=metadata,
            updated_at=recent,
            max_age_days=30,
        )
        assert result is not None
        assert result.is_fresh is True


# ---------------------------------------------------------------------------
# build_character_voice_profile — voice_metrics surfacing (ADR-057 Decision 1)
# ---------------------------------------------------------------------------


class TestBuildCharacterVoiceProfileVoiceMetrics:
    """ADR-057: the builder surfaces structured voice_metrics on the checking
    path, parsed from ``speech.voice_analysis.voice_metrics``. Graceful
    (RULE-11): absent/empty/malformed → None, never a crash. The descriptive
    ``speech_summary`` is unchanged (CR-04)."""

    def test_voice_metrics_populated_when_present(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {
                    "formality": 0.9,
                    "voice_metrics": {
                        "avg_sentence_length": 18.5,
                        "type_token_ratio": 0.72,
                        "verbal_tic_frequency": {"indeed": 0.12},
                        "punctuation_profile": {";": 0.3},
                    },
                },
            },
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is not None
        assert result.voice_metrics.avg_sentence_length == 18.5
        assert result.voice_metrics.type_token_ratio == 0.72
        assert result.voice_metrics.verbal_tic_frequency == {"indeed": 0.12}
        assert result.voice_metrics.punctuation_profile == {";": 0.3}

    def test_voice_metrics_none_when_no_voice_analysis(self) -> None:
        metadata: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None

    def test_voice_metrics_none_when_no_metrics_key(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {"dialect": "Southern", "voice_analysis": {"formality": 0.5}},
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None

    def test_voice_metrics_none_when_empty_dict(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {"formality": 0.5, "voice_metrics": {}},
            },
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None

    def test_voice_metrics_none_when_not_a_dict(self) -> None:
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {"formality": 0.5, "voice_metrics": "oops"},
            },
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None

    def test_voice_metrics_none_when_malformed(self) -> None:
        """RULE-11: malformed metric block → graceful None, no crash."""
        metadata: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {
                    "formality": 0.5,
                    "voice_metrics": {"avg_sentence_length": "not-a-number"},
                },
            },
        }
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None

    def test_speech_summary_unaffected_by_metrics(self) -> None:
        """CR-04: metrics presence does not change the descriptive summary."""
        base: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        with_metrics: dict[str, Any] = {
            "speech": {
                "dialect": "Southern",
                "voice_analysis": {
                    "formality": 0.9,
                    "voice_metrics": {"avg_sentence_length": 18.5},
                },
            },
        }
        r_base = build_character_voice_profile(entity_id="c1", name="Alice", metadata=base)
        r_metrics = build_character_voice_profile(
            entity_id="c1", name="Alice", metadata=with_metrics
        )
        assert r_base is not None and r_metrics is not None
        # The shared descriptive part renders identically.
        assert "dialect: Southern" in r_metrics.speech_summary
        # Metric numbers/keys never leak into the descriptive summary.
        assert "18.5" not in r_metrics.speech_summary
        assert "voice_metrics" not in r_metrics.speech_summary

    def test_existing_flows_unaffected_when_no_metrics(self) -> None:
        """A plain speech block (no voice_analysis) yields a profile identical
        to the pre-ADR-057 shape: voice_metrics is None, everything else equal."""
        metadata: dict[str, Any] = {"speech": {"dialect": "Southern"}}
        result = build_character_voice_profile(entity_id="c1", name="Alice", metadata=metadata)
        assert result is not None
        assert result.voice_metrics is None
        assert result.character_id == "c1"
        assert result.name == "Alice"
        assert result.speech_summary == "dialect: Southern"
        assert result.is_fresh is True
