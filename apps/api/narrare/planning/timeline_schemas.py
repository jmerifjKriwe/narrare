"""Timeline event CRUD schemas — request/response models for PLAN-004.

These schemas are for the persistent timeline event CRUD API.
The existing ``TimelineEventResponse`` and ``TimelineResponse`` in
``schemas.py`` are for the AI analysis endpoint and remain unchanged.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from narrare_core.agents.temporal_extraction_types import (
        ExtractedTemporalExpression,
    )


class TimelineEventCreateRequest(BaseModel):
    """Request body for creating a timeline event."""

    event_name: str = Field(min_length=1, max_length=500)
    description: str = ""
    event_type: str = "plot_point"
    timestamp_raw: str = ""
    timestamp_normalized: str = ""
    temporal_order: int | None = None
    chapter_id: uuid.UUID | None = None
    character_refs: list[dict[str, str]] = []  # [{"id": "uuid", "name": "John"}]
    location_ref: dict[str, str] | None = None  # {"id": "uuid", "name": "Castle"}
    causes: str = ""
    consequences: str = ""


class TimelineEventUpdateRequest(BaseModel):
    """Request body for updating a timeline event.

    All fields are optional — only provided fields are updated.
    """

    event_name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    event_type: str | None = None
    timestamp_raw: str | None = None
    timestamp_normalized: str | None = None
    temporal_order: int | None = None
    chapter_id: uuid.UUID | None = None
    character_refs: list[dict[str, str]] | None = None
    location_ref: dict[str, str] | None = None
    causes: str | None = None
    consequences: str | None = None


class TimelineEventCRUDResponse(BaseModel):
    """Response for a single persistent timeline event.

    Named ``TimelineEventCRUDResponse`` to avoid collision with the
    AI-analysis ``TimelineEventResponse`` in ``schemas.py``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    event_name: str
    description: str
    event_type: str
    timestamp_raw: str
    timestamp_normalized: str
    temporal_order: int | None
    chapter_id: uuid.UUID | None
    character_refs: list[dict[str, object]]
    location_ref: dict[str, object] | None
    causes: str
    consequences: str
    source: str
    confidence: float | None
    is_confirmed: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Phase 2 schemas — extraction and consistency (PLAN-004)
# ---------------------------------------------------------------------------


class TemporalIssueResponse(BaseModel):
    """A single temporal consistency issue."""

    severity: str  # "error" | "warning" | "info"
    rule_id: str
    event_ids: list[str]
    description: str
    suggestion: str
    source: str  # "deterministic" | "llm"


class TemporalConsistencyResponse(BaseModel):
    """Response from temporal consistency check."""

    issues: list[TemporalIssueResponse]
    deterministic_pass: bool
    overall_assessment: str


class ExtractedEventResponse(BaseModel):
    """A single extracted temporal expression, pending user review."""

    id: str  # Temporary ID for tracking
    expression: str
    event_name: str
    timestamp_raw: str
    chapter_reference: str
    character_names: list[str]
    location_name: str
    confidence: float
    context: str


class ExtractionRequest(BaseModel):
    """Request to extract temporal expressions from chapters."""

    chapter_ids: list[uuid.UUID] = []  # If empty, extract from all chapters


class ConfirmExtractionRequest(BaseModel):
    """Request to confirm an extracted temporal expression as a timeline event."""

    expression: str = ""
    event_name: str = ""
    timestamp_raw: str = ""
    chapter_reference: str = ""
    character_names: list[str] = []
    location_name: str = ""
    confidence: float = 0.0
    context: str = ""

    def to_extracted_expression(self) -> ExtractedTemporalExpression:
        """Convert this request to an ExtractedTemporalExpression for service consumption.

        Uses lazy import to avoid circular dependency on core types.
        """
        from narrare_core.agents.temporal_extraction_types import (
            ExtractedTemporalExpression as _ExtractedTemporalExpression,
        )

        return _ExtractedTemporalExpression(
            expression=self.expression,
            event_name=self.event_name,
            timestamp_raw=self.timestamp_raw,
            chapter_reference=self.chapter_reference,
            character_names=self.character_names,
            location_name=self.location_name,
            confidence=self.confidence,
            context=self.context,
        )


# ---------------------------------------------------------------------------
# Phase 3 schemas — character ages (PLAN-004)
# ---------------------------------------------------------------------------


class CharacterAgeInfo(BaseModel):
    """Age info for a single character."""

    character_name: str
    character_id: str | None = None
    birth_date: str | None = None
    birth_date_narrative: str | None = None
    age_available: bool = False


class CharacterAgeReport(BaseModel):
    """Report on character ages from KB metadata."""

    characters: list[CharacterAgeInfo]
    characters_with_age: int
    characters_without_age: int
