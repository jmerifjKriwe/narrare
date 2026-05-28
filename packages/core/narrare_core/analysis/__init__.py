"""Analysis services — deterministic computation layer.

All analysis algorithms are pure, deterministic computations that use
the NLPProvider (``core/nlp/``) for linguistic features.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
"""

from narrare_core.analysis.contracts import (
    NarrativeArcType,
    SentimentAnalyzer,
)
from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.types import (
    EmotionScores,
    NarrativeArc,
    SentenceSentiment,
    SentimentOverview,
    VADScores,
)

__all__ = [
    "EmotionScores",
    "LexiconSentimentAnalyzer",
    "NarrativeArc",
    "NarrativeArcType",
    "SentenceSentiment",
    "SentimentAnalyzer",
    "SentimentOverview",
    "VADScores",
]
