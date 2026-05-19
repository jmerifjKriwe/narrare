"""Timeline entity metadata schema.

Fields capture the essential attributes of a fictional timeline
or historical period as recommended by the bundled timeline template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class TimelineMetadata(KBEntryMetadata):
    """Metadata for timeline KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    era: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    first_appearance: str | None = None
