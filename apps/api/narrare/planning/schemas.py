"""Planning domain — Pydantic request/response schemas.

All schemas for the storyboard feature: outlines, sync status,
and structure remap.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Beat schemas
# ---------------------------------------------------------------------------


class BeatSchema(BaseModel):
    """A single beat within a chapter outline."""

    title: str
    description: str = ""
    completed: bool = False


# ---------------------------------------------------------------------------
# Outline schemas
# ---------------------------------------------------------------------------


class OutlineUpdateRequest(BaseModel):
    """Request body for updating a chapter outline."""

    stage_assignment: str | None = Field(default=None, max_length=50)
    planned_beats: list[BeatSchema] | None = None
    outline_notes: str | None = None


class OutlineResponse(BaseModel):
    """Full chapter outline with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    stage_assignment: str
    planned_beats: list[BeatSchema]
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
    confirmed: bool
