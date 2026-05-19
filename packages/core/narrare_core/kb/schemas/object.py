"""Object entity metadata schema.

Fields capture the essential attributes of a fictional object
as recommended by the bundled object template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class ObjectMetadata(KBEntryMetadata):
    """Metadata for object KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    object_type: str | None = None
    owner: str | None = None
    origin: str | None = None
    first_appearance: str | None = None
