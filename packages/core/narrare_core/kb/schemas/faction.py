"""Faction entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional faction
as recommended by the bundled faction template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class FactionStructure(BaseModel):
    """Organisational structure of the faction."""

    model_config = ConfigDict(extra="allow")

    leadership: str | None = None
    hierarchy: str | None = None
    membership_count: str | None = None
    headquarters: str | None = None


class FactionIdeology(BaseModel):
    """Beliefs and ideological stance."""

    model_config = ConfigDict(extra="allow")

    beliefs: list[str] | None = None
    goals: list[str] | None = None
    methods: str | None = None
    taboos: list[str] | None = None


class FactionHistory(BaseModel):
    """Historical background of the faction."""

    model_config = ConfigDict(extra="allow")

    founded: str | None = None
    key_events: list[str] | None = None
    current_status: str | None = None


class FactionMetadata(KBEntryMetadata):
    """Metadata for faction KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    founded: str | None = None
    members: list[str] | None = None
    ideology: str | None = None
    first_appearance: str | None = None
    # Nested groups
    structure: FactionStructure | None = None
    belief_system: FactionIdeology | None = None
    history: FactionHistory | None = None
