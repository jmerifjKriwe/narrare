"""Concept entity metadata schema.

A concept captures abstract worldbuilding elements like technology,
society, culture, magic rules, or philosophical ideas.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class ConceptDefinition(BaseModel):
    """Core definition and principles of the concept."""

    model_config = ConfigDict(extra="allow")

    category: str | None = None  # "technology", "society", "magic", "philosophy", etc.
    summary: str | None = None
    key_principles: list[str] | None = None
    rules: list[str] | None = None
    implications: str | None = None


class ConceptHistory(BaseModel):
    """Historical background of the concept."""

    model_config = ConfigDict(extra="allow")

    origin: str | None = None
    discovery: str | None = None
    key_figures: list[str] | None = None
    evolution: str | None = None


class ConceptMetadata(KBEntryMetadata):
    """Metadata for concept KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields for backward compat
    concept_type: str | None = None
    first_appearance: str | None = None
    # Nested groups
    definition: ConceptDefinition | None = None
    history: ConceptHistory | None = None
