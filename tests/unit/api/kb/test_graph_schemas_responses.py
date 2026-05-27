"""Unit tests for KB graph visualization Pydantic schemas — Responses.

Tests GraphStats, GraphFilter, GraphResponse, and ShortestPathResponse:
valid creation, defaults, and validation constraints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.kb.graph_schemas import (
    GraphEdge,
    GraphFilter,
    GraphNode,
    GraphResponse,
    GraphStats,
    ShortestPathResponse,
)

# ---------------------------------------------------------------------------
# GraphStats
# ---------------------------------------------------------------------------


class TestGraphStats:
    """GraphStats schema validation."""

    def test_valid_creation(self) -> None:
        """GraphStats requires all count fields and dicts."""
        stats = GraphStats(
            node_count=10,
            edge_count=15,
            isolated_count=2,
            connected_components=3,
            entity_type_counts={"character": 5, "location": 5},
            rel_type_counts={"ally": 8, "enemy": 7},
        )

        assert stats.node_count == 10
        assert stats.edge_count == 15
        assert stats.isolated_count == 2
        assert stats.connected_components == 3

    def test_empty_dicts_allowed(self) -> None:
        """Empty entity/rel type count dicts are valid."""
        stats = GraphStats(
            node_count=0,
            edge_count=0,
            isolated_count=0,
            connected_components=0,
            entity_type_counts={},
            rel_type_counts={},
        )

        assert stats.entity_type_counts == {}
        assert stats.rel_type_counts == {}

    def test_missing_field_raises(self) -> None:
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            GraphStats(node_count=1)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# GraphFilter
# ---------------------------------------------------------------------------


class TestGraphFilter:
    """GraphFilter schema validation with constraints."""

    def test_defaults(self) -> None:
        """Default max_nodes=500, max_edges=2000."""
        f = GraphFilter()

        assert f.max_nodes == 500
        assert f.max_edges == 2000
        assert f.entity_types is None
        assert f.rel_types is None

    def test_custom_values(self) -> None:
        """Custom filter values are accepted."""
        f = GraphFilter(
            entity_types=["character"],
            rel_types=["ally"],
            max_nodes=100,
            max_edges=500,
        )

        assert f.entity_types == ["character"]
        assert f.rel_types == ["ally"]
        assert f.max_nodes == 100
        assert f.max_edges == 500

    def test_max_nodes_minimum_is_one(self) -> None:
        """max_nodes=1 is valid."""
        f = GraphFilter(max_nodes=1)
        assert f.max_nodes == 1

    def test_max_nodes_zero_raises(self) -> None:
        """max_nodes=0 raises ValidationError (ge=1)."""
        with pytest.raises(ValidationError):
            GraphFilter(max_nodes=0)

    def test_max_nodes_above_1000_raises(self) -> None:
        """max_nodes=1001 raises ValidationError (le=1000)."""
        with pytest.raises(ValidationError):
            GraphFilter(max_nodes=1001)

    def test_max_nodes_1000_is_valid(self) -> None:
        """max_nodes=1000 is the upper bound and is valid."""
        f = GraphFilter(max_nodes=1000)
        assert f.max_nodes == 1000

    def test_max_edges_minimum_is_one(self) -> None:
        """max_edges=1 is valid."""
        f = GraphFilter(max_edges=1)
        assert f.max_edges == 1

    def test_max_edges_zero_raises(self) -> None:
        """max_edges=0 raises ValidationError (ge=1)."""
        with pytest.raises(ValidationError):
            GraphFilter(max_edges=0)

    def test_max_edges_above_5000_raises(self) -> None:
        """max_edges=5001 raises ValidationError (le=5000)."""
        with pytest.raises(ValidationError):
            GraphFilter(max_edges=5001)

    def test_max_edges_5000_is_valid(self) -> None:
        """max_edges=5000 is the upper bound and is valid."""
        f = GraphFilter(max_edges=5000)
        assert f.max_edges == 5000


# ---------------------------------------------------------------------------
# GraphResponse
# ---------------------------------------------------------------------------


class TestGraphResponse:
    """GraphResponse schema validation."""

    def test_valid_full_response(self) -> None:
        """GraphResponse with nodes, edges, and stats."""
        node = GraphNode(id=uuid4(), label="A", entity_type="character")
        edge = GraphEdge(id=uuid4(), source=node.id, target=uuid4(), rel_type="ally")
        stats = GraphStats(
            node_count=1,
            edge_count=1,
            isolated_count=0,
            connected_components=1,
            entity_type_counts={"character": 1},
            rel_type_counts={"ally": 1},
        )

        response = GraphResponse(nodes=[node], edges=[edge], stats=stats)

        assert len(response.nodes) == 1
        assert len(response.edges) == 1
        assert response.stats.node_count == 1

    def test_empty_graph(self) -> None:
        """GraphResponse with empty nodes and edges lists."""
        stats = GraphStats(
            node_count=0,
            edge_count=0,
            isolated_count=0,
            connected_components=0,
            entity_type_counts={},
            rel_type_counts={},
        )

        response = GraphResponse(nodes=[], edges=[], stats=stats)

        assert response.nodes == []
        assert response.edges == []


# ---------------------------------------------------------------------------
# ShortestPathResponse
# ---------------------------------------------------------------------------


class TestShortestPathResponse:
    """ShortestPathResponse schema validation."""

    def test_with_path(self) -> None:
        """Response with a found path."""
        ids = [uuid4(), uuid4(), uuid4()]
        resp = ShortestPathResponse(
            path=ids,
            length=2,
            entity_names=["A", "\u2192", "B", "\u2192", "C"],
        )

        assert resp.path == ids
        assert resp.length == 2
        assert resp.entity_names == ["A", "\u2192", "B", "\u2192", "C"]

    def test_no_path_found(self) -> None:
        """Response when no path exists — all fields None."""
        resp = ShortestPathResponse(path=None, length=None, entity_names=None)

        assert resp.path is None
        assert resp.length is None
        assert resp.entity_names is None

    def test_single_node_path(self) -> None:
        """Path with a single node (length=0)."""
        node_id = uuid4()
        resp = ShortestPathResponse(
            path=[node_id],
            length=0,
            entity_names=["A"],
        )

        assert resp.path == [node_id]
        assert resp.length == 0
