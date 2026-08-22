# apps/api/narrare/notes/schemas.py
"""Notes Pydantic schemas — request/response models (NOTES-001 §5)."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic model resolution
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from narrare_core.notes.types import (
    DEFAULT_NOTE_LIMITS,
    NoteType,
    validate_scope,
)


def _check_tag_lengths(value: list[str]) -> list[str]:
    max_tag_length = DEFAULT_NOTE_LIMITS.max_tag_length
    for tag in value:
        if len(tag) > max_tag_length:
            msg = f"Each tag must be at most {max_tag_length} characters"
            raise ValueError(msg)
    return value


class NoteCreateRequest(BaseModel):
    """Create a note — used by BOTH quick capture and the full editor (spec §5)."""

    title: str | None = Field(default=None, max_length=500)
    content: str = Field(default="", max_length=50_000)
    note_type: NoteType = NoteType.IDEA
    tags: list[str] = Field(default_factory=list, max_length=DEFAULT_NOTE_LIMITS.max_tags_per_note)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None

    @field_validator("tags")
    @classmethod
    def _tags_within_limit(cls, value: list[str]) -> list[str]:
        return _check_tag_lengths(value)

    @model_validator(mode="after")
    def _scope_not_both(self) -> NoteCreateRequest:
        validate_scope(self.novel_id, self.series_id)
        return self


class NoteUpdateRequest(BaseModel):
    """Partial update. Explicit ``null`` clears a field (exclude_unset semantics)."""

    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=50_000)
    note_type: NoteType | None = None
    tags: list[str] | None = Field(default=None, max_length=DEFAULT_NOTE_LIMITS.max_tags_per_note)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None

    @field_validator("tags")
    @classmethod
    def _tags_within_limit(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _check_tag_lengths(value)

    @model_validator(mode="after")
    def _scope_not_both(self) -> NoteUpdateRequest:
        validate_scope(self.novel_id, self.series_id)
        return self


class NoteResponse(BaseModel):
    """API representation of a note.

    ``title`` is the stored (possibly None) title — display fallback lives
    with the client (``noteDisplayTitle``) per spec §4.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    content: str
    note_type: str
    tags: list[str]
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class NoteTagsResponse(BaseModel):
    """Distinct existing tags for autocomplete (spec §5 GET /notes/tags)."""

    tags: list[str]


class NoteSearchRequest(BaseModel):
    """Semantic search body — same optional filters as the list endpoint (§6a)."""

    query: str = Field(min_length=1, max_length=500)
    note_type: NoteType | None = None
    tag: str | None = Field(default=None, max_length=32)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


class NoteSearchHit(NoteResponse):
    """A note plus its similarity score (None in lexical mode)."""

    similarity: float | None = None


class NoteSearchResponse(BaseModel):
    """Search result with an honest mode badge (RULE-11 spirit, §6a)."""

    mode: Literal["lexical", "semantic"]
    query: str
    results: list[NoteSearchHit]
