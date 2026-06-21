"""Eval models for the planning_structure suite.

Extracted from ``evals/models.py`` to keep that module within the RULE-04
file-size limit (architectural-discipline: file-size limits force
modularization, not compression). All symbols are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The four planning-panel agents (Outline, CharacterArc, Timeline, Worldbuilding)
produce structurally different outputs. Mirroring the analysis_metrics pattern,
the planning_structure result is a union model with one optional section per
agent. Exactly one section is populated, matching the case's ``agent_type``.

Reality check (per architectural-discipline): the eval-expansion plan prose
says OutlineAgent tests "variant count compliance", but the REAL
``OutlineOutput`` has no variant concept — its invariants are a non-empty
``chapter_title`` and at least one non-empty scene. The validators assert the
real schema, not the plan prose.

Each section mirrors its authoritative agent output type:

- OutlineSection            → ``narrare_core.agents.outline_types.OutlineOutput``
- CharacterArcSection       → ``narrare_core.agents.character_arc_types.CharacterArcOutput``
- CharacterArcPhaseSection  → ``narrare_core.agents.character_arc_types.ArcPhase``
- TimelineSection           → ``narrare_core.agents.timeline_types.TimelineOutput``
- TimelineEventSection      → ``narrare_core.agents.timeline_types.TimelineEvent``
- WorldbuildingSection      → ``narrare_core.agents.worldbuilding_types.WorldbuildingPhase1Output``
- WorldbuildingGapSection   → ``narrare_core.agents.worldbuilding_types.Phase1GapOutput``
- WorldbuildingConnectionSection →
  ``narrare_core.agents.worldbuilding_types.Phase1ConnectionOutput``
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


def _empty_outline_scenes() -> list[str]:
    """Return a typed empty outline scene list."""

    return []


def _empty_arc_phases() -> list[CharacterArcPhaseSection]:
    """Return a typed empty arc phase list."""

    return []


def _empty_arc_relationships() -> list[str]:
    """Return a typed empty key-relationships list."""

    return []


def _empty_timeline_events() -> list[TimelineEventSection]:
    """Return a typed empty timeline event list."""

    return []


def _empty_timeline_conflicts() -> list[str]:
    """Return a typed empty temporal-conflicts list."""

    return []


def _empty_coverage_gaps() -> list[str]:
    """Return a typed empty coverage-gaps list."""

    return []


def _empty_worldbuilding_gaps() -> list[WorldbuildingGapSection]:
    """Return a typed empty worldbuilding gap list."""

    return []


def _empty_worldbuilding_connections() -> list[WorldbuildingConnectionSection]:
    """Return a typed empty worldbuilding connection list."""

    return []


def _empty_candidate_pairs() -> list[tuple[str, str]]:
    """Return a typed empty candidate-pairs list."""

    return []


class OutlineSection(BaseModel):
    """Outline agent output section.

    Mirrors ``narrare_core.agents.outline_types.OutlineOutput``.
    """

    chapter_title: str = ""
    scenes: list[str] = Field(default_factory=_empty_outline_scenes)
    outline_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterArcPhaseSection(BaseModel):
    """Single arc phase. Mirrors ``narrare_core.agents.character_arc_types.ArcPhase``."""

    phase_name: str = ""
    description: str = ""
    emotional_state: str = ""
    turning_point: str = ""
    chapters_suggested: str = ""


class CharacterArcSection(BaseModel):
    """Character arc agent output section.

    Mirrors ``narrare_core.agents.character_arc_types.CharacterArcOutput``.
    """

    character_name: str = ""
    starting_state: str = ""
    ending_state: str = ""
    arc_type: str = ""
    phases: list[CharacterArcPhaseSection] = Field(default_factory=_empty_arc_phases)
    key_relationships: list[str] = Field(default_factory=_empty_arc_relationships)
    internal_conflict: str = ""
    resolution: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineEventSection(BaseModel):
    """Single timeline event. Mirrors ``narrare_core.agents.timeline_types.TimelineEvent``."""

    event_name: str = ""
    description: str = ""
    timestamp: str = ""
    chapter_reference: str = ""
    characters_involved: list[str] = Field(default_factory=list)
    location: str = ""
    causes: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)


class TimelineSection(BaseModel):
    """Timeline agent output section.

    Mirrors ``narrare_core.agents.timeline_types.TimelineOutput``.
    """

    timeline_events: list[TimelineEventSection] = Field(default_factory=_empty_timeline_events)
    temporal_conflicts: list[str] = Field(default_factory=_empty_timeline_conflicts)
    coverage_gaps: list[str] = Field(default_factory=_empty_coverage_gaps)
    overall_assessment: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldbuildingGapSection(BaseModel):
    """Single Phase 1 gap. Mirrors ``narrare_core.agents.worldbuilding_types.Phase1GapOutput``."""

    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    gap_type: str = ""
    field_key: str | None = None
    description: str = ""
    related_entity_type: str | None = None
    story_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: str = "major"


class WorldbuildingConnectionSection(BaseModel):
    """Single Phase 1 connection. Mirrors ``Phase1ConnectionOutput``."""

    source_entity_id: str = ""
    source_entity_name: str = ""
    target_entity_id: str = ""
    target_entity_name: str = ""
    suggested_rel_type: str = ""
    inverse_rel_type: str | None = None
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    story_relevance: float = Field(default=0.5, ge=0.0, le=1.0)


class WorldbuildingSection(BaseModel):
    """Worldbuilding Phase 1 output section.

    Mirrors ``narrare_core.agents.worldbuilding_types.WorldbuildingPhase1Output``.
    """

    gaps: list[WorldbuildingGapSection] = Field(default_factory=_empty_worldbuilding_gaps)
    connection_suggestions: list[WorldbuildingConnectionSection] = Field(
        default_factory=_empty_worldbuilding_connections
    )
    assessment: str = ""
    worldbuilding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_pairs_for_consistency: list[tuple[str, str]] = Field(
        default_factory=_empty_candidate_pairs
    )


class PlanningStructureInput(BaseModel):
    """Input for planning structure eval cases."""

    agent_type: Literal["outline", "character_arc", "timeline", "worldbuilding"]
    prompt_text: str
    genre: str = "Fantasy"
    language: str = "en"


class PlanningStructureResult(BaseModel):
    """Union result for the planning_structure eval suite.

    Exactly one section is populated, matching the case's ``agent_type``.
    """

    outline: OutlineSection | None = None
    character_arc: CharacterArcSection | None = None
    timeline: TimelineSection | None = None
    worldbuilding: WorldbuildingSection | None = None
