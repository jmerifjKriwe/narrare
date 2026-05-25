"""Knowledge Base extraction schemas.

Split from schemas.py per RULE-04 (file size limit).
Request/response models for the KB extraction apply flow.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ApplyExtractionItem(BaseModel):
    """A single endorsed extraction item to apply.

    Created from the user's endorsement of an ExtractionItem in
    the extraction review panel. Maps directly to what the frontend
    sends after the user reviews and endorses extraction results.
    """

    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    """What kind of operation this item represents."""

    name: str
    """Entity or source entity name."""

    entity_type: str | None = None
    """KB entity type (character, location, etc.) for new/update entities."""

    proposed_content: dict[str, Any] | None = None
    """Suggested metadata fields for new/update entities."""

    target_entity_id: str | None = None
    """ID of existing entity to update (update_entity mode)."""

    relationship_type: str | None = None
    """Type of relationship (ally, member_of, etc.)."""

    related_entity_name: str | None = None
    """The other entity name in a relationship."""

    source_text: str = ""
    """Exact quote from chapter text supporting this extraction."""


class ApplyExtractionRequest(BaseModel):
    """Request body for endorsing extraction results.

    Contains the list of extraction items the user has reviewed
    and chosen to apply to their Knowledge Base.
    """

    items: list[ApplyExtractionItem]


class ApplyExtractionEntryResult(BaseModel):
    """Result of a single created or updated KB entry.

    Returned to the frontend so the UI can update its state
    with the new/updated entry IDs.
    """

    id: str
    """Entry UUID as string."""

    name: str
    """Entry name."""

    entity_type: str
    """KB entity type."""


class ApplyExtractionResponse(BaseModel):
    """Response after applying endorsed extraction items.

    Reports which entries were created vs updated so the frontend
    can refresh only the affected parts of the KB display.
    """

    created_entries: list[ApplyExtractionEntryResult] = []
    """Newly created KB entries."""

    updated_entries: list[ApplyExtractionEntryResult] = []
    """Updated existing KB entries."""
