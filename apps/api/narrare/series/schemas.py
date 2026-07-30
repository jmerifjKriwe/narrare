"""Pydantic request/response schemas for the Series API.

Consumes ``SeriesStatus`` from Core (Task 1.1). Used by the router
(Task 3.6) and the frontend (Slice 4). Join-flow types expose the
per-entry treatment so the UI can show "what would happen" before apply.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.series.schemas import (
    SeriesStatus,  # noqa: TC001 - needed at runtime for Pydantic model resolution
)


class SeriesCreateRequest(BaseModel):
    """POST /api/v1/series body."""

    title: str
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus | None = None  # service defaults to "draft"
    planned_novel_count: int | None = None


class SeriesUpdateRequest(BaseModel):
    """PATCH /api/v1/series/{id} body. All fields optional."""

    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus | None = None
    planned_novel_count: int | None = None


class SeriesResponse(BaseModel):
    """Response for single Series GET/POST/PATCH."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    subtitle: str | None
    description: str | None
    genre: str | None
    writing_language: str | None
    status: SeriesStatus
    planned_novel_count: int | None
    novel_count: int = 0  # computed; not stored on Series


class SeriesSummary(BaseModel):
    """List item: lighter than SeriesResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subtitle: str | None
    status: SeriesStatus
    novel_count: int = 0


class SeriesSettingsResponse(BaseModel):
    """Response for GET /api/v1/series/{id}/settings."""

    model_config = ConfigDict(from_attributes=True)

    series_id: uuid.UUID
    author_voice: dict[str, object] | None


class SeriesSettingsUpdateRequest(BaseModel):
    """PATCH /api/v1/series/{id}/settings body. Spec 1: usually null."""

    author_voice: dict[str, object] | None = None


class ReorderNovelsRequest(BaseModel):
    """PATCH /api/v1/series/{id}/novels/reorder body — full ordered id list.

    The caller supplies every novel id of the series in the desired order;
    the service reassigns sequential 1-based ``series_position`` values.
    """

    novel_ids: list[uuid.UUID]


# --- Join Flow types ---------------------------------------------------------


class JoinEntryTreatment(BaseModel):
    """Per-entry decision in a JoinPreview: what would happen to this entry."""

    entry_id: uuid.UUID
    slug: str
    entity_type: str
    current_scope: Literal["novel"]  # before join, all entries are novel-scoped
    target_scope: Literal["series", "novel"]  # after join + apply
    reason: str  # human-readable explanation


class JoinPreview(BaseModel):
    """Result of POST /api/v1/series/{id}/novels (preview step).

    Lists every KB entry of the joining novel + how it would be treated
    on apply (promoted to Canon or kept as Overlay) based on Policy alpha.
    """

    series_id: uuid.UUID
    novel_id: uuid.UUID
    canon_empty: bool  # True -> heuristics apply; False -> all stay Overlay
    treatments: list[JoinEntryTreatment]


class JoinResult(BaseModel):
    """Result of POST /api/v1/series/{id}/novels/{novel_id}/apply."""

    series_id: uuid.UUID
    novel_id: uuid.UUID
    position: int
    promoted_to_canon: int  # 0 if canon was non-empty
    kept_as_overlay: int


# --- Join Flow request bodies -----------------------------------------------


class JoinPreviewRequest(BaseModel):
    """POST /api/v1/series/{id}/novels body — the novel to preview joining."""

    novel_id: uuid.UUID


class JoinApplyRequest(BaseModel):
    """POST /api/v1/series/{id}/novels/{novel_id}/apply body.

    ``position`` is the 1-based slot the novel takes within the series.
    """

    position: int = Field(ge=1)
