"""Faction entity metadata schema.

Fields capture the essential attributes of a fictional faction
as recommended by the bundled faction template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class FactionMetadata(KBEntryMetadata):
    """Metadata for faction KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    founded: str | None = None
    members: list[str] | None = None
    ideology: str | None = None
    first_appearance: str | None = None
