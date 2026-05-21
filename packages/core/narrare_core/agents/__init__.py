"""Narrare Agents — erste-Klasse-Bürger für alle Narrare-Agents.

Siehe ADR-015 für die vollständige Modul-Architektur.
"""

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftConfig, DraftOutput
from narrare_core.agents.graph_store import GraphStateStore
from narrare_core.agents.kb_agent import KBAgent, KBDeps
from narrare_core.agents.writing_graph import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
    build_writing_graph,
    create_writing_graph,
)

__all__ = [
    "Approved",
    "DraftAgent",
    "DraftConfig",
    "DraftDeps",
    "DraftOutput",
    "GraphStateStore",
    "KBAgent",
    "KBDeps",
    "NarrareAgent",
    "NeedsRevision",
    "WritingDeps",
    "WritingState",
    "WritingStatus",
    "build_writing_graph",
    "create_writing_graph",
]
