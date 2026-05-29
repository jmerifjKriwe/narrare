"""Types für den Writing-Graphen.

Enthält WritingState, WritingDeps, WritingStatus und Decision-Signale.
Getrennt von writing_graph.py gemäss RULE-04 (Agent-Definition < 200 Zeilen).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WritingStatus(StrEnum):
    """Status-Lifecycle für den Writing-Graphen."""

    PLANNED = "planned"
    OUTLINED = "outlined"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    NEEDS_REVISION = "needs_revision"
    REVISED = "revised"
    SUMMARIZED = "summarized"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@dataclass
class WritingDeps:
    """Dependencies für den Writing-Graphen.

    Attributes:
        registry: ModelRegistry für Agent-Modelle.
        context_assembler: Assembliert Writing-Kontext.
        model_config: ResolvedModelConfig für den aktuellen LLM-Call.
        api_key: Optionaler API-Key.
        base_url: Optionaler Base-URL.
        chapter_content: Vorhandener Kapitel-Content.
        chapter_outline: Outline.
        genre: Genre.
        word_target: Zielwortzahl.
        tone: Tonfall.
        language: Sprache.
    """

    registry: Any  # ModelRegistry (Any zur Vermeidung von Zirkelimporten)
    composer: Any = None  # PromptComposer (RULE-02, Any zur Vermeidung von Zirkelimporten)
    context_assembler: Any = None  # WritingContextAssembler
    model_config: Any = None  # ResolvedModelConfig
    api_key: str | None = None
    base_url: str | None = None
    chapter_content: str = ""
    chapter_outline: str = ""
    genre: str = ""
    word_target: int | None = None
    tone: str = "balanced"
    language: str = "en"
    writing_language: str = ""  # output language (freetext)
    store: Any = None  # GraphStateStore (Any zur Vermeidung von Zirkelimporten)
    run_id: str = ""
    user_id: str = ""  # User identity for preference auto-injection
    agent_registry: Any = None  # AgentRegistry (optional, ADR-016 Phase 3)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class WritingState:
    """State des Writing-Graphen — wird durch jeden Step mutiert."""

    chapter_id: str = ""
    novel_id: str = ""
    outline: str = ""
    draft: str = ""
    revision: str = ""
    final: str = ""
    summary: str = ""
    status: WritingStatus = WritingStatus.PLANNED
    attempts: int = 0
    feedback: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Decision Signals
# ---------------------------------------------------------------------------


@dataclass
class Approved:
    """Signal: Draft ist genehmigt."""


@dataclass
class NeedsRevision:
    """Signal: Draft benötigt Überarbeitung."""

    feedback: str = ""


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def create_writing_graph() -> Any:
    """Convenience: build and return the Writing-Graph."""
    from narrare_core.agents.writing_graph import build_writing_graph

    return build_writing_graph().build()
