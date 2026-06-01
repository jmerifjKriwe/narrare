"""Timeline event CRUD schemas — request/response models for PLAN-004.

These schemas are for the persistent timeline event CRUD API.
The existing ``TimelineEventResponse`` and ``TimelineResponse`` in
``schemas.py`` are for the AI analysis endpoint and remain unchanged.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


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
