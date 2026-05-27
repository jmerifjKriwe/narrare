"""Unit tests for KB graph visualization Pydantic schemas — Node and Edge.

Tests GraphNode and GraphEdge: valid creation, defaults, and validation
constraints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.kb.graph_schemas import GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# GraphNode
# ---------------------------------------------------------------------------


class TestGraphNode:
    """GraphNode schema validation."""

    def test_valid_creation_with_required_fields(self) -> None:
        """GraphNode requires id, label, entity_type."""
        node = GraphNode(id=uuid4(), label="Aria", entity_type="character")

        assert node.label == "Aria"
        assert node.entity_type == "character"

    def test_default_status_is_draft(self) -> None:
        """Default status is 'draft'."""
        node = GraphNode(id=uuid4(), label="Aria", entity_type="character")

        assert node.status == "draft"

    def test_default_tags_is_none(self) -> None:
        """Default tags is None."""
        node = GraphNode(id=uuid4(), label="Aria", entity_type="character")

        assert node.tags is None

    def test_default_metadata_is_none(self) -> None:
        """Default metadata is None."""
        node = GraphNode(id=uuid4(), label="Aria", entity_type="character")

        assert node.metadata is None

    def test_default_degree_is_zero(self) -> None:
        """Default degree is 0."""
        node = GraphNode(id=uuid4(), label="Aria", entity_type="character")

        assert node.degree == 0

    def test_optional_fields_set(self) -> None:
        """Optional fields can be set explicitly."""
        node = GraphNode(
            id=uuid4(),
            label="Aria",
            entity_type="character",
            status="canon",
            tags=["protagonist"],
            metadata={"power": "fire"},
            degree=5,
        )

        assert node.status == "canon"
        assert node.tags == ["protagonist"]
        assert node.metadata == {"power": "fire"}
        assert node.degree == 5

    def test_missing_required_field_raises(self) -> None:
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            GraphNode(id=uuid4(), label="Aria")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# GraphEdge
# ---------------------------------------------------------------------------


class TestGraphEdge:
    """GraphEdge schema validation."""

    def test_valid_creation_with_required_fields(self) -> None:
        """GraphEdge requires id, source, target, rel_type."""
        source = uuid4()
        target = uuid4()
        edge = GraphEdge(id=uuid4(), source=source, target=target, rel_type="ally")

        assert edge.source == source
        assert edge.target == target
        assert edge.rel_type == "ally"

    def test_default_label_is_none(self) -> None:
        """Default label is None."""
        edge = GraphEdge(id=uuid4(), source=uuid4(), target=uuid4(), rel_type="ally")

        assert edge.label is None

    def test_default_direction_is_directed(self) -> None:
        """Default direction is 'directed'."""
        edge = GraphEdge(id=uuid4(), source=uuid4(), target=uuid4(), rel_type="ally")

        assert edge.direction == "directed"

    def test_default_weight_is_one(self) -> None:
        """Default weight is 1.0."""
        edge = GraphEdge(id=uuid4(), source=uuid4(), target=uuid4(), rel_type="ally")

        assert edge.weight == 1.0

    def test_all_fields_set(self) -> None:
        """All optional fields can be set."""
        edge = GraphEdge(
            id=uuid4(),
            source=uuid4(),
            target=uuid4(),
            label="Best friends",
            rel_type="ally",
            direction="mutual",
            weight=2.5,
        )

        assert edge.label == "Best friends"
        assert edge.direction == "mutual"
        assert edge.weight == 2.5

    def test_missing_rel_type_raises(self) -> None:
        """Missing rel_type raises ValidationError."""
        with pytest.raises(ValidationError):
            GraphEdge(id=uuid4(), source=uuid4(), target=uuid4())  # type: ignore[call-arg]
