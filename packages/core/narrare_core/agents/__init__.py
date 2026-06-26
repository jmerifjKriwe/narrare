"""Narrare Agents — erste-Klasse-Bürger für alle Narrare-Agents.

Siehe ADR-015 für die vollständige Modul-Architektur.
"""

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from narrare_core.agents.character_arc_agent import CharacterArcAgent, CharacterArcDeps
from narrare_core.agents.character_arc_types import (
    ArcPhase,
    CharacterArcOutput,
)
from narrare_core.agents.consistency_agent import ConsistencyAgent
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)
from narrare_core.agents.contracts import AgentRegistryProtocol
from narrare_core.agents.coreference_agent import CoreferenceAgent
from narrare_core.agents.coreference_types import (
    CharacterMention,
    CoreferenceDeps,
    CoreferenceOutput,
    PronounResolution,
)
from narrare_core.agents.draft_agent import DraftAgent
from narrare_core.agents.draft_types import DraftConfig, DraftDeps, DraftOutput
from narrare_core.agents.errors import (
    AgentCancelledError,
    AgentError,
    AgentTimeoutError,
    ModelExecutionError,
    ModelRetryExhaustedError,
)
from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.agents.fact_extractor_agent import FactExtractorAgent
from narrare_core.agents.fact_extractor_types import (
    ExtractedFact,
    FactExtractorDeps,
    FactExtractorOutput,
    FactExtractorProtocol,
    TimelineEventEnvelope,
)
from narrare_core.agents.graph_store import GraphStateStore
from narrare_core.agents.history_policy import HistoryPolicy
from narrare_core.agents.inline_suggest_agent import InlineSuggestAgent
from narrare_core.agents.inline_suggest_types import InlineSuggestDeps
from narrare_core.agents.kb_agent import KBAgent, KBDeps
from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import (
    ImprovementSuggestion,
    KBImproveDeps,
    KBImproveOutput,
    KBImproveSuggestion,  # backward-compat alias
    SuggestionType,
)
from narrare_core.agents.merge_agent import KBMergeAgent, KBMergeDeps
from narrare_core.agents.merge_types import (
    MergeDecision,
    MergeOutput,
    MergeStrategy,
)
from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.pov_agent import POVDeps, POVDetectionAgent
from narrare_core.agents.pov_types import (
    POVDetectedIssue,
    POVDetectedScene,
    POVDetectionOutput,
)
from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput
from narrare_core.agents.prompt_live_test_agent import (
    PromptLiveTestAgent,
    PromptLiveTestDeps,
    PromptLiveTestResult,
)
from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
from narrare_core.agents.readability_types import (
    ReadabilityAgentOutput,
    SentenceIssue,
    SentenceSuggestion,
)
from narrare_core.agents.registry import AgentRegistry
from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.story_suggest_agent import StorySuggestAgent
from narrare_core.agents.story_suggest_types import (
    StorySuggestDeps,
    StorySuggestion,
    StorySuggestionType,
    StorySuggestOutput,
)
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.agents.temporal_extraction_agent import (
    TemporalExtractionAgent,
    TemporalExtractionDeps,
)
from narrare_core.agents.temporal_extraction_types import (
    ExtractedTemporalExpression,
    TemporalExtractionOutput,
)
from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps
from narrare_core.agents.timeline_types import (
    TimelineEvent,
    TimelineOutput,
)
from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import (
    Phase1ConnectionOutput,
    Phase1EntitySummary,
    Phase1GapOutput,
    Phase2ConsistencyOutput,
    WorldbuildingDeps,
    WorldbuildingPhase1Output,
    WorldbuildingPhase2Output,
)
from narrare_core.agents.writing_graph import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
    build_writing_graph,
)
from narrare_core.agents.writing_graph_types import create_writing_graph

__all__ = [
    "AgentCancelledError",
    "AgentDeepDiveFeedback",
    "AgentError",
    "AgentFeedbackItem",
    "AgentOverallAssessment",
    "AgentReaderQuestion",
    "AgentRegistry",
    "AgentRegistryProtocol",
    "AgentStrength",
    "AgentTimeoutError",
    "Approved",
    "ArcPhase",
    "BetaReaderAgent",
    "BetaReaderDeps",
    "BetaReaderPhase1Output",
    "BetaReaderPhase2Output",
    "ChapterSummaryAgent",
    "CharacterArcAgent",
    "CharacterArcDeps",
    "CharacterArcOutput",
    "CharacterMention",
    "ConsistencyAgent",
    "ConsistencyCheckType",
    "ConsistencyDeps",
    "ConsistencyIssue",
    "ConsistencyOutput",
    "ConsistencySeverity",
    "CoreferenceAgent",
    "CoreferenceDeps",
    "CoreferenceOutput",
    "DraftAgent",
    "DraftConfig",
    "DraftDeps",
    "DraftOutput",
    "ExtractedFact",
    "ExtractedTemporalExpression",
    "ExtractionAgent",
    "ExtractionDeps",
    "ExtractionItem",
    "ExtractionOutput",
    "FactExtractorAgent",
    "FactExtractorDeps",
    "FactExtractorOutput",
    "FactExtractorProtocol",
    "GraphStateStore",
    "HistoryPolicy",
    "ImprovementSuggestion",
    "InlineSuggestAgent",
    "InlineSuggestDeps",
    "KBAgent",
    "KBAssistAgent",
    "KBAssistDeps",
    "KBAssistOutput",
    "KBDeps",
    "KBImproveAgent",
    "KBImproveDeps",
    "KBImproveOutput",
    "KBImproveSuggestion",
    "KBMergeAgent",
    "KBMergeDeps",
    "MergeDecision",
    "MergeOutput",
    "MergeStrategy",
    "ModelExecutionError",
    "ModelRetryExhaustedError",
    "NarrareAgent",
    "NeedsRevision",
    "OutlineAgent",
    "OutlineDeps",
    "OutlineOutput",
    "POVDeps",
    "POVDetectedIssue",
    "POVDetectedScene",
    "POVDetectionAgent",
    "POVDetectionOutput",
    "Phase1ConnectionOutput",
    "Phase1EntitySummary",
    "Phase1GapOutput",
    "Phase2ConsistencyOutput",
    "PreferenceAnalysisAgent",
    "PreferenceAnalysisDeps",
    "PreferenceAnalysisOutput",
    "PromptLiveTestAgent",
    "PromptLiveTestDeps",
    "PromptLiveTestResult",
    "PronounResolution",
    "ReadabilityAgent",
    "ReadabilityAgentOutput",
    "ReadabilityDeps",
    "ReviewAgent",
    "ReviewDeps",
    "ReviewOutput",
    "SentenceIssue",
    "SentenceSuggestion",
    "StorySuggestAgent",
    "StorySuggestDeps",
    "StorySuggestOutput",
    "StorySuggestion",
    "StorySuggestionType",
    "SuggestionType",
    "SummaryDeps",
    "SummaryOutput",
    "TemporalExtractionAgent",
    "TemporalExtractionDeps",
    "TemporalExtractionOutput",
    "TimelineAgent",
    "TimelineDeps",
    "TimelineEvent",
    "TimelineEventEnvelope",
    "TimelineOutput",
    "WorldbuildingAgent",
    "WorldbuildingDeps",
    "WorldbuildingPhase1Output",
    "WorldbuildingPhase2Output",
    "WritingDeps",
    "WritingState",
    "WritingStatus",
    "build_writing_graph",
    "create_writing_graph",
]
