"""Eval models for the kb_operations suite.

Extracted from ``evals/models.py`` to keep that module below RULE-04 limits.
All symbols are re-exported from ``evals.models``.

The four KB operation agents have structurally different outputs. Mirroring
the ``planning_structure`` pattern, the kb_operations result is a union model
with one optional section per agent. Exactly one section is populated,
matching the case's ``agent_type``.

Validated schemas and invariants are sourced from real core symbols:

- KBAgentOperationSection mirrors ``kb_agent.KBAgent`` tool operations:
  ``search_kb``, ``get_entity``, ``get_related_entities``.
- KBAssistSection mirrors ``kb_assist_types.KBAssistOutput``.
- KBImproveSection / KBImproveSuggestionSection mirror
  ``kb_improve_types.KBImproveOutput`` / ``ImprovementSuggestion``.
- KBMergeSection / KBMergeDecisionSection / KBMergeStrategySection mirror
  ``merge_types.MergeOutput`` / ``MergeDecision`` / ``MergeStrategy``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


def _empty_context_used() -> list[str]:
    """Return a typed empty context-used list."""

    return []


def _empty_improvement_suggestions() -> list[KBImproveSuggestionSection]:
    """Return a typed empty improvement-suggestion list."""

    return []


def _empty_merge_decisions() -> list[KBMergeDecisionSection]:
    """Return a typed empty merge-decision list."""

    return []


def _empty_merge_fields() -> dict[str, str]:
    """Return a typed empty merge-fields mapping."""

    return {}


def _empty_aliases() -> list[str]:
    """Return a typed empty alias list."""

    return []


def _empty_metadata() -> dict[str, Any]:
    """Return a typed empty metadata mapping."""

    return {}


class KBAgentOperationSection(BaseModel):
    """KBAgent tool-operation output section.

    Mirrors the public tool surface of ``narrare_core.agents.kb_agent.KBAgent``.
    """

    operation: str = ""
    query: str = ""
    entity_type: str | None = None
    entity_name: str = ""
    relation_type: str | None = None
    formatted_response: str = ""


class KBAssistSection(BaseModel):
    """KB assist output section.

    Mirrors ``narrare_core.agents.kb_assist_types.KBAssistOutput``.
    """

    mode: Literal["question", "suggestion", "draft", "complete"]
    question: str | None = None
    field_key: str | None = None
    suggestion: str | None = None
    reasoning: str | None = None
    context_used: list[str] | None = None
    draft_entry: dict[str, Any] | None = None
    final_entry: dict[str, Any] | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


class KBImproveSuggestionSection(BaseModel):
    """Single KB improvement suggestion.

    Mirrors ``narrare_core.agents.kb_improve_types.ImprovementSuggestion``.
    """

    type: str = ""
    target: str = ""
    description: str = ""
    proposed_content: str | None = None
    related_entity_id: str | None = None
    related_entity_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str | None = None


class KBImproveSection(BaseModel):
    """KB improvement analysis output section.

    Mirrors ``narrare_core.agents.kb_improve_types.KBImproveOutput``.
    """

    suggestions: list[KBImproveSuggestionSection] = Field(
        default_factory=_empty_improvement_suggestions
    )
    overall_assessment: str = ""
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    context_used: list[str] = Field(default_factory=_empty_context_used)


class KBMergeStrategySection(BaseModel):
    """Merge strategy section. Mirrors ``merge_types.MergeStrategy``."""

    keep_name: str = ""
    merge_fields: dict[str, str] = Field(default_factory=_empty_merge_fields)
    preserve_aliases: list[str] = Field(default_factory=_empty_aliases)
    merge_relationships: bool = True


class KBMergeDecisionSection(BaseModel):
    """Single merge decision. Mirrors ``merge_types.MergeDecision``."""

    pair_id: str = ""
    decision: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    merge_strategy: KBMergeStrategySection | None = None


class KBMergeSection(BaseModel):
    """KB merge output section. Mirrors ``merge_types.MergeOutput``."""

    merge_decisions: list[KBMergeDecisionSection] = Field(default_factory=_empty_merge_decisions)
    overall_notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=_empty_metadata)


class KBOperationsInput(BaseModel):
    """Input for KB operations eval cases."""

    agent_type: Literal["kb_agent", "kb_assist", "kb_improve", "kb_merge"]
    prompt_text: str
    entity_type: str = "character"
    field_key: str = "name"
    language: str = "en"


class KBOperationsResult(BaseModel):
    """Union result for the kb_operations eval suite.

    Exactly one section is populated, matching the case's ``agent_type``.
    """

    kb_agent: KBAgentOperationSection | None = None
    kb_assist: KBAssistSection | None = None
    kb_improve: KBImproveSection | None = None
    kb_merge: KBMergeSection | None = None
