"""Volume schemas, contracts, repository, service, and router."""

# ---- schemas.py content ----
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class CreateVolumeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class UpdateVolumeRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)


class VolumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    novel_id: uuid.UUID
    title: str
    position: int
    created_at: datetime
