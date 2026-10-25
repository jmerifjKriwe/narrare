"""Request and response shapes for the writing capability."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=80)
    blurb: str | None = None


class NovelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    genre: str | None
    blurb: str | None
    created_at: datetime
    updated_at: datetime


class ChapterCreate(BaseModel):
    # Empty is the honest default: the database stores no locale, the chapter
    # list shows the localized placeholder for an untitled chapter.
    title: str = Field(default="", max_length=200)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    title: str
    position: int
    body: str
    created_at: datetime
    updated_at: datetime
