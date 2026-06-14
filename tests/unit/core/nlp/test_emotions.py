"""Tests for the emotion lexicon — get_emotions, get_vad, VAD mapping.

Covers the public API of narrare_core.nlp.languages.emotions including
edge cases: unknown language, emotions without VAD mapping, and the
NotImplementedError placeholder for full NRC EmoLex loading.

See ADR-021 (Deterministic Analysis Strategy).
"""

from __future__ import annotations

import pytest

from narrare_core.nlp.languages.emotions import (
    ATTRIBUTION,
    VADScores,
    get_emotions,
    get_vad,
    load_full_nrc_emolex,
)

# ---------------------------------------------------------------------------
# A. get_emotions
# ---------------------------------------------------------------------------


class TestGetEmotions:
    """get_emotions() — word-to-emotion-label lookup."""

    def test_known_english_word(self) -> None:
        """A word in the English lexicon returns its emotion set."""
        result = get_emotions("happy", "en")
        assert "joy" in result
        assert "positive" in result

    def test_unknown_word_returns_empty_set(self) -> None:
        """A word not in the lexicon returns an empty set."""
        result = get_emotions("xyzqwerty", "en")
        assert result == set()

    def test_case_insensitive(self) -> None:
        """Lookup is case-insensitive."""
        assert get_emotions("HAPPY", "en") == get_emotions("happy", "en")

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped before lookup."""
        assert get_emotions("  happy  ", "en") == get_emotions("happy", "en")

    def test_german_word(self) -> None:
        """German lexicon lookup works."""
        result = get_emotions("glücklich", "de")
        assert "joy" in result
        assert "positive" in result

    def test_french_word(self) -> None:
        """French lexicon lookup works."""
        result = get_emotions("joie", "fr")
        assert "joy" in result

    def test_unknown_language_returns_empty_set(self) -> None:
        """Unknown language code returns empty set (line 118)."""
        result = get_emotions("happy", "xx")
        assert result == set()

    def test_returns_set_type(self) -> None:
        """Return type is always a set."""
        assert isinstance(get_emotions("happy", "en"), set)
        assert isinstance(get_emotions("unknown", "en"), set)


# ---------------------------------------------------------------------------
# B. get_vad
# ---------------------------------------------------------------------------


class TestGetVad:
    """get_vad() — aggregate Valence-Arousal-Dominance scores."""

    def test_known_word_returns_vad_scores(self) -> None:
        """A word with emotions returns aggregate VADScores."""
        result = get_vad("happy", "en")
        assert result is not None
        assert isinstance(result, VADScores)
        # "happy" → {joy, positive} → mean of joy(0.81,0.35,0.31)
        # and positive(0.65,0.10,0.30)
        assert result.valence == pytest.approx((0.81 + 0.65) / 2, abs=0.01)
        assert result.arousal == pytest.approx((0.35 + 0.10) / 2, abs=0.01)

    def test_unknown_word_returns_none(self) -> None:
        """Word not in lexicon returns None."""
        result = get_vad("xyzqwerty", "en")
        assert result is None

    def test_unknown_language_returns_none(self) -> None:
        """Unknown language has no lexicon → no emotions → None."""
        result = get_vad("happy", "xx")
        assert result is None

    def test_vad_scores_are_rounded(self) -> None:
        """VAD values are rounded to 3 decimal places."""
        result = get_vad("happy", "en")
        assert result is not None
        # round(..., 3) produces at most 3 decimal places
        for value in (result.valence, result.arousal, result.dominance):
            assert round(value, 3) == value

    def test_vad_none_when_emotion_not_in_vad_map(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Line 153: all emotions lack VAD mapping → return None."""
        fake_lexicon: dict[str, set[str]] = {"ghostword": {"nonexistent_emotion"}}
        monkeypatch.setattr(
            "narrare_core.nlp.languages.emotions._LEXICONS",
            {"en": fake_lexicon},
        )
        result = get_vad("ghostword", "en")
        assert result is None

    def test_vad_partial_match_skips_unknown_emotion(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 146->144: emotion without VAD is skipped, valid ones counted."""
        fake_lexicon: dict[str, set[str]] = {
            "mixed": {"joy", "nonexistent_emotion"},
        }
        monkeypatch.setattr(
            "narrare_core.nlp.languages.emotions._LEXICONS",
            {"en": fake_lexicon},
        )
        result = get_vad("mixed", "en")
        assert result is not None
        # Only "joy" counted: (0.81, 0.35, 0.31)
        assert result.valence == pytest.approx(0.81, abs=0.001)


# ---------------------------------------------------------------------------
# C. VADScores dataclass
# ---------------------------------------------------------------------------


class TestVADScores:
    """VADScores — frozen dataclass for VAD values."""

    def test_is_frozen(self) -> None:
        """VADScores is immutable."""
        scores = VADScores(valence=0.5, arousal=0.3, dominance=0.2)
        with pytest.raises(AttributeError):
            scores.valence = 0.9  # type: ignore[misc]

    def test_field_values(self) -> None:
        """Fields are accessible."""
        scores = VADScores(valence=0.8, arousal=-0.2, dominance=0.1)
        assert scores.valence == 0.8
        assert scores.arousal == -0.2
        assert scores.dominance == 0.1


# ---------------------------------------------------------------------------
# D. load_full_nrc_emolex
# ---------------------------------------------------------------------------


class TestLoadFullNrcEmolex:
    """load_full_nrc_emolex() — placeholder raises NotImplementedError."""

    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            load_full_nrc_emolex("/fake/path.txt")

    def test_error_mentions_attribution(self) -> None:
        """Error message includes attribution text."""
        with pytest.raises(NotImplementedError) as exc_info:
            load_full_nrc_emolex("/fake/path.txt")
        assert "NRC" in str(exc_info.value)


# ---------------------------------------------------------------------------
# E. ATTRIBUTION constant
# ---------------------------------------------------------------------------


class TestAttribution:
    """ATTRIBUTION — NRC EmoLex license attribution string."""

    def test_is_non_empty_string(self) -> None:
        assert isinstance(ATTRIBUTION, str)
        assert len(ATTRIBUTION) > 0

    def test_mentions_nrc(self) -> None:
        assert "NRC" in ATTRIBUTION
