"""Sentiment analysis — lexicon-based VAD scoring and arc detection.

Implements the :class:`SentimentAnalyzer` Protocol using the NLPProvider
for tokenization and the emotion lexicon for word-level scoring.

All results are **deterministic** — same text + same language always
produces identical output (ADR-021).

Usage::

    from narrare_core.nlp.provider_spacy import SpacyNLPProvider
    from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer

    nlp = SpacyNLPProvider()
    analyzer = LexiconSentimentAnalyzer(nlp_provider=nlp)
    result = await analyzer.analyze("She felt a surge of joy.", language="en")
    # result.average_vad.valence ≈ 0.73
    # result.overall_emotions.joy ≈ 0.25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.analysis.sentiment_arcs import detect_narrative_arc
from narrare_core.analysis.types import (
    EmotionScores,
    NarrativeArc,
    SentenceSentiment,
    SentimentOverview,
    VADScores,
)
from narrare_core.nlp.dialogue import is_dialogue_line
from narrare_core.nlp.languages.emotions import (
    get_emotions as _get_lexicon_emotions,
)
from narrare_core.nlp.languages.emotions import (
    get_vad as _get_lexicon_vad,
)
from narrare_core.shared.errors import NLPProviderError

if TYPE_CHECKING:
    from narrare_core.nlp.contracts import NLPProvider
    from narrare_core.nlp.contracts_types import LanguageCode, Token

logger = structlog.get_logger(__name__)

_EMOTION_LABELS: list[str] = [
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "sadness",
    "surprise",
    "trust",
    "positive",
    "negative",
]

_MIN_ARCS_SENTENCES: int = 5


class LexiconSentimentAnalyzer:
    """Sentiment analyzer using lexicon-based VAD + emotion scoring.

    Implements :class:`SentimentAnalyzer` Protocol.

    Args:
        nlp_provider: An :class:`NLPProvider` for tokenization and
            sentence splitting. Callers should check
            ``nlp_provider.is_available()`` first.
    """

    def __init__(self, nlp_provider: NLPProvider) -> None:
        self._nlp = nlp_provider

    async def analyze(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
        detect_arc: bool = True,
    ) -> SentimentOverview:
        """Analyze sentiment of the entire text.

        See :meth:`SentimentAnalyzer.analyze` for full documentation.
        """
        if not text or not text.strip():
            return SentimentOverview(
                sentence_count=0,
                average_vad=VADScores(valence=0.0, arousal=0.0, dominance=0.0),
                overall_emotions=EmotionScores(),
                sentences=[],
                dominant_emotions=[],
            )

        if not self._nlp.is_available(language=language):
            raise NLPProviderError(f"NLP provider is not available for language '{language}'")

        try:
            _tokens, sentences = await self._nlp.tokenize_for_sentiment(text, language=language)
        except Exception as exc:
            logger.error("Tokenization failed", language=language, error=str(exc))
            raise NLPProviderError(f"Tokenization failed: {exc}") from exc

        if not sentences:
            return SentimentOverview(
                sentence_count=0,
                average_vad=VADScores(valence=0.0, arousal=0.0, dominance=0.0),
                overall_emotions=EmotionScores(),
                sentences=[],
                dominant_emotions=[],
            )

        # Analyze each sentence
        sentence_results: list[SentenceSentiment] = []
        for idx, sentence in enumerate(sentences):
            sent = await self._analyze_single(sentence, idx, language)
            sentence_results.append(sent)

        # Aggregate
        avg_vad = self._compute_average_vad(sentence_results)
        overall_emotions = self._compute_overall_emotions(sentence_results)
        dominant_emotions = self._get_top_emotions(overall_emotions)

        # Arc detection
        narrative_arc: NarrativeArc | None = None
        if detect_arc and len(sentence_results) >= _MIN_ARCS_SENTENCES:
            raw = detect_narrative_arc(sentence_results)
            if raw is not None:
                narrative_arc = NarrativeArc(**raw)

        return SentimentOverview(
            sentence_count=len(sentence_results),
            average_vad=avg_vad,
            overall_emotions=overall_emotions,
            narrative_arc=narrative_arc,
            sentences=sentence_results,
            dominant_emotions=dominant_emotions,
        )

    async def analyze_sentence(
        self,
        sentence: str,
        *,
        language: LanguageCode = "en",
    ) -> SentenceSentiment:
        """Analyze sentiment of a single sentence.

        See :meth:`SentimentAnalyzer.analyze_sentence` for full documentation.
        """
        if not self._nlp.is_available(language=language):
            raise NLPProviderError(f"NLP provider is not available for language '{language}'")

        return await self._analyze_single(sentence, 0, language)

    # Internal helpers

    async def _analyze_single(
        self,
        sentence: str,
        idx: int,
        language: LanguageCode,
    ) -> SentenceSentiment:
        """Tokenize and score a single sentence."""
        try:
            result = await self._nlp.tokenize(sentence, language=language)
        except Exception as exc:
            logger.error("Sentence tokenization failed", language=language, error=str(exc))
            raise NLPProviderError(f"Sentence tokenization failed: {exc}") from exc

        tokens = result.tokens
        vad = self._compute_sentence_vad(tokens, language)
        emotions = self._compute_sentence_emotions(tokens, language)
        dominant = self._get_dominant_emotion(emotions)

        return SentenceSentiment(
            sentence=sentence,
            sentence_index=idx,
            vad=vad if vad is not None else VADScores(valence=0.0, arousal=0.0, dominance=0.0),
            emotions=emotions,
            word_count=len(tokens),
            is_dialogue=is_dialogue_line(sentence),
            dominant_emotion=dominant,
        )

    @staticmethod
    def _compute_sentence_vad(
        tokens: list[Token],
        language: LanguageCode,
    ) -> VADScores | None:
        """Average VAD from word-level lexicon lookups."""
        total_v = total_a = total_d = 0.0
        count = 0
        for token in tokens:
            raw_vad = _get_lexicon_vad(token.text, language)
            if raw_vad is not None:
                total_v += raw_vad.valence
                total_a += raw_vad.arousal
                total_d += raw_vad.dominance
                count += 1
        if count == 0:
            return None
        return VADScores(
            valence=round(total_v / count, 4),
            arousal=round(total_a / count, 4),
            dominance=round(total_d / count, 4),
        )

    @staticmethod
    def _compute_sentence_emotions(
        tokens: list[Token],
        language: LanguageCode,
    ) -> EmotionScores:
        """Emotion proportions from word-level lexicon lookups."""
        emotion_counts: dict[str, int] = dict.fromkeys(_EMOTION_LABELS, 0)
        word_count = 0
        for token in tokens:
            emotions = _get_lexicon_emotions(token.text, language)
            if emotions:
                for e in emotions:
                    if e in emotion_counts:
                        emotion_counts[e] += 1
                word_count += 1
        if word_count == 0:
            return EmotionScores()
        return EmotionScores(
            **{e: round(count / word_count, 4) for e, count in emotion_counts.items()}
        )

    @staticmethod
    def _build_scores(emotions: EmotionScores) -> dict[str, float]:
        """Unpack emotion scores into a flat dict keyed by label."""
        return {k: getattr(emotions, k) for k in _EMOTION_LABELS}

    @staticmethod
    def _get_dominant_emotion(emotions: EmotionScores) -> str | None:
        """Emotion with highest score (excluding positive/negative meta)."""
        scores = LexiconSentimentAnalyzer._build_scores(emotions)
        best_label = ""
        best_score = 0.0
        for label, score in scores.items():
            if label in ("positive", "negative"):
                continue
            if score > best_score:
                best_score = score
                best_label = label
        return best_label if best_score > 0 else None

    @staticmethod
    def _get_top_emotions(
        emotions: EmotionScores,
        top_n: int = 3,
    ) -> list[str]:
        """Return the top N emotion labels by score (> 0)."""
        scores = LexiconSentimentAnalyzer._build_scores(emotions)
        sorted_ = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [name for name, score in sorted_ if score > 0][:top_n]

    @staticmethod
    def _compute_average_vad(
        sentences: list[SentenceSentiment],
    ) -> VADScores:
        """Mean VAD across sentence results."""
        n = len(sentences)
        if n == 0:
            return VADScores(valence=0.0, arousal=0.0, dominance=0.0)
        total_v = sum(s.vad.valence for s in sentences)
        total_a = sum(s.vad.arousal for s in sentences)
        total_d = sum(s.vad.dominance for s in sentences)
        return VADScores(
            valence=round(total_v / n, 4),
            arousal=round(total_a / n, 4),
            dominance=round(total_d / n, 4),
        )

    @staticmethod
    def _compute_overall_emotions(
        sentences: list[SentenceSentiment],
    ) -> EmotionScores:
        """Mean emotion scores across sentence results."""
        n = len(sentences)
        if n == 0:
            return EmotionScores()
        result: dict[str, float] = {}
        for label in _EMOTION_LABELS:
            total = sum(getattr(s.emotions, label, 0.0) for s in sentences)
            result[label] = round(total / n, 4)
        return EmotionScores(**result)
