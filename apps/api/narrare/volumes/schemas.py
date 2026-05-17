"""Volume Pydantic schemas."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class CreateVolumeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = None
    description: str | None = None
    word_count_target: int | None = Field(default=None, ge=0)


class UpdateVolumeRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    description: str | None = None
    word_count_target: int | None = Field(default=None, ge=0)


class ReorderVolumesRequest(BaseModel):
    """Batch reorder — provide full ordered list of volume IDs."""

    volume_ids: list[uuid.UUID]


class VolumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    title: str
    subtitle: str | None
    description: str | None
    word_count_target: int | None
    is_default: bool
    position: int
    created_at: datetime


class VolumeStatsResponse(BaseModel):
    """Aggregated stats for a single volume."""

    word_count: int
    chapter_count: int
    word_count_target: int | None
    completion_percentage: float | None
