"""Schema registry — maps entity type strings to metadata schema classes.

Provides a single lookup point for determining which Pydantic model to
use when validating metadata for a given entity type.  Unknown entity
types fall back to the base ``KBEntryMetadata`` class.
"""

from __future__ import annotations

from .base import KBEntryMetadata
from .character import CharacterMetadata
from .concept import ConceptMetadata
from .faction import FactionMetadata
from .location import LocationMetadata
from .object import ObjectMetadata
from .setting import SettingMetadata
from .system import SystemMetadata
from .timeline import TimelineMetadata

SCHEMA_REGISTRY: dict[str, type[KBEntryMetadata]] = {
    "character": CharacterMetadata,
    "concept": ConceptMetadata,
    "faction": FactionMetadata,
    "location": LocationMetadata,
    "object": ObjectMetadata,
    "setting": SettingMetadata,
    "system": SystemMetadata,
    "timeline": TimelineMetadata,
}
"""Mapping of entity type strings to their metadata schema classes."""


def get_schema(entity_type: str) -> type[KBEntryMetadata]:
    """Return the metadata schema class for the given entity type.

    Args:
        entity_type: Entity type string (e.g. "character", "location").

    Returns:
        The type-specific schema class if known, otherwise the base
        ``KBEntryMetadata`` class (which allows extra fields).
    """
    return SCHEMA_REGISTRY.get(entity_type, KBEntryMetadata)
