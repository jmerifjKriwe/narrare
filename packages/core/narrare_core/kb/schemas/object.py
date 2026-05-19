"""Object entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional object
as recommended by the bundled object template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class ObjectProperties(BaseModel):
    """Physical properties of the object."""

    model_config = ConfigDict(extra="allow")

    material: str | None = None
    dimensions: str | None = None
    weight: str | None = None
    condition: str | None = None
    appearance: str | None = None


class ObjectOrigin(BaseModel):
    """Origin and creation details."""

    model_config = ConfigDict(extra="allow")

    creator: str | None = None
    created_date: str | None = None
    place_of_origin: str | None = None
    method_of_creation: str | None = None


class ObjectSignificance(BaseModel):
    """Significance and role in the story."""

    model_config = ConfigDict(extra="allow")

    purpose: str | None = None
    powers: list[str] | None = None
    historical_significance: str | None = None
    current_location: str | None = None


class ObjectMetadata(KBEntryMetadata):
    """Metadata for object KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    object_type: str | None = None
    owner: str | None = None
    origin: str | None = None
    first_appearance: str | None = None
    # Nested groups
    properties: ObjectProperties | None = None
    origin_details: ObjectOrigin | None = None
    significance: ObjectSignificance | None = None
