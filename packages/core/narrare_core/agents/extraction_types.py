"""Output types for ExtractionAgent.

See design.md D3 — structured list output with confidence scoring.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExtractionItem(BaseModel):
    """A single extraction result from chapter text.

    Attributes:
        item_type: What kind of extraction this is.
        entity_type: KB entity type (character, location, etc.) for new/update.
        name: Entity or relationship name.
        confidence: Confidence score 0.0-1.0.
        source_text: Exact quote from chapter text supporting this extraction.
        proposed_content: Suggested metadata fields for new/update entities.
        target_entity_id: ID of existing entity (update_entity mode).
        conflict_description: What contradicts existing KB data (conflict mode).
        relationship_type: Type of relationship (ally, member_of, etc.).
        related_entity_name: The other entity in a relationship.
    """

    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    entity_type: str | None = None
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    proposed_content: dict[str, Any] | None = None
    target_entity_id: str | None = None
    conflict_description: str | None = None
    relationship_type: str | None = None
    related_entity_name: str | None = None


class ExtractionOutput(BaseModel):
    """Structured output of an ExtractionAgent run.

    Attributes:
        results: List of extracted items from the chapter text.
        analysis_notes: Agent's overall observations about the text.
    """

    results: list[ExtractionItem] = []
    analysis_notes: str = ""
