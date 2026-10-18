"""Knowledge Base reference-resolution schemas (@Name mention resolution).

Split from ``schemas.py`` per RULE-04 (second 200-line warning on that
file): the @Name-reference family is a self-contained feature — it shares
no model with the entry, relationship, search, or suggestion families.
Re-exported from ``schemas.py`` so all existing import paths stay
byte-compatible.
"""

from __future__ import annotations

from pydantic import BaseModel


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
