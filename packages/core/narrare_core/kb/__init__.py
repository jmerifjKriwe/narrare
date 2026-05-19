"""Knowledge Base domain module.

Owns metadata schemas, relationship type definitions, and any future
KB-specific domain logic.  No HTTP, no database sessions, no user auth.
"""

from narrare_core.kb.schemas import (
    SCHEMA_REGISTRY,
    KBEntryMetadata,
    get_schema,
)

__all__ = [
    "SCHEMA_REGISTRY",
    "KBEntryMetadata",
    "get_schema",
]
