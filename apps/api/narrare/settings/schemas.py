"""Settings Pydantic schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    display_name: str
    ui_language: str
    theme: str
    updated_at: datetime


class UpdateUserSettingsRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    ui_language: str | None = Field(default=None, min_length=2, max_length=10)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")


class ProjectSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    novel_id: uuid.UUID
    autosave_interval: int
    default_language: str
    ai_provider: str
    ai_model: str
    model_overrides: str
    updated_at: datetime


class UpdateProjectSettingsRequest(BaseModel):
    autosave_interval: int | None = Field(default=None, ge=0, le=3600)
    default_language: str | None = Field(default=None, min_length=2, max_length=10)
    ai_provider: str | None = Field(default=None, max_length=50)
    ai_model: str | None = Field(default=None, max_length=200)
    model_overrides: str | None = None  # JSON string
