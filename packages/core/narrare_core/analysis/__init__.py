"""Analysis services — deterministic computation layer.

All analysis algorithms are pure, deterministic computations that use
the NLPProvider (``core/nlp/``) for linguistic features.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
ADR-025 Decision 3 — ContextAssembler Centralization (Phase 5).
"""

from narrare_core.analysis.age_check import CharacterAgeCheck
from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.analysis.author_metrics import AuthorMetrics, AuthorMetricsAnalyzer
from narrare_core.analysis.author_voice_drift_scoring import (
    PerAuthorChapterMetrics,
    compute_per_chapter_author_metrics,
    detect_adjacent_author_jumps,
    trend_against_author_profile,
)
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
from narrare_core.analysis.duration_check import DurationImpossibilityCheck
from narrare_core.analysis.readability import FormulaReadabilityAnalyzer
from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.temporal import (
    DuplicateEventCheck,
    TemporalOrderingCheck,
    run_deterministic_checks,
)
from narrare_core.analysis.temporal_types import (
    TemporalConsistencyResult,
    TemporalIssue,
    TemporalIssueSeverity,
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
from narrare_core.analysis.voice_check_scoring import (
    VoiceCheckBand,
    VoiceCheckScore,
    VoiceCheckScorer,
    author_metric_distances,
    band_for_score,
    blend_scores,
    metric_delta_subscore,
    voice_metric_distances,
)
from narrare_core.analysis.voice_drift_scoring import (
    DEFAULT_JUMP_THRESHOLD,
    JumpPoint,
    PerChapterMetrics,
    TrendPoint,
    compute_per_chapter_metrics,
    detect_adjacent_jumps,
    trend_against_profile,
)
from narrare_core.analysis.voice_merge import merge_character_voice
from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
from narrare_core.analysis.voice_types import AttributedUtterance

__all__ = [
    "DEFAULT_JUMP_THRESHOLD",
    "AnalysisAssemblerProtocol",
    "AnalysisBudgetManager",
    "AnalysisContextAssembler",
    "AttributedUtterance",
    "AuthorMetrics",
    "AuthorMetricsAnalyzer",
    "CharacterAgeCheck",
    "DuplicateEventCheck",
    "DurationImpossibilityCheck",
    "EmotionScores",
    "FormulaReadabilityAnalyzer",
    "JumpPoint",
    "LexiconSentimentAnalyzer",
    "NarrativeArc",
    "NarrativeArcType",
    "POVDetector",
    "POVIssue",
    "POVIssueType",
    "POVResult",
    "POVScene",
    "PerAuthorChapterMetrics",
    "PerChapterMetrics",
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
    "TrendPoint",
    "VADScores",
    "VoiceCheckBand",
    "VoiceCheckScore",
    "VoiceCheckScorer",
    "VoiceMetricsAnalyzer",
    "author_metric_distances",
    "band_for_score",
    "blend_scores",
    "compute_per_chapter_author_metrics",
    "compute_per_chapter_metrics",
    "detect_adjacent_author_jumps",
    "detect_adjacent_jumps",
    "merge_character_voice",
    "metric_delta_subscore",
    "run_deterministic_checks",
    "trend_against_author_profile",
    "trend_against_profile",
    "voice_metric_distances",
]
