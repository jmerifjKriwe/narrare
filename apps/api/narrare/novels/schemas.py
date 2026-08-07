"""Novel Pydantic schemas."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class CreateNovelRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    writing_language: str = Field(default="en", max_length=100)
    tone: str = Field(default="", max_length=100)
    story_structure: str = Field(default="three_act", max_length=100)
    logline: str = Field(default="", max_length=500)
    synopsis: str = Field(default="")


class UpdateNovelRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    writing_language: str | None = Field(default=None, max_length=100)
    tone: str | None = Field(default=None, max_length=100)
    story_structure: str | None = Field(default=None, max_length=100)
    logline: str | None = Field(default=None, max_length=500)
    synopsis: str | None = None


class NovelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Series membership (Spec 1, ADR-075). None = standalone novel.
    # Mapped automatically via from_attributes=True from the Novel ORM column.
    series_id: uuid.UUID | None = None
    title: str
    author: str
    genre: str
    writing_language: str
    tone: str
    story_structure: str
    logline: str
    synopsis: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class NovelSummaryResponse(BaseModel):
    """Compact novel representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Series membership, surfaced for list views (incl. the series novels list).
    # None = standalone novel. Mapped automatically via from_attributes=True.
    series_id: uuid.UUID | None = None
    # 1-based position within the series; None for standalone novels. Surfaced
    # so list views (e.g. BändeList) can render the band number without an extra
    # fetch. Auto-mapped from the Novel ORM column via from_attributes=True.
    series_position: int | None = None
    title: str
    author: str
    genre: str
    writing_language: str
    is_demo: bool
    updated_at: datetime
