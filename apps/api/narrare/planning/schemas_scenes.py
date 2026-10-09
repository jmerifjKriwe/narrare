"""Scene plan schemas — aggregate CRUD + AI draft/refine wire shapes (PLAN-001).

Field-for-field per the binding spec §5.1/§5.2. ``SceneSchema`` doubles as
the save-payload item (whole-aggregate PUT) and the response item; the AI
proposal schemas (T7/T8 consumers) are defined here up front so the later
tasks only wire them.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Hybrid KB refs + presence
# ---------------------------------------------------------------------------


class SceneRefSchema(BaseModel):
    """Hybrid KB ref (AD-1 pattern) — ``id`` links to the KB entry, ``name``
    keeps display alive when the entry is dead. ``id=None`` = name-only ref."""

    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=300)


class ScenePresenceSchema(BaseModel):
    """One ``present_characters`` entry."""

    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=300)
    goal: str = ""


# ---------------------------------------------------------------------------
# Scene aggregate
# ---------------------------------------------------------------------------


class SceneSchema(BaseModel):
    """One scene in a chapter's scene plan."""

    id: uuid.UUID
    position: int = Field(ge=1)
    title: str = Field(default="", max_length=500)
    pov_character_ref: SceneRefSchema | None = None
    location_ref: SceneRefSchema | None = None
    present_characters: list[ScenePresenceSchema] = []
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = []
    status: Literal["planned", "in_progress", "complete"] = "planned"
    created_at: datetime
    updated_at: datetime


class ScenePlanAggregateResponse(BaseModel):
    """Whole-chapter aggregate — scenes ordered by position."""

    chapter_id: uuid.UUID
    scenes: list[SceneSchema]
    version_updated_at: datetime


class ScenePlanSaveRequest(BaseModel):
    """Whole-aggregate save payload — diff-synced server-side by scene id."""

    scenes: list[SceneSchema]


# ---------------------------------------------------------------------------
# AI draft / refine (defined now, wired by T7/T8) — spec §5.2
# ---------------------------------------------------------------------------


class SceneProposalSchema(BaseModel):
    """AI-generated scene proposal — ``SceneSchema`` minus identity/status/
    timestamps; the client assigns ids/positions and saves via the PUT."""

    title: str = Field(default="", max_length=500)
    pov_character_ref: SceneRefSchema | None = None
    location_ref: SceneRefSchema | None = None
    present_characters: list[ScenePresenceSchema] = []
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = []


class SceneDraftRequest(BaseModel):
    """Chapter-level AI draft request (all context is optional run input)."""

    structure_type: str = ""
    outline_notes: str = ""
    chapter_summary: str = ""
    neighbor_summaries: str = ""
    instruction: str = ""
    scene_count: int = 0  # 0 = model chooses (3-8 enforced by the agent)


class SceneDraftResponse(BaseModel):
    """AI chapter draft — empty proposals + ``ai_unavailable`` degrade HTTP 200."""

    proposals: list[SceneProposalSchema] = []
    ai_unavailable: bool = False


class SceneRefineRequest(BaseModel):
    """Single-scene AI refinement — full scene carried so unsaved drafts are
    refinable (stateless; zero DB writes)."""

    scene: SceneSchema
    prev_scene_summary: str = ""
    next_scene_summary: str = ""
    chapter_summary: str = ""
    instruction: str = ""


class SceneRefineResponse(BaseModel):
    """AI single-scene proposal — ``proposal=None`` + ``ai_unavailable`` degrade."""

    proposal: SceneProposalSchema | None = None
    ai_unavailable: bool = False
