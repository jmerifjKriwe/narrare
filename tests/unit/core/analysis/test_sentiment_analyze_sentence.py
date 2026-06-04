"""Tests for LexiconSentimentAnalyzer.analyze_sentence() — per-sentence analysis.

Covers:
1. Positive/negative/neutral sentence sentiment
2. Provider unavailability and tokenization failures
3. Return type and field correctness
4. Dialogue detection
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.types import (
    SentenceSentiment,
    VADScores,
)
from narrare_core.nlp.contracts_types import TokenResult
from narrare_core.shared.errors import NLPProviderError

from .helpers import FailingNLPProvider, FakeNLPProvider, _make_tokens


class TestAnalyzeSentence:
    """LexiconSentimentAnalyzer.analyze_sentence() tests."""

    @pytest.mark.asyncio
    async def test_analyze_sentence_positive_returns_positive_vad(
        self,
    ) -> None:
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
    async def test_analyze_sentence_negative_returns_negative_vad(
        self,
    ) -> None:
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
    async def test_analyze_sentence_neutral_unknown_words_returns_zero_vad(
        self,
    ) -> None:
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
    async def test_analyze_sentence_provider_unavailable_raises_error(
        self,
    ) -> None:
        """NLPProviderError when provider is unavailable."""
        nlp = FakeNLPProvider(available=False)
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="not available"):
            await analyzer.analyze_sentence("Hello")

    @pytest.mark.asyncio
    async def test_analyze_sentence_tokenization_failure_raises_error(
        self,
    ) -> None:
        """NLPProviderError wraps tokenization failures."""
        nlp = FailingNLPProvider()
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="Sentence tokenization failed"):
            await analyzer.analyze_sentence("Hello")

    @pytest.mark.asyncio
    async def test_analyze_sentence_returns_sentence_sentiment(
        self,
    ) -> None:
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
