"""Writing module Pydantic schemas — request/response models."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class GenerationModeEnum(StrEnum):
    """Supported generation modes."""

    FULL_DRAFT = "full_draft"
    SCENE_BY_SCENE = "scene_by_scene"
    INTERVIEW_ASSISTED = "interview_assisted"
    INTERACTIVE_SESSION = "interactive_session"


class GenerationStatusEnum(StrEnum):
    """Generation request lifecycle states."""

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class GenerateRequest(BaseModel):
    """Start a chapter generation."""

    mode: GenerationModeEnum
    outline: str | None = None
    prompt: str | None = None
    auto_continue: bool = False
    word_target: int | None = Field(None, ge=100, le=50000)
    tone: str = Field("balanced", min_length=1, max_length=100)
    language: str = Field("en", min_length=2, max_length=5)


class GenerateResponse(BaseModel):
    """Response after starting generation."""

    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    status: str
    mode: str


class GenerationStatusResponse(BaseModel):
    """Generation request status."""

    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    status: str
    mode: str
    word_count: int
    tokens_used: int
    model_id: str | None
    provider_name: str | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class StopResponse(BaseModel):
    """Response after stopping generation."""

    request_id: uuid.UUID
    status: str = "stopped"
    word_count: int


class AcceptResponse(BaseModel):
    """Response after accepting draft."""

    request_id: uuid.UUID
    chapter_id: uuid.UUID
    word_count: int


class RejectResponse(BaseModel):
    """Response after rejecting draft."""

    request_id: uuid.UUID
    status: str = "rejected"


class SceneAcceptRequest(BaseModel):
    """Accept a scene in scene-by-scene mode."""

    scene_text: str | None = None


class SceneNextResponse(BaseModel):
    """Response for next scene generation."""

    request_id: uuid.UUID
    scene_number: int
    status: str


class GenerationStatsResponse(BaseModel):
    """Aggregated generation statistics."""

    total_generations: int
    success_rate: float
    avg_tokens: float
    avg_word_count: float
    most_used_model: str | None


class InlineSuggestRequest(BaseModel):
    """Request for an inline ghost text suggestion.

    Sent when the user pauses typing.  Contains the text before and
    optionally after the cursor.  The backend returns a short (1-3
    sentence) completion streamed via SSE.
    """

    text_before: str = Field(
        ...,
        max_length=5000,
        description="Text before cursor position — used as the prompt for completion",
    )
    text_after: str | None = Field(
        default=None,
        max_length=1000,
        description="Text after cursor (if any) — provides forward context",
    )


class InlineSuggestResponse(BaseModel):
    """One chunk of an inline suggestion SSE stream."""

    text: str
    is_final: bool = False
