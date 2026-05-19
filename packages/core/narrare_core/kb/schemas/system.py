"""System entity metadata schema.

Fields capture the essential attributes of a fictional system
(e.g. magic system, technology) as recommended by the bundled
system template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class SystemMetadata(KBEntryMetadata):
    """Metadata for system KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    system_type: str | None = None
    practitioners: list[str] | None = None
    first_appearance: str | None = None
