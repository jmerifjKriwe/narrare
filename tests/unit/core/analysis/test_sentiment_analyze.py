"""Tests for LexiconSentimentAnalyzer.analyze() — VAD scoring and arc detection (ADR-021).

Covers:
1. analyze() — happy path, arc detection, empty text, single/multi sentences
2. Protocol compliance — satisfies SentimentAnalyzer
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.contracts import SentimentAnalyzer
from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.types import (
    EmotionScores,
    SentimentOverview,
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
# A. analyze() — happy path
# ---------------------------------------------------------------------------


class TestAnalyze:
    """LexiconSentimentAnalyzer.analyze() tests."""

    @pytest.mark.asyncio
    async def test_analyze_happy_path_returns_overview(
        self, analyzer: LexiconSentimentAnalyzer
    ) -> None:
        """Happy path: known text returns a SentimentOverview."""
        nlp = FakeNLPProvider(
            sentences=["She felt a surge of joy."],
            tokenize_result=TokenResult(
                tokens=_make_tokens(["She", "felt", "a", "surge", "of", "joy"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze("She felt a surge of joy.")

        assert isinstance(result, SentimentOverview)
        assert result.sentence_count == 1
        assert len(result.sentences) == 1
        assert result.sentences[0].sentence == "She felt a surge of joy."

    @pytest.mark.asyncio
    async def test_analyze_empty_text_returns_empty_overview(
        self, analyzer: LexiconSentimentAnalyzer
    ) -> None:
        """Empty text returns zeroed overview."""
        result = await analyzer.analyze("")

        assert result.sentence_count == 0
        assert result.sentences == []
        assert result.dominant_emotions == []
        assert result.average_vad == VADScores(valence=0.0, arousal=0.0, dominance=0.0)
        assert result.overall_emotions == EmotionScores()

    @pytest.mark.asyncio
    async def test_analyze_whitespace_only_returns_empty_overview(
        self, analyzer: LexiconSentimentAnalyzer
    ) -> None:
        """Whitespace-only text is treated as empty."""
        result = await analyzer.analyze("   \n\t  ")

        assert result.sentence_count == 0
        assert result.sentences == []

    @pytest.mark.asyncio
    async def test_analyze_provider_unavailable_raises_nlp_provider_error(self) -> None:
        """NLPProviderError when provider is unavailable for language."""
        nlp = FakeNLPProvider(available=False)
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="not available"):
            await analyzer.analyze("Hello world.")

    @pytest.mark.asyncio
    async def test_analyze_tokenization_failure_raises_nlp_provider_error(self) -> None:
        """NLPProviderError wraps tokenization failures."""
        nlp = FailingNLPProvider()
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)

        with pytest.raises(NLPProviderError, match="Tokenization failed"):
            await analyzer.analyze("Some text.")

    @pytest.mark.asyncio
    async def test_analyze_multiple_sentences(self) -> None:
        """Multi-sentence text produces per-sentence results."""
        sentences = ["She was happy.", "Then she felt deep sadness."]
        nlp = FakeNLPProvider(
            sentences=sentences,
            tokenize_result=TokenResult(
                tokens=_make_tokens(["She", "was", "happy"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze("She was happy. Then she felt deep sadness.")

        assert result.sentence_count == 2
        assert len(result.sentences) == 2

    @pytest.mark.asyncio
    async def test_analyze_no_sentences_after_split_returns_empty(self) -> None:
        """When sentence splitting returns empty list, returns zeroed overview."""
        nlp = FakeNLPProvider(sentences=[])
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze("...")

        assert result.sentence_count == 0
        assert result.sentences == []

    @pytest.mark.asyncio
    async def test_analyze_arc_detection_on_with_enough_sentences(self) -> None:
        """Arc detection is triggered when detect_arc=True and >= 5 sentences."""
        sentences = [
            "She felt pure joy.",
            "But then came anger.",
            "A deep sadness overwhelmed her.",
            "Slowly trust returned.",
            "Finally hope blossomed.",
        ]
        tokens = _make_tokens(["happy", "sad", "joy", "fear", "anger"])
        nlp = FakeNLPProvider(
            sentences=sentences,
            tokenize_result=TokenResult(tokens=tokens, language="en"),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze(
            " ".join(sentences),
            detect_arc=True,
        )

        assert isinstance(result, SentimentOverview)
        assert result.sentence_count == 5

    @pytest.mark.asyncio
    async def test_analyze_arc_detection_off_no_narrative_arc(self) -> None:
        """No arc detection when detect_arc=False."""
        sentences = [f"Sentence {i}." for i in range(6)]
        nlp = FakeNLPProvider(
            sentences=sentences,
            tokenize_result=TokenResult(
                tokens=_make_tokens(["word"] * 6),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze(
            " ".join(sentences),
            detect_arc=False,
        )

        assert result.narrative_arc is None


# ---------------------------------------------------------------------------
# I. Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """LexiconSentimentAnalyzer satisfies SentimentAnalyzer protocol."""

    def test_satisfies_protocol(self) -> None:
        """Instance is recognized as SentimentAnalyzer via runtime check."""
        nlp = FakeNLPProvider()
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        assert isinstance(analyzer, SentimentAnalyzer)

    @pytest.mark.asyncio
    async def test_analyze_signature_matches_protocol(self) -> None:
        """analyze() accepts keyword-only language and detect_arc."""
        nlp = FakeNLPProvider(
            sentences=["Hello."],
            tokenize_result=TokenResult(
                tokens=_make_tokens(["Hello"]),
                language="en",
            ),
        )
        analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
        result = await analyzer.analyze("Hello.", language="en", detect_arc=False)

        assert isinstance(result, SentimentOverview)
