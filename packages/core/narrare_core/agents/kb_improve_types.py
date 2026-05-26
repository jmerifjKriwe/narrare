"""Output types for KBImproveAgent — analysis-based entry improvement.

The improve agent analyzes an existing KB entry and returns a list
of structured suggestions with confidence scores, rather than producing
a filled entity (which is what the enhance mode does).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SuggestionType(StrEnum):
    ADD_FIELD = "add_field"  # Missing field that should be filled
    CONNECT = "connect"  # Unlinked related entity
    EXPAND = "expand"  # Existing field too sparse
    REORGANIZE = "reorganize"  # Structural improvement


class ImprovementSuggestion(BaseModel):
    """A single improvement suggestion for a KB entry.

    Attributes:
        type: Category of improvement.
        target: Field key (add_field/expand) or entity name (connect).
        description: Human-readable explanation of what and why.
        proposed_content: Suggested value for add_field/expand.
        related_entity_id: UUID str of entity to connect (connect only).
        related_entity_name: Name of entity to connect (connect only).
        confidence: Score 0.0-1.0 for how confident the AI is.
        reasoning: Chain-of-thought explanation.
    """

    type: SuggestionType
    target: str
    description: str
    proposed_content: str | None = None
    related_entity_id: str | None = None
    related_entity_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


class KBImproveOutput(BaseModel):
    """Structured output from KBImproveAgent analysis.

    Attributes:
        suggestions: List of improvement suggestions (max 8).
        overall_assessment: Brief summary of entry quality.
        completeness_score: How complete the entry is (0.0-1.0).
        context_used: Entity names referenced during analysis.
    """

    suggestions: list[ImprovementSuggestion]
    overall_assessment: str
    completeness_score: float = Field(ge=0.0, le=1.0)
    context_used: list[str] = []


class KBImproveDeps:
    """Dependencies for KBImproveAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Project genre for context.
        entity_type: Target entity type (character, location, etc.).
        template_structure: JSON schema of the entity type template fields.
        entry_content: Current entry metadata + body content.
        existing_relationships: Current relationships as list of dicts.
        world_context: Assembled world context from KB or ProactiveContext.
        adjacency_map: Connected entity IDs.
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        entity_type: str = "",
        template_structure: dict[str, Any] | None = None,
        entry_content: dict[str, Any] | None = None,
        existing_relationships: list[dict[str, Any]] | None = None,
        world_context: str | None = None,
        adjacency_map: dict[str, set[str]] | None = None,
    ) -> None:
        self.language = language
        self.genre = genre
        self.entity_type = entity_type
        self.template_structure = template_structure
        self.entry_content = entry_content
        self.existing_relationships = existing_relationships
        self.world_context = world_context
        self.adjacency_map = adjacency_map
