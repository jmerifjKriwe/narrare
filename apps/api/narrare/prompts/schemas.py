"""Prompts Pydantic schemas — maps core dataclasses to API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptInfoResponse(BaseModel):
    """Metadata summary for a single prompt."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Prompt ID: {category}/{language}/{mode}")
    name: str
    category: str
    language: str
    source: str
    has_override: bool
    prompt_version: str


class PromptDetailResponse(BaseModel):
    """Full prompt content with metadata and variable info."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    content: str
    base_content: str
    source: str
    is_overridden: bool
    variables: list[str]
    metadata: dict[str, Any]


class CascadePathResponse(BaseModel):
    """A single level in the prompt cascade."""

    model_config = ConfigDict(from_attributes=True)

    level: str
    path: str
    exists: bool


class UpdateInfoResponse(BaseModel):
    """Information about a prompt with available bundled updates."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    override_version: str
    current_bundled_version: str


class DiffResponse(BaseModel):
    """Side-by-side content for diff comparison."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    override_content: str
    bundled_content: str


class SaveOverrideRequest(BaseModel):
    """Request body for saving a prompt override."""

    content: str = Field(..., min_length=1, description="Override prompt content")
