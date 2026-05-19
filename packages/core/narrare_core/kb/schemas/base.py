"""Base metadata model for Knowledge Base entries.

Provides the foundational Pydantic model that all entity-type-specific
metadata schemas inherit from.  Extra fields are always allowed so that
unknown or future entity types don't cause validation failures.

Templates are recommendations, not enforcement — every field is optional.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KBEntryMetadata(BaseModel):
    """Base metadata model for any KB entry.

    All entity-type-specific metadata classes inherit from this.
    ``extra="allow"`` ensures forward-compatibility: new fields added
    by the user or future template versions are preserved rather than
    discarded.
    """

    model_config = ConfigDict(extra="allow")

    # No required fields — every field is optional because templates
    # are recommendations, not enforcement.  Subclasses add typed
    # optional fields for their entity type.
