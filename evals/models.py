"""Typed case inputs and outputs for Narrare eval suites — re-export hub.

Per RULE-04 (file-size limits force modularization, not compression) every
suite's models live in its own ``evals/models_<suite>.py`` module and are
re-exported here, so existing ``from evals.models import ...`` imports keep
working. This module intentionally contains no model definitions.

Suite modules:

- ``models_analysis_feedback`` — beta_reader / review / consistency feedback
- ``models_analysis_metrics`` — Readability / POV / ChapterSummary (union)
- ``models_chat`` — chat / draft / inline_suggest generation
- ``models_dialogue_coach`` — dialogue coach weights
- ``models_kb_extraction`` — chapter-to-KB extraction
- ``models_kb_operations`` — KB assist / improve / merge (union)
- ``models_names`` — name generation (smoke-only suite)
- ``models_planning`` — Outline / CharacterArc / Timeline / Worldbuilding
  (union); see that module for the plan-vs-reality note (OutlineAgent has
  no "variant count" concept)
- ``models_preference`` — preference extraction from feedback events
- ``models_rewrite`` — inline rewrite mode selection
- ``models_writing`` — writing prose quality
"""

from evals.models_analysis_feedback import (
    AnalysisFeedbackInput,
    AnalysisFeedbackResult,
)
from evals.models_analysis_metrics import (
    AnalysisMetricsInput,
    AnalysisMetricsResult,
    POVMetricsIssue,
    POVMetricsScene,
    POVSection,
    ReadabilitySection,
    SummarySection,
)
from evals.models_chat import (
    ChatGenerationInput,
    ChatGenerationResult,
    DraftOutputField,
)
from evals.models_dialogue_coach import (
    DialogueCoachEvalInput,
    DialogueCoachEvalResult,
    DialogueCoachWeightResult,
)
from evals.models_kb_extraction import (
    KBExtractionInput,
    KBExtractionItem,
    KBExtractionResult,
)
from evals.models_kb_operations import (
    KBAgentOperationSection,
    KBAssistSection,
    KBImproveSection,
    KBImproveSuggestionSection,
    KBMergeDecisionSection,
    KBMergeSection,
    KBMergeStrategySection,
    KBOperationsInput,
    KBOperationsResult,
)
from evals.models_names import (
    NameGenerationInput,
    NameGenerationResult,
)
from evals.models_planning import (
    CharacterArcPhaseSection,
    CharacterArcSection,
    OutlineSection,
    PlanningStructureInput,
    PlanningStructureResult,
    TimelineEventSection,
    TimelineSection,
    WorldbuildingConnectionSection,
    WorldbuildingGapSection,
    WorldbuildingSection,
)
from evals.models_preference import (
    PreferenceAnalysisInput,
    PreferenceAnalysisResult,
)
from evals.models_rewrite import (
    RewriteSelectionInput,
    RewriteSelectionResult,
)
from evals.models_writing import (
    WritingProseInput,
    WritingProseResult,
)

__all__ = [
    "AnalysisFeedbackInput",
    "AnalysisFeedbackResult",
    "AnalysisMetricsInput",
    "AnalysisMetricsResult",
    "CharacterArcPhaseSection",
    "CharacterArcSection",
    "ChatGenerationInput",
    "ChatGenerationResult",
    "DialogueCoachEvalInput",
    "DialogueCoachEvalResult",
    "DialogueCoachWeightResult",
    "DraftOutputField",
    "KBAgentOperationSection",
    "KBAssistSection",
    "KBExtractionInput",
    "KBExtractionItem",
    "KBExtractionResult",
    "KBImproveSection",
    "KBImproveSuggestionSection",
    "KBMergeDecisionSection",
    "KBMergeSection",
    "KBMergeStrategySection",
    "KBOperationsInput",
    "KBOperationsResult",
    "NameGenerationInput",
    "NameGenerationResult",
    "OutlineSection",
    "POVMetricsIssue",
    "POVMetricsScene",
    "POVSection",
    "PlanningStructureInput",
    "PlanningStructureResult",
    "PreferenceAnalysisInput",
    "PreferenceAnalysisResult",
    "ReadabilitySection",
    "RewriteSelectionInput",
    "RewriteSelectionResult",
    "SummarySection",
    "TimelineEventSection",
    "TimelineSection",
    "WorldbuildingConnectionSection",
    "WorldbuildingGapSection",
    "WorldbuildingSection",
    "WritingProseInput",
    "WritingProseResult",
]
