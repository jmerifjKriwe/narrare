"""Wiki Pydantic schemas.

Request/response models for Wiki summary endpoints.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Entity Wiki Summary
# ---------------------------------------------------------------------------


class WikiSummaryResponse(BaseModel):
    """Full wiki summary for a single KB entity."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    entity_id: uuid.UUID
    # M11: display name from the KB entry (None when the entry is gone).
    entity_name: str | None = None
    narrative_summary: str
    role_in_story: str | None
    key_attributes: list[str] | None
    relationships: list[dict[str, Any]] | None
    chapter_references: list[dict[str, Any]] | None
    character_arc: str | None
    status: str
    version: int
    generated_at: datetime | None
    refreshed_at: datetime | None


# ---------------------------------------------------------------------------
# Chapter Wiki Summary
# ---------------------------------------------------------------------------


class WikiChapterSummaryResponse(BaseModel):
    """Chapter-level wiki summary."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    narrative_summary: str
    key_events: list[str] | None
    entities_involved: list[dict[str, Any]] | None
    themes: list[str] | None
    emotional_arc: str | None
    status: str
    version: int
    generated_at: datetime | None = Field(
        validation_alias="created_at",
        default=None,
    )


# ---------------------------------------------------------------------------
# Paginated List
# ---------------------------------------------------------------------------


class WikiSummaryListResponse(BaseModel):
    """Paginated list of wiki summaries."""

    items: list[WikiSummaryResponse]
    total: int


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class WikiRefreshRequest(BaseModel):
    """Manual refresh trigger for wiki summaries.

    If entity_id is omitted, all stale summaries for the novel are refreshed.
    Set force=True to refresh even FRESH summaries.
    """

    entity_id: uuid.UUID | None = Field(
        default=None,
        description="Target entity; omit to refresh all stale summaries.",
    )
    force: bool = Field(
        default=False,
        description="Force refresh even if status is FRESH.",
    )


class WikiRefreshResponse(BaseModel):
    """Result of a wiki summary refresh operation."""

    summary_id: uuid.UUID | None = None
    status: str
    message: str


# ---------------------------------------------------------------------------
# Wiki Index
# ---------------------------------------------------------------------------


class WikiIndexResponse(BaseModel):
    """Karpathy-inspired wiki index metadata for the overview page."""

    novel_id: uuid.UUID
    total_summaries: int
    fresh_count: int
    stale_count: int
    pending_count: int
    last_generated_at: datetime | None = None
