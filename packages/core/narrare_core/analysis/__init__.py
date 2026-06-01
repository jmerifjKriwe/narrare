"""Analysis services — deterministic computation layer.

All analysis algorithms are pure, deterministic computations that use
the NLPProvider (``core/nlp/``) for linguistic features.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
ADR-025 Decision 3 — ContextAssembler Centralization (Phase 5).
"""

from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.analysis.budget import AnalysisBudgetManager
from narrare_core.analysis.contracts import (
    AnalysisAssemblerProtocol,
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
    "AnalysisAssemblerProtocol",
    "AnalysisBudgetManager",
    "AnalysisContextAssembler",
    "EmotionScores",
    "LexiconSentimentAnalyzer",
    "NarrativeArc",
    "NarrativeArcType",
    "SentenceSentiment",
    "SentimentAnalyzer",
    "SentimentOverview",
    "VADScores",
]
