"""Unit tests for KB extraction Pydantic schemas.

Tests ApplyExtractionItem, ApplyExtractionRequest,
ApplyExtractionEntryResult, and ApplyExtractionResponse:
valid creation, defaults, literal validation, and edge cases.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.kb.schemas_extraction import (
    ApplyExtractionEntryResult,
    ApplyExtractionItem,
    ApplyExtractionRequest,
    ApplyExtractionResponse,
)

# ---------------------------------------------------------------------------
# ApplyExtractionItem
# ---------------------------------------------------------------------------


class TestApplyExtractionItem:
    """ApplyExtractionItem schema validation."""

    def test_new_entity_valid(self) -> None:
        """Valid new_entity item with required fields."""
        item = ApplyExtractionItem(
            item_type="new_entity",
            name="Aria",
            entity_type="character",
            proposed_content={"role": "protagonist"},
        )

        assert item.item_type == "new_entity"
        assert item.name == "Aria"
        assert item.entity_type == "character"
        assert item.proposed_content == {"role": "protagonist"}

    def test_update_entity_valid(self) -> None:
        """Valid update_entity item with target_entity_id."""
        entity_id = str(uuid4())
        item = ApplyExtractionItem(
            item_type="update_entity",
            name="Aria",
            entity_type="character",
            target_entity_id=entity_id,
            proposed_content={"role": "antagonist"},
        )

        assert item.item_type == "update_entity"
        assert item.target_entity_id == entity_id

    def test_relationship_valid(self) -> None:
        """Valid relationship item."""
        item = ApplyExtractionItem(
            item_type="relationship",
            name="Aria",
            relationship_type="ally",
            related_entity_name="Kael",
        )

        assert item.item_type == "relationship"
        assert item.relationship_type == "ally"
        assert item.related_entity_name == "Kael"

    def test_conflict_valid(self) -> None:
        """Valid conflict item."""
        item = ApplyExtractionItem(
            item_type="conflict",
            name="Aria",
        )

        assert item.item_type == "conflict"

    def test_invalid_item_type_raises(self) -> None:
        """Invalid item_type raises ValidationError."""
        with pytest.raises(ValidationError):
            ApplyExtractionItem(
                item_type="invalid_type",  # type: ignore[arg-type]
                name="Aria",
            )

    def test_defaults_are_none_or_empty(self) -> None:
        """Optional fields default to None or empty string."""
        item = ApplyExtractionItem(
            item_type="new_entity",
            name="Aria",
        )

        assert item.entity_type is None
        assert item.proposed_content is None
        assert item.target_entity_id is None
        assert item.relationship_type is None
        assert item.related_entity_name is None
        assert item.source_text == ""

    def test_source_text_set(self) -> None:
        """source_text can be set with supporting quote."""
        item = ApplyExtractionItem(
            item_type="new_entity",
            name="Aria",
            source_text="Aria drew her sword.",
        )

        assert item.source_text == "Aria drew her sword."

    def test_missing_name_raises(self) -> None:
        """Missing required 'name' field raises ValidationError."""
        with pytest.raises(ValidationError):
            ApplyExtractionItem(item_type="new_entity")  # type: ignore[call-arg]

    def test_missing_item_type_raises(self) -> None:
        """Missing required 'item_type' raises ValidationError."""
        with pytest.raises(ValidationError):
            ApplyExtractionItem(name="Aria")  # type: ignore[call-arg]

    def test_all_item_types_valid(self) -> None:
        """All four literal values are accepted."""
        for t in ("new_entity", "update_entity", "relationship", "conflict"):
            item = ApplyExtractionItem(item_type=t, name="Test")
            assert item.item_type == t


# ---------------------------------------------------------------------------
# ApplyExtractionRequest
# ---------------------------------------------------------------------------


class TestApplyExtractionRequest:
    """ApplyExtractionRequest schema validation."""

    def test_valid_request_with_items(self) -> None:
        """Request with a list of extraction items."""
        items = [
            ApplyExtractionItem(item_type="new_entity", name="Aria"),
            ApplyExtractionItem(
                item_type="relationship",
                name="Aria",
                relationship_type="ally",
                related_entity_name="Kael",
            ),
        ]
        request = ApplyExtractionRequest(items=items)

        assert len(request.items) == 2
        assert request.items[0].name == "Aria"
        assert request.items[1].relationship_type == "ally"

    def test_empty_items_list(self) -> None:
        """Empty items list is valid (no-op apply)."""
        request = ApplyExtractionRequest(items=[])

        assert request.items == []

    def test_missing_items_raises(self) -> None:
        """Missing items field raises ValidationError."""
        with pytest.raises(ValidationError):
            ApplyExtractionRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ApplyExtractionEntryResult
# ---------------------------------------------------------------------------


class TestApplyExtractionEntryResult:
    """ApplyExtractionEntryResult schema validation."""

    def test_valid_result(self) -> None:
        """Result with id, name, entity_type."""
        entry_id = str(uuid4())
        result = ApplyExtractionEntryResult(
            id=entry_id,
            name="Aria",
            entity_type="character",
        )

        assert result.id == entry_id
        assert result.name == "Aria"
        assert result.entity_type == "character"

    def test_missing_field_raises(self) -> None:
        """Missing any required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ApplyExtractionEntryResult(id=str(uuid4()), name="Aria")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ApplyExtractionResponse
# ---------------------------------------------------------------------------


class TestApplyExtractionResponse:
    """ApplyExtractionResponse schema validation."""

    def test_defaults_empty_lists(self) -> None:
        """Default created/updated entries are empty lists."""
        response = ApplyExtractionResponse()

        assert response.created_entries == []
        assert response.updated_entries == []

    def test_with_created_entries(self) -> None:
        """Response with created entries."""
        entry = ApplyExtractionEntryResult(
            id=str(uuid4()),
            name="Aria",
            entity_type="character",
        )
        response = ApplyExtractionResponse(created_entries=[entry])

        assert len(response.created_entries) == 1
        assert response.created_entries[0].name == "Aria"
        assert response.updated_entries == []

    def test_with_updated_entries(self) -> None:
        """Response with updated entries."""
        entry = ApplyExtractionEntryResult(
            id=str(uuid4()),
            name="Kael",
            entity_type="character",
        )
        response = ApplyExtractionResponse(updated_entries=[entry])

        assert response.created_entries == []
        assert len(response.updated_entries) == 1
        assert response.updated_entries[0].name == "Kael"

    def test_with_both_entries(self) -> None:
        """Response with both created and updated entries."""
        created = ApplyExtractionEntryResult(id=str(uuid4()), name="Aria", entity_type="character")
        updated = ApplyExtractionEntryResult(id=str(uuid4()), name="Kael", entity_type="character")
        response = ApplyExtractionResponse(
            created_entries=[created],
            updated_entries=[updated],
        )

        assert len(response.created_entries) == 1
        assert len(response.updated_entries) == 1
