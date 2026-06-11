"""Unit tests for ConceptMetadata schema with nested groups.

Tests cover:
- ConceptMetadata with flat fields (backward compat)
- ConceptMetadata with nested group fields
- Nested group models have extra="allow"
- Extra fields preserved on both metadata and nested groups
- Validation constraints maintained
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from narrare_core.kb.schemas import (
    ConceptDefinition,
    ConceptHistory,
    ConceptMetadata,
)


class TestConceptDefinition:
    """Tests for the ConceptDefinition nested group model."""

    def test_all_optional(self) -> None:
        fields = ConceptDefinition()
        assert fields.category is None
        assert fields.summary is None
        assert fields.key_principles is None

    def test_with_data(self) -> None:
        fields = ConceptDefinition(
            category="magic",
            summary="A system of elemental manipulation",
            key_principles=["Balance", "Conservation"],
            rules=["Cannot create matter"],
        )
        assert fields.category == "magic"
        assert fields.key_principles is not None
        assert len(fields.key_principles) == 2
        assert fields.rules is not None
        assert "Cannot create matter" in fields.rules

    def test_extra_fields_preserved(self) -> None:
        fields: Any = ConceptDefinition(
            **cast("Any", {"category": "technology", "custom_field": "extra"})
        )
        assert fields.custom_field == "extra"

    def test_model_config_extra_allow(self) -> None:
        assert ConceptDefinition.model_config.get("extra") == "allow"


class TestConceptHistory:
    """Tests for the ConceptHistory nested group model."""

    def test_all_optional(self) -> None:
        fields = ConceptHistory()
        assert fields.origin is None
        assert fields.key_figures is None

    def test_with_data(self) -> None:
        fields = ConceptHistory(
            origin="Ancient civilization",
            discovery="Found in ruins",
            key_figures=["Archimedes", "Socrates"],
            evolution="Simplified over centuries",
        )
        assert fields.origin == "Ancient civilization"
        assert fields.key_figures is not None
        assert len(fields.key_figures) == 2

    def test_extra_fields_preserved(self) -> None:
        fields: Any = ConceptHistory(**cast("Any", {"origin": "Unknown", "source": "tablet"}))
        assert fields.source == "tablet"


class TestConceptMetadata:
    """Tests for ConceptMetadata with nested groups."""

    def test_flat_fields_only(self) -> None:
        """Backward compat: flat fields still work."""
        meta = ConceptMetadata(
            concept_type="philosophy",
            first_appearance="Chapter 1",
        )
        assert meta.concept_type == "philosophy"
        assert meta.first_appearance == "Chapter 1"

    def test_with_nested_groups(self) -> None:
        meta = ConceptMetadata(
            concept_type="magic",
            definition=ConceptDefinition(
                category="elemental",
                summary="Control over the four elements",
                key_principles=["Balance"],
            ),
            history=ConceptHistory(
                origin="The Old World",
                key_figures=["The First Mage"],
            ),
        )
        assert meta.concept_type == "magic"
        assert meta.definition is not None
        assert meta.definition.category == "elemental"
        assert meta.definition.key_principles == ["Balance"]
        assert meta.history is not None
        assert meta.history.origin == "The Old World"

    def test_nested_groups_optional(self) -> None:
        """Nested groups should be None when not provided."""
        meta = ConceptMetadata(concept_type="technology")
        assert meta.definition is None
        assert meta.history is None

    def test_all_groups(self) -> None:
        """All nested groups should work together."""
        meta = ConceptMetadata(
            definition=ConceptDefinition(category="social"),
            history=ConceptHistory(evolution="Gradual acceptance"),
        )
        assert meta.definition is not None
        assert meta.history is not None

    def test_extra_fields_on_metadata(self) -> None:
        """Extra fields should be preserved (inherited from KBEntryMetadata)."""
        meta: Any = ConceptMetadata(
            **cast("Any", {"concept_type": "philosophy", "custom_flag": True})
        )
        assert meta.custom_flag is True

    def test_extra_fields_in_group(self) -> None:
        """Extra fields within nested groups should be preserved."""
        meta: Any = ConceptMetadata(
            definition=ConceptDefinition(
                **cast("Any", {"category": "magic", "extra_attribute": "custom"})
            ),
        )
        assert meta.definition is not None
        assert meta.definition.extra_attribute == "custom"

    def test_validation_maintained(self) -> None:
        """Type validation should still work for flat fields."""
        with pytest.raises(ValidationError, match="concept_type"):
            ConceptMetadata.model_validate({"concept_type": 42})

    def test_empty_metadata(self) -> None:
        """Empty metadata should pass validation."""
        meta = ConceptMetadata()
        assert meta.concept_type is None
        assert meta.first_appearance is None

    def test_model_dump_includes_groups(self) -> None:
        """Serialisation should include nested groups."""
        meta = ConceptMetadata(
            definition=ConceptDefinition(category="technology"),
        )
        dumped = meta.model_dump()
        assert dumped["definition"] is not None
        assert dumped["definition"]["category"] == "technology"
