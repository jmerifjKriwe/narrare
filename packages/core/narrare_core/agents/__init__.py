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
from narrare_core.agents.consistency_agent import ConsistencyAgent
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)
from narrare_core.agents.contracts import AgentRegistryProtocol
from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftConfig, DraftOutput
from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.agents.graph_store import GraphStateStore
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
from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput
from narrare_core.agents.registry import AgentRegistry
from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput
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
    "AgentDeepDiveFeedback",
    "AgentFeedbackItem",
    "AgentOverallAssessment",
    "AgentReaderQuestion",
    "AgentRegistry",
    "AgentRegistryProtocol",
    "AgentStrength",
    "Approved",
    "BetaReaderAgent",
    "BetaReaderDeps",
    "BetaReaderPhase1Output",
    "BetaReaderPhase2Output",
    "ChapterSummaryAgent",
    "ConsistencyAgent",
    "ConsistencyCheckType",
    "ConsistencyDeps",
    "ConsistencyIssue",
    "ConsistencyOutput",
    "ConsistencySeverity",
    "DraftAgent",
    "DraftConfig",
    "DraftDeps",
    "DraftOutput",
    "ExtractionAgent",
    "ExtractionDeps",
    "ExtractionItem",
    "ExtractionOutput",
    "GraphStateStore",
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
    "NarrareAgent",
    "NeedsRevision",
    "OutlineAgent",
    "OutlineDeps",
    "OutlineOutput",
    "Phase1ConnectionOutput",
    "Phase1EntitySummary",
    "Phase1GapOutput",
    "Phase2ConsistencyOutput",
    "PreferenceAnalysisAgent",
    "PreferenceAnalysisDeps",
    "PreferenceAnalysisOutput",
    "ReviewAgent",
    "ReviewDeps",
    "ReviewOutput",
    "SuggestionType",
    "SummaryDeps",
    "SummaryOutput",
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
