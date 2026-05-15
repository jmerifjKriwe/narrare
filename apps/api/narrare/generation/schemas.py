"""Generation Pydantic schemas — request/response models for name generation."""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class NameType(StrEnum):
    """Types of names that can be generated."""

    CHARACTER = "character"
    PLACE = "place"
    ORGANIZATION = "organization"
    ITEM = "item"


class GenderEnum(StrEnum):
    """Gender filters for name generation."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    ANY = "any"


class NameGenerateRequest(BaseModel):
    """Request body for name generation."""

    project_id: uuid.UUID
    name_type: NameType = NameType.CHARACTER
    culture: str = Field(default="fantasy", min_length=1, max_length=50)
    count: int = Field(default=10, ge=1, le=50)
    gender: GenderEnum = GenderEnum.ANY
    language: str = Field(default="en", min_length=2, max_length=5)


class GeneratedName(BaseModel):
    """A single generated name with metadata."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    pronunciation: str | None = None
    meaning: str | None = None
    type: str
    culture: str
    is_duplicate: bool = False
    confidence: float = 1.0


class NameGenerateResponse(BaseModel):
    """Response body for name generation."""

    model_config = ConfigDict(from_attributes=True)

    names: list[GeneratedName]
    count: int
    culture: str
    name_type: str
