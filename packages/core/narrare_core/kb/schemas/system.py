"""System entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional system
(e.g. magic system, technology) as recommended by the bundled
system template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class SystemMechanics(BaseModel):
    """Rules and mechanics of the system."""

    model_config = ConfigDict(extra="allow")

    rules: list[str] | None = None
    cost: str | None = None
    limitations: list[str] | None = None
    levels: list[str] | None = None


class SystemPractitioners(BaseModel):
    """Practitioners and users of the system."""

    model_config = ConfigDict(extra="allow")

    users: list[str] | None = None
    requirements: str | None = None
    training: str | None = None
    organizations: list[str] | None = None


class SystemOrigins(BaseModel):
    """Origin and discovery of the system."""

    model_config = ConfigDict(extra="allow")

    source: str | None = None
    discovered_by: str | None = None
    discovered_date: str | None = None
    history: str | None = None


class SystemMetadata(KBEntryMetadata):
    """Metadata for system KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    system_type: str | None = None
    practitioners: list[str] | None = None
    first_appearance: str | None = None
    # Nested groups
    mechanics: SystemMechanics | None = None
    practitioner_details: SystemPractitioners | None = None
    origins: SystemOrigins | None = None
