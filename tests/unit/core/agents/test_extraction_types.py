"""Tests for ExtractionItem and ExtractionOutput models — validation, modes, defaults.

See extraction_types.py D3 — structured list output with confidence scoring.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput

# ---------------------------------------------------------------------------
# A. ExtractionItem — item types
# ---------------------------------------------------------------------------


class TestNewEntityItem:
    """item_type='new_entity' with entity_type and proposed_content."""

    def test_new_entity_item(self) -> None:
        item = ExtractionItem(
            item_type="new_entity",
            entity_type="character",
            name="Elena",
            confidence=0.9,
            source_text="Elena strode through the marble halls.",
            proposed_content={"role": "protagonist", "description": "A determined warrior"},
        )
        assert item.item_type == "new_entity"
        assert item.entity_type == "character"
        assert item.name == "Elena"
        assert item.proposed_content is not None
        assert item.proposed_content["role"] == "protagonist"


class TestUpdateEntityItem:
    """item_type='update_entity' with target_entity_id."""

    def test_update_entity_item(self) -> None:
        item = ExtractionItem(
            item_type="update_entity",
            entity_type="character",
            name="Anna",
            confidence=0.85,
            source_text="Anna now carries a silver sword.",
            target_entity_id="entity-123",
            proposed_content={"weapon": "silver sword"},
        )
        assert item.item_type == "update_entity"
        assert item.target_entity_id == "entity-123"


class TestRelationshipItem:
    """item_type='relationship' with relationship_type and related_entity_name."""

    def test_relationship_item(self) -> None:
        item = ExtractionItem(
            item_type="relationship",
            name="Anna and Peter",
            confidence=0.75,
            source_text="Anna and Peter fought side by side.",
            relationship_type="ally",
            related_entity_name="Peter",
        )
        assert item.item_type == "relationship"
        assert item.relationship_type == "ally"
        assert item.related_entity_name == "Peter"


class TestConflictItem:
    """item_type='conflict' with conflict_description."""

    def test_conflict_item(self) -> None:
        item = ExtractionItem(
            item_type="conflict",
            entity_type="character",
            name="Anna",
            confidence=0.8,
            source_text="Anna has blue eyes, but earlier she was described with green eyes.",
            conflict_description="KB says Anna has green eyes but chapter says blue eyes.",
        )
        assert item.item_type == "conflict"
        assert item.conflict_description is not None
        assert "green eyes" in item.conflict_description


# ---------------------------------------------------------------------------
# B. Confidence validation
# ---------------------------------------------------------------------------


class TestConfidenceValidation:
    """Confidence must be between 0.0 and 1.0."""

    def test_confidence_validation_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            ExtractionItem(
                item_type="new_entity",
                name="Ghost",
                confidence=-0.1,
                source_text="Mentioned once.",
            )

    def test_confidence_validation_rejects_over_one(self) -> None:
        with pytest.raises(ValidationError):
            ExtractionItem(
                item_type="new_entity",
                name="Ghost",
                confidence=1.5,
                source_text="Mentioned once.",
            )

    def test_confidence_boundary_zero(self) -> None:
        item = ExtractionItem(
            item_type="new_entity",
            name="Ghost",
            confidence=0.0,
            source_text="Mentioned once.",
        )
        assert item.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        item = ExtractionItem(
            item_type="new_entity",
            name="Elena",
            confidence=1.0,
            source_text="Explicitly named and described.",
        )
        assert item.confidence == 1.0


# ---------------------------------------------------------------------------
# C. ExtractionOutput — container model
# ---------------------------------------------------------------------------


class TestExtractionOutput:
    """ExtractionOutput list container."""

    def test_extraction_output_empty_results(self) -> None:
        output = ExtractionOutput()
        assert output.results == []
        assert output.analysis_notes == ""

    def test_extraction_output_multiple_results(self) -> None:
        items = [
            ExtractionItem(
                item_type="new_entity",
                entity_type="character",
                name="Elena",
                confidence=0.9,
                source_text="Elena appeared.",
            ),
            ExtractionItem(
                item_type="relationship",
                name="Elena → Peter",
                confidence=0.7,
                source_text="Elena trusts Peter.",
                relationship_type="ally",
                related_entity_name="Peter",
            ),
        ]
        output = ExtractionOutput(results=items, analysis_notes="Two extractions found.")
        assert len(output.results) == 2
        assert output.results[0].name == "Elena"
        assert output.results[1].item_type == "relationship"
        assert output.analysis_notes == "Two extractions found."


# ---------------------------------------------------------------------------
# D. Required fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """source_text and name are required."""

    def test_source_text_required(self) -> None:
        with pytest.raises(ValidationError, match="source_text"):
            ExtractionItem(  # pyright: ignore[reportCallIssue]
                item_type="new_entity",
                name="Elena",
                confidence=0.9,
            )

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            ExtractionItem(  # pyright: ignore[reportCallIssue]
                item_type="new_entity",
                confidence=0.9,
                source_text="Someone appeared.",
            )


# ---------------------------------------------------------------------------
# E. Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    """Round-trip serialization."""

    def test_roundtrip_extraction_item(self) -> None:
        original = ExtractionItem(
            item_type="new_entity",
            entity_type="location",
            name="The Tower",
            confidence=0.85,
            source_text="The Tower loomed over the city.",
            proposed_content={"type": "fortress"},
        )
        data = original.model_dump()
        restored = ExtractionItem.model_validate(data)
        assert restored.item_type == original.item_type
        assert restored.name == original.name
        assert restored.confidence == original.confidence
        assert restored.proposed_content == original.proposed_content

    def test_roundtrip_extraction_output(self) -> None:
        original = ExtractionOutput(
            results=[
                ExtractionItem(
                    item_type="conflict",
                    name="Anna",
                    confidence=0.8,
                    source_text="Contradiction.",
                    conflict_description="Eyes color mismatch.",
                ),
            ],
            analysis_notes="One conflict found.",
        )
        data = original.model_dump()
        restored = ExtractionOutput.model_validate(data)
        assert len(restored.results) == 1
        assert restored.results[0].conflict_description == "Eyes color mismatch."
        assert restored.analysis_notes == "One conflict found."
