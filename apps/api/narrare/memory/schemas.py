"""Memory Pydantic schemas."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class FeedbackRequest(BaseModel):
    """Request body for recording user feedback on an AI suggestion."""

    action: str = Field(..., pattern="^(accept|reject|modify)$")
    suggestion_id: uuid.UUID
    intent: str = Field(..., min_length=1, max_length=50)
    suggestion_text: str = Field(..., min_length=1)
    modification: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5, description="Optional 1-5 rating")
    context: dict[str, object] | None = None
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    genre: str | None = None
    mode: str | None = None


class FeedbackResponse(BaseModel):
    """Response body after successfully recording feedback."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    created_at: datetime


class PreferenceResponse(BaseModel):
    """Response body for aggregated user preferences."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    project_id: uuid.UUID
    event_count: int
    confidence: float
    style: dict[str, str]
    content: dict[str, str]
    constraints: list[str]
    last_updated: datetime


class ResetResponse(BaseModel):
    """Response body after resetting user preferences."""

    message: str
    deleted_count: int


class AnalyzeRequest(BaseModel):
    """Request body for triggering preference analysis."""

    project_id: uuid.UUID


class AnalyzeResponse(BaseModel):
    """Response body after preference analysis completes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    confidence: float
    summary: str
    style_patterns: list[str]
    content_patterns: list[str]
    avoidance_patterns: list[str]
    event_count_at_analysis: int
    created_at: datetime
    updated_at: datetime
