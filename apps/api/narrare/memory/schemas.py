"""Memory Pydantic schemas."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Closed-vocabulary literal for Pydantic schema validation (CR-AUFG-07-24).
# Pyright cannot narrow ``StrEnum_member.value`` to a literal string, so the
# member values are spelled out explicitly. This Literal MUST stay in sync
# with ``narrare_core.memory.source_types.FeedbackSourceType`` — enforced by
# tests/integration/memory/test_feedback_source_type_parity.py (Task 14).
_FeedbackSourceTypeLiteral = Literal[
    "co_author_change",
    "kb_field_suggest",
    "kb_enhance_field",
    "kb_improve_suggestion",
    "chat_message",
]


class FeedbackRequest(BaseModel):
    """Request body for recording user feedback on an AI suggestion.

    Identifier policy (CR-AUFG-07-24): callers MUST supply either a valid
    ``suggestion_id`` UUID (existing callers) OR a ``source_id`` +
    ``source_type`` pair (frontend canonical IDs). The backend derives a
    deterministic UUID from the pair (see ``suggestion_identity.py``) so the
    core layer and DB stay UUID-only.
    """

    action: str = Field(..., pattern="^(accept|reject|modify)$")
    suggestion_id: uuid.UUID | None = Field(
        default=None,
        description="Existing suggestion UUID. Mutually sufficient with source_id.",
    )
    intent: str = Field(..., min_length=1, max_length=50)
    source_type: _FeedbackSourceTypeLiteral | None = Field(
        default=None,
        description="Where the rated suggestion originated (CR-AUFG-07-24 taxonomy).",
    )
    source_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "Canonical frontend suggestion identifier (CR-AUFG-07-24). "
            "Requires source_type. Backend derives a UUID; raw value never "
            "reaches core or DB."
        ),
    )
    suggestion_text: str = Field(..., min_length=1)
    modification: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5, description="Optional 1-5 rating")
    context: dict[str, object] | None = None
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    genre: str | None = None
    mode: str | None = None

    @field_validator("source_id", mode="before")
    @classmethod
    def _strip_source_id(cls, value: object) -> object:
        """Trim surrounding whitespace before min/max length validation."""
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _require_identifier(self) -> FeedbackRequest:
        """Ensure exactly one identifier path is supplied and is complete.

        - ``suggestion_id`` alone is accepted (back-compat).
        - ``source_id`` alone is rejected; ``source_type`` is mandatory.
        - Neither identifier is rejected with a 422.
        """
        has_uuid = self.suggestion_id is not None
        has_source = self.source_id is not None  # min_length=1 rules out empty
        if not has_uuid and not has_source:
            raise ValueError("Either suggestion_id or (source_id with source_type) is required.")
        if has_source and self.source_type is None:
            raise ValueError("source_type is required when source_id is provided.")
        return self


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
