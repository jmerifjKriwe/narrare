"""Custom tone schemas for settings.

Extracted from schemas.py per RULE-04 (file size limit 200 lines).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CustomTone(BaseModel):
    """A user-defined writing tone."""

    id: str = Field(description="Unique tone identifier (UUID)")
    name: str = Field(min_length=1, max_length=50, description="Display name")
    instructions: str = Field(
        min_length=1, max_length=500, description="Tone instructions for the LLM"
    )


class CustomToneCreate(BaseModel):
    """Request to create a new custom tone."""

    name: str = Field(min_length=1, max_length=50, description="Display name")
    instructions: str = Field(
        min_length=1, max_length=500, description="Tone instructions for the LLM"
    )


class CustomToneUpdate(BaseModel):
    """Request to update an existing custom tone."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    instructions: str | None = Field(default=None, min_length=1, max_length=500)
