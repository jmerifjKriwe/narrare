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
    """Entity name; for relationship items the predicate (e.g. ``engaged_to``).
    Legacy relationship payloads carry the source entity name here."""

    entity_type: str | None = None
    """KB entity type (character, location, etc.) for new/update entities."""

    proposed_content: dict[str, Any] | None = None
    """Suggested metadata fields for new/update entities."""

    target_entity_id: str | None = None
    """ID of existing entity to update (update_entity mode)."""

    relationship_type: str | None = None
    """Type of relationship (ally, member_of, etc.)."""

    related_entity_name: str | None = None
    """Legacy target field for relationship items; prefer ``target_entity_name``."""

    source_entity_name: str | None = None
    """Source (subject) entity name for relationship items. When absent,
    ``name`` is used as a legacy fallback during apply."""

    target_entity_name: str | None = None
    """Target (object) entity name for relationship items. When absent,
    ``related_entity_name`` is used as a legacy fallback during apply."""

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
    can refresh only the affected parts of the KB display, plus every
    item that could NOT be applied (with reason) — unapplied items are
    never silently dropped.
    """

    created_entries: list[ApplyExtractionEntryResult] = []
    """Newly created KB entries."""

    updated_entries: list[ApplyExtractionEntryResult] = []
    """Updated existing KB entries."""

    skipped: list[SkippedItem] = []
    """Items that could not be applied, each with a machine-readable reason."""


class SkippedItem(BaseModel):
    """An endorsed extraction item that could not be applied.

    Reported in :attr:`ApplyExtractionResponse.skipped` so unapplied
    items stay visible instead of vanishing into log lines only.
    """

    name: str
    """The item's ``name`` field verbatim."""

    item_type: str
    """The item's operation type (new_entity, update_entity, …)."""

    reason: str
    """Machine-readable skip reason (e.g. ``source_not_found``)."""
