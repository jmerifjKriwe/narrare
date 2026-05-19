"""Knowledge Base Pydantic schemas.

Request/response models for KB entry and relationship endpoints.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# KB Entry
# ---------------------------------------------------------------------------


class KBEntryCreate(BaseModel):
    """Request body for creating a new KB entry."""

    entity_type: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=500)
    slug: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", max_length=20)
    tags: list[str] | None = Field(default=None)
    metadata: dict[str, object] | None = Field(default=None)
    body: str | None = Field(default=None)
    template_version: str | None = Field(default=None, max_length=20)


class KBEntryUpdate(BaseModel):
    """Request body for updating an existing KB entry.

    All fields are optional — only provided fields are changed.
    """

    name: str | None = Field(default=None, min_length=1, max_length=500)
    slug: str | None = Field(default=None, max_length=500)
    entity_type: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, max_length=20)
    tags: list[str] | None = Field(default=None)
    metadata: dict[str, object] | None = Field(default=None)
    body: str | None = Field(default=None)
    template_version: str | None = Field(default=None, max_length=20)


class KBEntryResponse(BaseModel):
    """Full KB entry representation."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    novel_id: uuid.UUID
    entity_type: str
    name: str
    slug: str
    status: str
    tags: list[str] | None
    metadata: dict[str, object] | None = Field(
        validation_alias="metadata_",
        default=None,
    )
    body: str | None
    template_version: str | None
    embeddings_dirty: bool
    created_at: datetime
    updated_at: datetime


class KBEntryListResponse(BaseModel):
    """Paginated list of KB entries."""

    items: list[KBEntryResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# KB Relationship
# ---------------------------------------------------------------------------


class KBRelationshipCreate(BaseModel):
    """Request body for creating a new KB relationship."""

    source_id: uuid.UUID
    target_id: uuid.UUID
    rel_type: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    direction: str = Field(default="directed", max_length=10)
    metadata: dict[str, object] | None = Field(default=None)


class KBRelationshipResponse(BaseModel):
    """Full KB relationship representation with entry names."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    rel_type: str
    label: str | None
    direction: str
    metadata: dict[str, object] | None = Field(
        validation_alias="metadata_",
        default=None,
    )
    created_at: datetime
    updated_at: datetime
    # Enriched names for display
    source_name: str | None = None
    target_name: str | None = None


# ---------------------------------------------------------------------------
# Reference Resolution
# ---------------------------------------------------------------------------


class ReferenceResolution(BaseModel):
    """A single resolved @Name reference in KB body text."""

    mention: str
    """The text after @ (e.g. "Anna Müller")."""

    entry_id: str | None = None
    """Resolved entry ID if found in the novel's KB."""

    entry_name: str | None = None
    """Resolved entry name."""

    entity_type: str | None = None
    """Entity type if found (character, location, etc.)."""

    slug: str | None = None
    """Slug for link generation."""


class ResolveReferencesRequest(BaseModel):
    """Request to resolve @Name mentions in text."""

    text: str


class ResolveReferencesResponse(BaseModel):
    """Response with resolved @Name references."""

    resolved: list[ReferenceResolution]
    html: str | None = None
    """Text with @mentions replaced by HTML anchor tags."""


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class KBSearchRequest(BaseModel):
    """Query parameters for KB entry search."""

    q: str | None = Field(default=None, min_length=1)
    entity_type: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = Field(default=None)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
