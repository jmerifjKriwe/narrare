"""Tests for VoiceMetricsAnalyzer — deterministic voice metrics (ANAL-008/ADR-021).

Covers:
- Per-character aggregation (utterances grouped by speaker).
- Each metric family: sentence-length mean/std, type-token ratio, syllables,
  contraction rate, verbal-tic frequency, punctuation profile.
- Edge cases: no utterances, unattributed (speaker None) utterances, empty
  utterance text, single sentence (std == 0).
- Property-based (hypothesis): TTR bounds 0-1, std >= 0, determinism.

Deterministic + pure (ADR-021). No real LLM (RULE-01b).
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
from narrare_core.analysis.voice_types import AttributedUtterance
from narrare_core.kb.schemas.character import VoiceMetrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def analyzer() -> VoiceMetricsAnalyzer:
    return VoiceMetricsAnalyzer()


def _utt(text: str, speaker: str | None = "X", confidence: float = 0.9) -> AttributedUtterance:
    return AttributedUtterance(text=text, speaker=speaker, confidence=confidence)


# ---------------------------------------------------------------------------
# A. Aggregation per character
# ---------------------------------------------------------------------------


class TestAggregation:
    """Utterances are grouped by speaker; None speakers are skipped."""

    def test_empty_utterances_returns_empty(self, analyzer: VoiceMetricsAnalyzer) -> None:
        assert analyzer.analyze([]) == {}

    def test_unattributed_utterances_skipped(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("Hello there.", speaker=None)])
        assert result == {}

    def test_single_speaker_single_key(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("I am here.", speaker="Elena")])
        assert set(result) == {"Elena"}

    def test_two_speechers_two_keys(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("Hello.", "Anna"), _utt("Goodbye.", "Bob")])
        assert set(result) == {"Anna", "Bob"}

    def test_metrics_are_voice_metrics(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("I am here.", "Elena")])
        assert isinstance(result["Elena"], VoiceMetrics)


# ---------------------------------------------------------------------------
# B. Sentence-length mean + std
# ---------------------------------------------------------------------------


class TestSentenceLength:
    """avg_sentence_length / sentence_length_std over per-utterance sentences."""

    def test_single_sentence_std_zero(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "I am here." = 3 words, one sentence → std 0.0.
        result = analyzer.analyze([_utt("I am here.", "Elena")])["Elena"]
        assert result.avg_sentence_length == pytest.approx(3.0)
        assert result.sentence_length_std == pytest.approx(0.0)

    def test_multiple_sentences_mean_and_std(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # Two sentences: "I am here." (3 words), "You go now." (3 words) → mean 3, std 0.
        result = analyzer.analyze([_utt("I am here. You go now.", "Elena")])["Elena"]
        assert result.avg_sentence_length == pytest.approx(3.0)
        assert result.sentence_length_std == pytest.approx(0.0)

    def test_varying_sentence_lengths(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "Hi." (1), "I am really very tired today." (6) → mean 3.5, std 2.5.
        result = analyzer.analyze([_utt("Hi. I am really very tired today.", "Elena")])["Elena"]
        assert result.avg_sentence_length == pytest.approx(3.5)
        assert result.sentence_length_std == pytest.approx(2.5)

    def test_aggregates_across_utterances(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # Two utterances, one sentence each: 2 words + 4 words → mean 3, std 1.
        result = analyzer.analyze([_utt("Hi there.", "Elena"), _utt("I will be back.", "Elena")])[
            "Elena"
        ]
        assert result.avg_sentence_length == pytest.approx(3.0)
        assert result.sentence_length_std == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# C. Type-token ratio
# ---------------------------------------------------------------------------


class TestTypeTokenRatio:
    """TTR = unique lowercase tokens / total tokens, bounded 0-1."""

    def test_all_unique_ttr_one(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("I am here.", "Elena")])["Elena"]
        assert result.type_token_ratio == pytest.approx(1.0)

    def test_repeated_words_ttr_below_one(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "the the the cat" → 2 unique / 4 total = 0.5
        result = analyzer.analyze([_utt("the the the cat.", "Elena")])["Elena"]
        assert result.type_token_ratio == pytest.approx(0.5)

    def test_case_insensitive(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "The the" → 1 unique / 2 total = 0.5
        result = analyzer.analyze([_utt("The the.", "Elena")])["Elena"]
        assert result.type_token_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# D. Syllables
# ---------------------------------------------------------------------------


class TestSyllables:
    """avg_syllables_per_word is computed via core/nlp syllable counting."""

    def test_simple_words(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "I am here." all 1-syllable → 1.0
        result = analyzer.analyze([_utt("I am here.", "Elena")])["Elena"]
        assert result.avg_syllables_per_word == pytest.approx(1.0)

    def test_positive_for_nonempty(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("A wonderful beautiful day.", "Elena")])["Elena"]
        assert result.avg_syllables_per_word is not None
        assert result.avg_syllables_per_word > 0.0


# ---------------------------------------------------------------------------
# E. Contraction rate
# ---------------------------------------------------------------------------


class TestContractionRate:
    """contraction_rate = contractions / total words."""

    def test_no_contractions(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("I am here now.", "Elena")])["Elena"]
        assert result.contraction_rate == pytest.approx(0.0)

    def test_with_contraction(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "I don't know." → 1 contraction / 3 words (I, don't, know)
        result = analyzer.analyze([_utt("I don't know.", "Elena")])["Elena"]
        assert result.contraction_rate == pytest.approx(1.0 / 3.0)

    def test_pronoun_apostrophe_s_counts(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "She's here." → "she's" is a contraction (pronoun+'s) / 2 words
        result = analyzer.analyze([_utt("She's here.", "Elena")])["Elena"]
        assert result.contraction_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# F. Verbal-tic frequency (candidate-driven)
# ---------------------------------------------------------------------------


class TestVerbalTicFrequency:
    """verbal_tic_frequency counts supplied candidate phrases per speaker."""

    def test_none_when_no_candidates(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("I say hello.", "Elena")])["Elena"]
        assert result.verbal_tic_frequency is None

    def test_counts_supplied_tics(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "you know I think you know" -> "you know" appears 2x; 6 words total
        result = analyzer.analyze(
            [_utt("you know I think you know.", "Elena")],
            verbal_tics={"Elena": ["you know"]},
        )["Elena"]
        tics = result.verbal_tic_frequency
        assert tics is not None
        assert "you know" in tics
        assert tics["you know"] == pytest.approx(2.0 / 6.0)

    def test_no_occurrence_zero_rate(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze(
            [_utt("hello world.", "Elena")],
            verbal_tics={"Elena": ["you know"]},
        )["Elena"]
        assert result.verbal_tic_frequency == {"you know": 0.0}

    def test_case_insensitive(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze(
            [_utt("You Know what I mean.", "Elena")],
            verbal_tics={"Elena": ["you know"]},
        )["Elena"]
        assert result.verbal_tic_frequency is not None
        assert result.verbal_tic_frequency["you know"] > 0.0


# ---------------------------------------------------------------------------
# G. Punctuation profile
# ---------------------------------------------------------------------------


class TestPunctuationProfile:
    """punctuation_profile = habit → occurrences / total words."""

    def test_exclamation_and_question(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "What? No way! Why?" → words: what, no, way, why = 4; ! x1, ? x2
        result = analyzer.analyze([_utt("What? No way! Why?", "Elena")])["Elena"]
        profile = result.punctuation_profile
        assert profile is not None
        assert profile["exclamation"] == pytest.approx(1.0 / 4.0)
        assert profile["question"] == pytest.approx(2.0 / 4.0)

    def test_em_dash_and_ellipsis(self, analyzer: VoiceMetricsAnalyzer) -> None:
        # "Well… I mean— really." words: well, i, mean, really = 4; ellipsis x1, em_dash x1
        # Use literal ellipsis "..." and em dash "—".
        result = analyzer.analyze([_utt("Well... I mean— really.", "Elena")])["Elena"]
        profile = result.punctuation_profile
        assert profile is not None
        assert profile["ellipsis"] == pytest.approx(1.0 / 4.0)
        assert profile["em_dash"] == pytest.approx(1.0 / 4.0)

    def test_no_punctuation_all_zero(self, analyzer: VoiceMetricsAnalyzer) -> None:
        result = analyzer.analyze([_utt("just plain words here.", "Elena")])["Elena"]
        profile = result.punctuation_profile
        assert profile is not None
        assert all(v == 0.0 for v in profile.values())


# ---------------------------------------------------------------------------
# H. Property-based (hypothesis) — invariants + determinism (ADR-021)
# ---------------------------------------------------------------------------


_WORD_STRATEGY = st.sampled_from(["cat", "dog", "run", "the", "a", "I", "am", "here"])


class TestProperties:
    """Determinism + metric bounds hold for arbitrary word sequences."""

    @given(words=st.lists(_WORD_STRATEGY, min_size=1, max_size=25))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ttr_in_bounds(self, analyzer: VoiceMetricsAnalyzer, words: list[str]) -> None:
        text = " ".join(words) + "."
        metrics = analyzer.analyze([_utt(text, "Elena")])["Elena"]
        assert metrics.type_token_ratio is not None
        assert 0.0 <= metrics.type_token_ratio <= 1.0

    @given(words=st.lists(_WORD_STRATEGY, min_size=1, max_size=25))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_std_non_negative(self, analyzer: VoiceMetricsAnalyzer, words: list[str]) -> None:
        text = " ".join(words) + "."
        metrics = analyzer.analyze([_utt(text, "Elena")])["Elena"]
        assert metrics.sentence_length_std is not None
        assert metrics.sentence_length_std >= 0.0

    @given(words=st.lists(_WORD_STRATEGY, min_size=1, max_size=25))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deterministic(self, analyzer: VoiceMetricsAnalyzer, words: list[str]) -> None:
        text = " ".join(words) + "."
        utterances = [_utt(text, "Elena")]
        first = analyzer.analyze(utterances)
        second = analyzer.analyze(utterances)
        assert first == second

    @given(words=st.lists(_WORD_STRATEGY, min_size=2, max_size=25))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_stable_across_minor_whitespace(
        self, analyzer: VoiceMetricsAnalyzer, words: list[str]
    ) -> None:
        # ADR-021/ANAL-009 drift: whitespace-only changes must not move metrics.
        tight = " ".join(words) + "."
        loose = "  ".join(words) + "."
        a = analyzer.analyze([_utt(tight, "Elena")])["Elena"]
        b = analyzer.analyze([_utt(loose, "Elena")])["Elena"]
        assert a == b
