"""KB metadata schemas — Pydantic models for entity-type-specific metadata.

Public exports:
    KBEntryMetadata — Base model (fallback for unknown entity types)
    CharacterMetadata — Character entity metadata
    LocationMetadata — Location entity metadata
    FactionMetadata — Faction entity metadata
    ObjectMetadata — Object entity metadata
    SystemMetadata — System entity metadata
    TimelineMetadata — Timeline entity metadata
    SCHEMA_REGISTRY — Mapping of entity type strings to schema classes
    get_schema — Lookup helper returning the correct schema class
"""

from .base import KBEntryMetadata
from .character import CharacterMetadata
from .faction import FactionMetadata
from .location import LocationMetadata
from .object import ObjectMetadata
from .registry import SCHEMA_REGISTRY, get_schema
from .system import SystemMetadata
from .timeline import TimelineMetadata

__all__ = [
    "SCHEMA_REGISTRY",
    "CharacterMetadata",
    "FactionMetadata",
    "KBEntryMetadata",
    "LocationMetadata",
    "ObjectMetadata",
    "SystemMetadata",
    "TimelineMetadata",
    "get_schema",
]
