"""Location entity metadata schema.

Fields capture the essential attributes of a fictional location
as recommended by the bundled location template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class LocationMetadata(KBEntryMetadata):
    """Metadata for location KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    location_type: str | None = None
    parent_location: str | None = None
    coordinates: str | None = None
    climate: str | None = None
    terrain: str | None = None
    size: str | None = None
    first_appearance: str | None = None
