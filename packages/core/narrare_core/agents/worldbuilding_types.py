"""Output types for WorldbuildingAgent.

Two output modes:
  - Phase 1 (Gap + Connections): Entity-summary-level analysis
  - Phase 2 (Consistency): Entity-pair-depth analysis

Follows the same pattern as kb_improve_types.py and kb_assist_types.py.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Phase 1: Gap Detection + Connection Suggestions (combined output)
# ---------------------------------------------------------------------------


class Phase1EntitySummary(BaseModel):
    """Summary of a single entity for the Phase 1 analysis prompt."""

    entry_id: str
    name: str
    entity_type: str
    field_fill_rate: float  # What fraction of template fields are non-empty
    relationship_count: int
    has_body: bool
    chapter_references: int  # How many chapters reference this entity


class Phase1GapOutput(BaseModel):
    """A single gap finding from Phase 1."""

    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    gap_type: str  # missing_entity, missing_field, missing_connection, missing_body
    field_key: str | None = None
    description: str
    related_entity_type: str | None = None
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    severity: str = "major"


class Phase1ConnectionOutput(BaseModel):
    """A single connection suggestion from Phase 1."""

    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    suggested_rel_type: str
    inverse_rel_type: str | None = None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)


class WorldbuildingPhase1Output(BaseModel):
    """Combined output of Phase 1 analysis."""

    gaps: list[Phase1GapOutput]
    connection_suggestions: list[Phase1ConnectionOutput]
    assessment: str
    worldbuilding_score: float = Field(ge=0.0, le=1.0)
    candidate_pairs_for_consistency: list[tuple[str, str]]  # Entity ID pairs to check


# ---------------------------------------------------------------------------
# Phase 2: Consistency Checking (separate, detailed)
# ---------------------------------------------------------------------------


class Phase2ConsistencyOutput(BaseModel):
    """A single consistency issue from Phase 2."""

    category: str  # geography, politics, economics, system_rules, timeline, character
    entity_ids: list[str]
    entity_names: list[str]
    description: str
    contradiction: str
    suggested_resolution: str | None = None
    severity: str = "major"
    confidence: float = Field(ge=0.0, le=1.0)


class WorldbuildingPhase2Output(BaseModel):
    """Output of Phase 2 consistency checking."""

    issues: list[Phase2ConsistencyOutput]
    assessment: str  # Overall consistency assessment


# ---------------------------------------------------------------------------
# Agent Dependencies
# ---------------------------------------------------------------------------


class WorldbuildingDeps(BaseModel):
    """Dependencies for WorldbuildingAgent.

    Attributes:
        language: Output language code.
        entity_summaries: Summary list of all entities (for Phase 1).
        entity_details: Full entity details keyed by ID (for Phase 2 lookup).
        template_structures: Template field definitions keyed by entity type.
        existing_relationships: All relationships in the project.
        available_rel_types: Entity-type-pair -> possible relationship types.
        world_context: KB context from ProactiveContextService.
        chapter_entity_refs: Entity IDs -> chapter reference count.
        candidate_pairs: For Phase 2 — entity ID pairs to check for consistency.
    """

    language: str = "en"
    entity_summaries: list[Phase1EntitySummary] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    entity_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    template_structures: dict[str, dict[str, Any]] = Field(default_factory=dict)
    existing_relationships: list[dict[str, Any]] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    available_rel_types: dict[str, list[str]] = Field(default_factory=dict)
    world_context: str = ""
    chapter_entity_refs: dict[str, int] = Field(default_factory=dict)
    candidate_pairs: list[tuple[str, str]] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
