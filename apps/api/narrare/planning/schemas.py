"""Planning domain — Pydantic request/response schemas.

All schemas for the storyboard feature: outlines, sync status,
and structure remap.

PLAN-001 T14 (ADR-096): the outline surface is beat-free — scene plans
(`schemas_scenes.py`) are the planning substrate. Unknown request fields
(e.g. a legacy client still sending beat data) are ignored by Pydantic
default config.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Outline schemas
# ---------------------------------------------------------------------------


class OutlineUpdateRequest(BaseModel):
    """Request body for updating a chapter outline."""

    stage_assignment: str | None = Field(default=None, max_length=50)
    outline_notes: str | None = None


class OutlineResponse(BaseModel):
    """Full chapter outline with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    stage_assignment: str
    outline_notes: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Storyboard view schemas
# ---------------------------------------------------------------------------


class ChapterInStoryboard(BaseModel):
    """Compact chapter info for the storyboard view."""

    chapter_id: uuid.UUID
    title: str
    word_count: int
    sync_status: str
    position: int


class StoryboardStageResponse(BaseModel):
    """A single stage within the storyboard, with its chapters."""

    stage_id: str
    stage_name: str
    chapters: list[ChapterInStoryboard]


class StoryboardResponse(BaseModel):
    """Complete storyboard view for a novel."""

    structure_type: str
    stages: list[StoryboardStageResponse]


# ---------------------------------------------------------------------------
# Sync status schemas
# ---------------------------------------------------------------------------


class SyncStatusResponse(BaseModel):
    """Sync status for a single chapter."""

    chapter_id: uuid.UUID
    sync_status: str


# ---------------------------------------------------------------------------
# Remap schemas
# ---------------------------------------------------------------------------


class RemapPreviewItem(BaseModel):
    """Single chapter remap preview — old stage to new stage."""

    chapter_id: uuid.UUID
    chapter_title: str
    old_stage: str
    new_stage: str


class RemapRequest(BaseModel):
    """Request to preview or confirm a structure remap."""

    new_structure: str
    confirm: bool = False


class RemapResponse(BaseModel):
    """Response for remap preview or confirmation."""

    new_structure: str
    remapped: list[RemapPreviewItem]
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Character arc schemas
# ---------------------------------------------------------------------------


class CharacterArcRequest(BaseModel):
    """Request body for character arc generation."""

    character_name: str = Field(min_length=1, max_length=200)
    character_current_state: str = ""
    character_goal_state: str = ""


class ArcPhaseResponse(BaseModel):
    """A single phase in a character arc."""

    phase_name: str = ""
    description: str = ""
    emotional_state: str = ""
    turning_point: str = ""
    chapters_suggested: str = ""


class CharacterArcResponse(BaseModel):
    """Response with full character arc analysis."""

    character_name: str = ""
    starting_state: str = ""
    ending_state: str = ""
    arc_type: str = ""
    phases: list[ArcPhaseResponse] = []
    key_relationships: list[str] = []
    internal_conflict: str = ""
    resolution: str = ""


# ---------------------------------------------------------------------------
# Timeline schemas
# ---------------------------------------------------------------------------


class TimelineEventResponse(BaseModel):
    """A single event in the narrative timeline."""

    event_name: str = ""
    description: str = ""
    timestamp: str = ""
    chapter_reference: str = ""
    characters_involved: list[str] = []
    location: str = ""
    causes: list[str] = []
    consequences: list[str] = []


class TimelineResponse(BaseModel):
    """Response with full timeline analysis."""

    timeline_events: list[TimelineEventResponse] = []
    temporal_conflicts: list[str] = []
    coverage_gaps: list[str] = []
    overall_assessment: str = ""
