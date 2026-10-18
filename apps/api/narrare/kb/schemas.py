"""Knowledge Base Pydantic schemas: request/response models for entry/relationship endpoints."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# Re-export (RULE-04 split): the @Name reference-resolution family lives
# in schemas_references.py; re-exported so every existing
# ``from narrare.kb.schemas import ...`` path stays byte-compatible.
from narrare.kb.schemas_references import (
    ReferenceResolution as ReferenceResolution,
)
from narrare.kb.schemas_references import (
    ResolveReferencesRequest as ResolveReferencesRequest,
)
from narrare.kb.schemas_references import (
    ResolveReferencesResponse as ResolveReferencesResponse,
)

# ---------------------------------------------------------------------------
# KB Entry
# ---------------------------------------------------------------------------


class KBEntryCreate(BaseModel):
    """Request body for creating a new KB entry."""

    entity_type: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=500)
    slug: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", max_length=20)
    # Omitted tags default to [] — sessions and extraction have no tag
    # concept, so the empty list is the honest value. Same centralized
    # seam pattern as metadata below (T7): every KBEntryCreate caller
    # (session mapper, extraction apply, REST omission) gets [] instead
    # of persisting null, which crashed the FE list (F10, 2026-10-17).
    # Explicit null stays legal (None) — legacy-null reads are guarded
    # in the FE (KBEntryList / KBEntryDetail).
    tags: list[str] | None = Field(default_factory=list)
    # Omitted metadata defaults to {} — the create seams (novel + canon)
    # must never persist None, which lands as jsonb null and crashes the
    # FE detail view. Explicit null stays legal (None) so the services'
    # explicit-null coercion remains the guard for programmatic clients.
    metadata: dict[str, object] | None = Field(default_factory=dict)
    body: str | None = Field(default=None)
    template_version: str | None = Field(default=None, max_length=20)
    source: str = Field(default="manual", max_length=50)
    review_status: str = Field(default="approved", max_length=20)


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
    source: str
    review_status: str
    embeddings_dirty: bool
    created_at: datetime
    updated_at: datetime


class KBEntryListResponse(BaseModel):
    """Paginated list of KB entries."""

    items: list[KBEntryResponse]
    total: int
    page: int
    page_size: int


class KBDemoteRequest(BaseModel):
    """Request body for demoting a Series-Canon entry to a Novel-Overlay.

    ``series_id`` identifies the canon's series; the target novel comes from the
    request PATH (``/novels/{novel_id}/.../demote``), mirroring the promote
    endpoint — so the body carries no target id that could disagree with the path.
    """

    series_id: uuid.UUID


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
    source_name: str | None = None
    target_name: str | None = None


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


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


class KBSuggestionResponse(BaseModel):
    """Response model for a single KB suggestion."""

    entry_id: uuid.UUID
    entry_type: str
    name: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    reason: str
    similarity: float = Field(ge=0.0, le=1.0)
    usage_count: int = Field(ge=0)
    last_referenced_at: datetime | None = None
