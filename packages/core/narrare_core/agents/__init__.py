"""Narrare Agents — erste-Klasse-Bürger für alle Narrare-Agents.

Siehe ADR-015 für die vollständige Modul-Architektur.
"""

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftConfig, DraftOutput
from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.agents.graph_store import GraphStateStore
from narrare_core.agents.kb_agent import KBAgent, KBDeps
from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput
from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput
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
    "Approved",
    "ChapterSummaryAgent",
    "DraftAgent",
    "DraftConfig",
    "DraftDeps",
    "DraftOutput",
    "ExtractionAgent",
    "ExtractionDeps",
    "ExtractionItem",
    "ExtractionOutput",
    "GraphStateStore",
    "KBAgent",
    "KBAssistAgent",
    "KBAssistDeps",
    "KBAssistOutput",
    "KBDeps",
    "NarrareAgent",
    "NeedsRevision",
    "OutlineAgent",
    "OutlineDeps",
    "OutlineOutput",
    "PreferenceAnalysisAgent",
    "PreferenceAnalysisDeps",
    "PreferenceAnalysisOutput",
    "ReviewAgent",
    "ReviewDeps",
    "ReviewOutput",
    "SummaryDeps",
    "SummaryOutput",
    "WritingDeps",
    "WritingState",
    "WritingStatus",
    "build_writing_graph",
    "create_writing_graph",
]
