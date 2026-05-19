"""Location entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional location
as recommended by the bundled location template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class LocationFeatures(BaseModel):
    """Geographic and architectural features."""

    model_config = ConfigDict(extra="allow")

    architecture: str | None = None
    natural_features: list[str] | None = None
    landmarks: list[str] | None = None
    atmosphere: str | None = None


class LocationInhabitants(BaseModel):
    """Inhabitants and population details."""

    model_config = ConfigDict(extra="allow")

    population: str | None = None
    species: list[str] | None = None
    factions: list[str] | None = None
    notable_residents: list[str] | None = None


class LocationHistory(BaseModel):
    """Historical context for the location."""

    model_config = ConfigDict(extra="allow")

    founded: str | None = None
    key_events: list[str] | None = None
    current_state: str | None = None


class LocationMetadata(KBEntryMetadata):
    """Metadata for location KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    location_type: str | None = None
    parent_location: str | None = None
    coordinates: str | None = None
    climate: str | None = None
    terrain: str | None = None
    size: str | None = None
    first_appearance: str | None = None
    # Nested groups
    features: LocationFeatures | None = None
    inhabitants: LocationInhabitants | None = None
    history: LocationHistory | None = None
