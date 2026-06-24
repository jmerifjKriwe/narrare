"""Prompts Pydantic schemas — maps core dataclasses to API responses.

Includes PROMPT-003 (CR-AUFG-07-16) schemas for the provider-free preview,
reset-with-metadata, and optional live-test endpoints. All new models use
Pydantic v2 with ``from_attributes=True`` so Core dataclasses can be mapped
via ``model_validate``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptInfoResponse(BaseModel):
    """Metadata summary for a single prompt."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str = Field(..., description="Prompt ID: {category}/{language}/{mode}")
    name: str
    category: str
    language: str
    source: str
    has_override: bool
    prompt_version: str


class PromptDetailResponse(BaseModel):
    """Full prompt content with metadata and variable info."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
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
    """Request body for saving a prompt override.

    ``change_reason`` is optional metadata forwarded to the prompt history
    record (CR-AUFG-07-19).  It is ignored when prompt history is disabled.
    """

    content: str = Field(..., min_length=1, description="Override prompt content")
    change_reason: str | None = Field(
        default=None,
        max_length=200,
        description="Optional human-readable reason recorded with the revision.",
    )


# PROMPT-003 (CR-AUFG-07-16) preview / reset / live-test schemas live in
# ``schemas_prompt_ux.py`` (split per RULE-04).  CR-AUFG-07-19 Prompt History
# schemas live in ``schemas_prompt_history.py``.
