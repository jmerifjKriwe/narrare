"""Core Pydantic schemas for Series and SeriesSettings (pure, no HTTP/DB)."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic model resolution
from typing import Literal
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict

SeriesStatus = Literal["draft", "active", "completed"]


class Series(BaseModel):
    """A series/reihe — groups multiple novels with shared Canon KB."""

    model_config = ConfigDict(extra="allow")

    id: UUID
    user_id: UUID
    title: str
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus = "draft"
    planned_novel_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SeriesSettings(BaseModel):
    """1:1 settings for a Series. author_voice empty in Spec 1 (Spec 3 fills)."""

    model_config = ConfigDict(extra="allow")

    series_id: UUID
    author_voice: dict[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
