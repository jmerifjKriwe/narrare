"""Character entity metadata schema.

Fields capture the essential attributes of a fictional character
as recommended by the bundled character template.
"""

from __future__ import annotations

from .base import KBEntryMetadata


class CharacterMetadata(KBEntryMetadata):
    """Metadata for character KB entries.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    age: int | None = None
    role: str | None = None
    arc: str | None = None
    gender: str | None = None
    pronouns: str | None = None
    nationality: str | None = None
    pov_character: bool | None = None
    affiliation: str | None = None
    element: str | None = None
    first_appearance: str | None = None
    aliases: list[str] | None = None
