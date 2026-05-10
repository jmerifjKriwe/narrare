"""Novel Pydantic schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class CreateNovelRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    language: str = Field(default="en", min_length=2, max_length=10)
    tone: str = Field(default="", max_length=100)
    story_structure: str = Field(default="three_act", max_length=100)
    logline: str = Field(default="", max_length=500)
    synopsis: str = Field(default="")


class UpdateNovelRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    tone: str | None = Field(default=None, max_length=100)
    story_structure: str | None = Field(default=None, max_length=100)
    logline: str | None = Field(default=None, max_length=500)
    synopsis: str | None = None


class NovelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: str
    genre: str
    language: str
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
    title: str
    author: str
    genre: str
    language: str
    is_demo: bool
    updated_at: datetime
