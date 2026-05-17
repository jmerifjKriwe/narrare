"""Chapter Pydantic schemas."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class CreateChapterRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="")
    position: int | None = None  # If None, appended at end
    volume_id: uuid.UUID | None = None


class UpdateChapterContentRequest(BaseModel):
    content: str
    word_count: int | None = None  # Client can provide; server recomputes if None


class UpdateChapterMetaRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(draft|reviewed|final)$")
    pov_character_id: str | None = Field(default=None, max_length=100)
    timeline_position: str | None = Field(default=None, max_length=200)
    volume_id: uuid.UUID | None = None


class ReorderChaptersRequest(BaseModel):
    """Batch reorder — provide full ordered list of chapter IDs."""

    chapter_ids: list[uuid.UUID]


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    volume_id: uuid.UUID | None
    title: str
    content: str
    summary: str
    position: int
    word_count: int
    status: str
    pov_character_id: str
    timeline_position: str
    created_at: datetime
    updated_at: datetime


class ChapterSummaryResponse(BaseModel):
    """Compact chapter for sidebar list — no content body."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    volume_id: uuid.UUID | None
    title: str
    position: int
    word_count: int
    status: str
    updated_at: datetime


class ChapterVersionResponse(BaseModel):
    """Single historical version of chapter content."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    word_count: int
    version_number: int
    source: str
    created_at: datetime


class ChapterVersionListResponse(BaseModel):
    """Paginated list of chapter versions."""

    versions: list[ChapterVersionResponse]
    total: int
