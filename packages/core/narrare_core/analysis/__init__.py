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
from narrare_core.analysis.contracts_pov import POVDetector
from narrare_core.analysis.contracts_readability import (
    ReadabilityAgentProtocol,
    ReadabilityAnalyzer,
)
from narrare_core.analysis.readability import FormulaReadabilityAnalyzer
from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.temporal import (
    DuplicateEventCheck,
    DurationImpossibilityCheck,
    TemporalConsistencyResult,
    TemporalIssue,
    TemporalIssueSeverity,
    TemporalOrderingCheck,
    run_deterministic_checks,
)
from narrare_core.analysis.types import (
    EmotionScores,
    NarrativeArc,
    POVIssue,
    POVIssueType,
    POVResult,
    POVScene,
    ReadabilityMetrics,
    ReadabilityResult,
    SentenceAnalysis,
    SentenceSentiment,
    SentimentOverview,
    VADScores,
)

__all__ = [
    "AnalysisAssemblerProtocol",
    "AnalysisBudgetManager",
    "AnalysisContextAssembler",
    "DuplicateEventCheck",
    "DurationImpossibilityCheck",
    "EmotionScores",
    "FormulaReadabilityAnalyzer",
    "LexiconSentimentAnalyzer",
    "NarrativeArc",
    "NarrativeArcType",
    "POVDetector",
    "POVIssue",
    "POVIssueType",
    "POVResult",
    "POVScene",
    "ReadabilityAgentProtocol",
    "ReadabilityAnalyzer",
    "ReadabilityMetrics",
    "ReadabilityResult",
    "SentenceAnalysis",
    "SentenceSentiment",
    "SentimentAnalyzer",
    "SentimentOverview",
    "TemporalConsistencyResult",
    "TemporalIssue",
    "TemporalIssueSeverity",
    "TemporalOrderingCheck",
    "VADScores",
    "run_deterministic_checks",
]
