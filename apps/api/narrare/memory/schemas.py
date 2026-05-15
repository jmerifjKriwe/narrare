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
    context: dict[str, object] | None = None
    project_id: uuid.UUID


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
