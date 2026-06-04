"""Tests for LexiconSentimentAnalyzer — sentence-level and aggregate scoring.

Covers:
1. analyze_sentence() — positive/negative/neutral, provider unavailability
2. _compute_sentence_vad() — with tokens, empty tokens, unknown words
3. _compute_sentence_emotions() — word-level emotion lookup
4. _get_dominant_emotion() — best emotion selection
5. _get_top_emotions() — top N selection
6. _compute_average_vad() — mean across sentences
7. _compute_overall_emotions() — mean emotions across sentences
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.types import (
    EmotionScores,
    SentenceSentiment,
    VADScores,
)
from narrare_core.nlp.contracts_types import TokenResult
from narrare_core.shared.errors import NLPProviderError
from tests.unit.core.analysis.helpers import (
    FailingNLPProvider,
    FakeNLPProvider,
    _make_tokens,
)

# ---------------------------------------------------------------------------
# B. analyze_sentence()
# ---------------------------------------------------------------------------


class TestAnalyzeSentence:
    """LexiconSentimentAnalyzer.analyze_sentence() tests."""

    @pytest.mark.asyncio
    async def test_analyze_sentence_positive_returns_positive_vad(self) -> None:
        """Sentence with 'joy' has positive valence."""
        nlp = FakeNLPProvider(
            tokenize_result=TokenResult(
                tokens=_make_tokens(["She", "felt", "joy"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze_sentence("She felt joy")

        assert result.vad.valence > 0.0
        assert result.dominant_emotion == "joy"

    @pytest.mark.asyncio
    async def test_analyze_sentence_negative_returns_negative_vad(self) -> None:
        """Sentence with 'fear' has negative valence."""
        nlp = FakeNLPProvider(
            tokenize_result=TokenResult(
                tokens=_make_tokens(["She", "felt", "fear"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze_sentence("She felt fear")

        assert result.vad.valence < 0.0

    @pytest.mark.asyncio
    async def test_analyze_sentence_neutral_unknown_words_returns_zero_vad(self) -> None:
        """Sentence with no emotion words gets zero VAD."""
        nlp = FakeNLPProvider(
            tokenize_result=TokenResult(
                tokens=_make_tokens(["xyz", "abc"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze_sentence("xyz abc")

        assert result.vad == VADScores(valence=0.0, arousal=0.0, dominance=0.0)

    @pytest.mark.asyncio
    async def test_analyze_sentence_provider_unavailable_raises_error(self) -> None:
        """NLPProviderError when provider is unavailable."""
        nlp = FakeNLPProvider(available=False)
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="not available"):
            await analyzer.analyze_sentence("Hello")

    @pytest.mark.asyncio
    async def test_analyze_sentence_tokenization_failure_raises_error(self) -> None:
        """NLPProviderError wraps tokenization failures."""
        nlp = FailingNLPProvider()
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="Sentence tokenization failed"):
            await analyzer.analyze_sentence("Hello")

    @pytest.mark.asyncio
    async def test_analyze_sentence_returns_sentence_sentiment(self) -> None:
        """analyze_sentence returns SentenceSentiment."""
        nlp = FakeNLPProvider(
            tokenize_result=TokenResult(
                tokens=_make_tokens(["Hello", "world"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze_sentence("Hello world")

        assert isinstance(result, SentenceSentiment)
        assert result.sentence == "Hello world"
        assert result.sentence_index == 0
        assert result.word_count == 2

    @pytest.mark.asyncio
    async def test_analyze_sentence_dialogue_detection(self) -> None:
        """Dialogue sentences are detected via is_dialogue_line."""
        nlp = FakeNLPProvider(
            tokenize_result=TokenResult(
                tokens=_make_tokens(["Hello"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze_sentence('"Hello"')

        assert result.is_dialogue is True


# ---------------------------------------------------------------------------
# C. _compute_sentence_vad() — static method
# ---------------------------------------------------------------------------


class TestComputeSentenceVAD:
    """LexiconSentimentAnalyzer._compute_sentence_vad() tests."""

    def test_with_emotion_tokens_returns_vad(self) -> None:
        """Tokens with known emotion words produce VAD scores."""
        tokens = _make_tokens(["joy", "happy"])
        result = LexiconSentimentAnalyzer._compute_sentence_vad(tokens, "en")

        assert result is not None
        assert result.valence > 0.0

    def test_with_no_emotion_tokens_returns_none(self) -> None:
        """Tokens with no emotion words return None."""
        tokens = _make_tokens(["xyz", "abc", "def"])
        result = LexiconSentimentAnalyzer._compute_sentence_vad(tokens, "en")

        assert result is None

    def test_with_empty_tokens_returns_none(self) -> None:
        """Empty token list returns None."""
        result = LexiconSentimentAnalyzer._compute_sentence_vad([], "en")

        assert result is None

    def test_mixed_tokens_averages_known(self) -> None:
        """Mix of known and unknown tokens averages only known ones."""
        tokens = _make_tokens(["joy", "xyz", "happy"])
        result = LexiconSentimentAnalyzer._compute_sentence_vad(tokens, "en")

        assert result is not None
        assert result.valence > 0.0

    def test_negative_emotion_tokens_return_negative_valence(self) -> None:
        """Fear and anger tokens produce negative valence."""
        tokens = _make_tokens(["fear", "anger"])
        result = LexiconSentimentAnalyzer._compute_sentence_vad(tokens, "en")

        assert result is not None
        assert result.valence < 0.0

    def test_vad_scores_are_rounded_to_4_decimals(self) -> None:
        """VAD scores are rounded to 4 decimal places."""
        tokens = _make_tokens(["joy"])
        result = LexiconSentimentAnalyzer._compute_sentence_vad(tokens, "en")

        assert result is not None
        val_str = str(result.valence)
        if "." in val_str:
            decimals = len(val_str.split(".")[1])
            assert decimals <= 4


# ---------------------------------------------------------------------------
# D. _compute_sentence_emotions() — static method
# ---------------------------------------------------------------------------


class TestComputeSentenceEmotions:
    """LexiconSentimentAnalyzer._compute_sentence_emotions() tests."""

    def test_with_joy_tokens_produces_joy_score(self) -> None:
        """Tokens with 'joy' produce non-zero joy score."""
        tokens = _make_tokens(["joy", "happy"])
        result = LexiconSentimentAnalyzer._compute_sentence_emotions(tokens, "en")

        assert result.joy > 0.0

    def test_with_no_emotion_tokens_returns_zero_scores(self) -> None:
        """Tokens with no emotion words return zero scores."""
        tokens = _make_tokens(["xyz", "abc"])
        result = LexiconSentimentAnalyzer._compute_sentence_emotions(tokens, "en")

        assert result == EmotionScores()

    def test_with_empty_tokens_returns_zero_scores(self) -> None:
        """Empty token list returns zero scores."""
        result = LexiconSentimentAnalyzer._compute_sentence_emotions([], "en")

        assert result == EmotionScores()

    def test_emotion_proportions_sum_correctly(self) -> None:
        """Emotion proportions reflect word-level counts."""
        tokens = _make_tokens(["joy", "fear"])
        result = LexiconSentimentAnalyzer._compute_sentence_emotions(tokens, "en")

        assert result.joy > 0.0
        assert result.fear > 0.0


# ---------------------------------------------------------------------------
# E. _get_dominant_emotion() — static method
# ---------------------------------------------------------------------------


class TestGetDominantEmotion:
    """LexiconSentimentAnalyzer._get_dominant_emotion() tests."""

    def test_returns_highest_emotion(self) -> None:
        """Returns the emotion with the highest score."""
        emotions = EmotionScores(joy=0.8, sadness=0.2)
        result = LexiconSentimentAnalyzer._get_dominant_emotion(emotions)

        assert result == "joy"

    def test_excludes_positive_negative(self) -> None:
        """'positive' and 'negative' meta-labels are excluded."""
        emotions = EmotionScores(positive=0.9, joy=0.1)
        result = LexiconSentimentAnalyzer._get_dominant_emotion(emotions)

        assert result == "joy"

    def test_all_zero_returns_none(self) -> None:
        """All-zero scores return None."""
        emotions = EmotionScores()
        result = LexiconSentimentAnalyzer._get_dominant_emotion(emotions)

        assert result is None


# ---------------------------------------------------------------------------
# F. _get_top_emotions() — static method
# ---------------------------------------------------------------------------


class TestGetTopEmotions:
    """LexiconSentimentAnalyzer._get_top_emotions() tests."""

    def test_returns_top_three_by_default(self) -> None:
        """Returns top 3 emotions by default."""
        emotions = EmotionScores(joy=0.8, fear=0.5, sadness=0.3, anger=0.1)
        result = LexiconSentimentAnalyzer._get_top_emotions(emotions)

        assert result == ["joy", "fear", "sadness"]

    def test_excludes_zero_scores(self) -> None:
        """Emotions with score 0 are excluded."""
        emotions = EmotionScores(joy=0.8)
        result = LexiconSentimentAnalyzer._get_top_emotions(emotions)

        assert result == ["joy"]

    def test_custom_top_n(self) -> None:
        """Custom top_n parameter works."""
        emotions = EmotionScores(joy=0.8, fear=0.5, sadness=0.3)
        result = LexiconSentimentAnalyzer._get_top_emotions(emotions, top_n=2)

        assert len(result) == 2
        assert result[0] == "joy"

    def test_all_zero_returns_empty(self) -> None:
        """All-zero scores return empty list."""
        emotions = EmotionScores()
        result = LexiconSentimentAnalyzer._get_top_emotions(emotions)

        assert result == []


# ---------------------------------------------------------------------------
# G. _compute_average_vad() — static method
# ---------------------------------------------------------------------------


class TestComputeAverageVAD:
    """LexiconSentimentAnalyzer._compute_average_vad() tests."""

    def test_averages_across_sentences(self) -> None:
        """Mean VAD across multiple sentence results."""
        sentences = [
            SentenceSentiment(
                sentence="A",
                sentence_index=0,
                vad=VADScores(valence=0.5, arousal=0.3, dominance=0.2),
                emotions=EmotionScores(),
                word_count=1,
            ),
            SentenceSentiment(
                sentence="B",
                sentence_index=1,
                vad=VADScores(valence=0.7, arousal=0.5, dominance=0.4),
                emotions=EmotionScores(),
                word_count=1,
            ),
        ]
        result = LexiconSentimentAnalyzer._compute_average_vad(sentences)

        assert result.valence == 0.6
        assert result.arousal == 0.4
        assert result.dominance == 0.3

    def test_empty_list_returns_zero_vad(self) -> None:
        """Empty sentence list returns zeroed VAD."""
        result = LexiconSentimentAnalyzer._compute_average_vad([])

        assert result == VADScores(valence=0.0, arousal=0.0, dominance=0.0)

    def test_single_sentence(self) -> None:
        """Single sentence returns its VAD unchanged."""
        vad = VADScores(valence=0.8, arousal=0.6, dominance=0.4)
        sentences = [
            SentenceSentiment(
                sentence="Test",
                sentence_index=0,
                vad=vad,
                emotions=EmotionScores(),
                word_count=1,
            ),
        ]
        result = LexiconSentimentAnalyzer._compute_average_vad(sentences)

        assert result.valence == 0.8
        assert result.arousal == 0.6
        assert result.dominance == 0.4


# ---------------------------------------------------------------------------
# H. _compute_overall_emotions() — static method
# ---------------------------------------------------------------------------


class TestComputeOverallEmotions:
    """LexiconSentimentAnalyzer._compute_overall_emotions() tests."""

    def test_averages_emotions_across_sentences(self) -> None:
        """Mean emotions across multiple sentence results."""
        sentences = [
            SentenceSentiment(
                sentence="A",
                sentence_index=0,
                vad=VADScores(valence=0.0, arousal=0.0, dominance=0.0),
                emotions=EmotionScores(joy=0.5, sadness=0.0),
                word_count=1,
            ),
            SentenceSentiment(
                sentence="B",
                sentence_index=1,
                vad=VADScores(valence=0.0, arousal=0.0, dominance=0.0),
                emotions=EmotionScores(joy=0.3, sadness=0.7),
                word_count=1,
            ),
        ]
        result = LexiconSentimentAnalyzer._compute_overall_emotions(sentences)

        assert result.joy == 0.4  # (0.5 + 0.3) / 2
        assert result.sadness == 0.35  # (0.0 + 0.7) / 2

    def test_empty_list_returns_zero_emotions(self) -> None:
        """Empty sentence list returns zeroed emotions."""
        result = LexiconSentimentAnalyzer._compute_overall_emotions([])

        assert result == EmotionScores()
