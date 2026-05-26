"""Unit tests for graph_utils — pure BFS and connected-components algorithms.

No I/O, no DB, no LLM — pure function tests.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.kb.graph_schemas import GraphEdge, GraphNode
from narrare.kb.graph_utils import bfs_shortest_path, count_connected_components


class TestBfsShortestPath:
    """Tests for the bfs_shortest_path utility function."""

    def test_direct_neighbor(self) -> None:
        """Path of length 1 between direct neighbors."""
        a, b = uuid4(), uuid4()
        adjacency = {a: {b}, b: {a}}
        result = bfs_shortest_path(adjacency, a, b)
        assert result == [a, b]

    def test_two_hop_path(self) -> None:
        """Path of length 2 via intermediate node."""
        a, b, c = uuid4(), uuid4(), uuid4()
        adjacency = {a: {b}, b: {a, c}, c: {b}}
        result = bfs_shortest_path(adjacency, a, c)
        assert result == [a, b, c]

    def test_no_path_returns_none(self) -> None:
        """Disconnected components return None."""
        a, b = uuid4(), uuid4()
        adjacency = {a: set(), b: set()}
        result = bfs_shortest_path(adjacency, a, b)
        assert result is None

    def test_same_source_and_target(self) -> None:
        """Source == target returns single-element path."""
        a = uuid4()
        adjacency = {a: set()}
        result = bfs_shortest_path(adjacency, a, a)
        assert result == [a]

    def test_picks_shortest_path(self) -> None:
        """BFS picks shortest path when multiple paths exist."""
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
        # a -> d direct edge (length 1) should be preferred over a -> b -> d (length 2)
        adjacency = {a: {b, c, d}, b: {a, d}, c: {a, d}, d: {a, b, c}}
        result = bfs_shortest_path(adjacency, a, d)
        assert result is not None
        assert result == [a, d]
        assert len(result) == 2  # shortest path


class TestCountConnectedComponents:
    """Tests for the count_connected_components utility function."""

    def test_empty_graph(self) -> None:
        """Empty graph has 0 components."""
        result = count_connected_components([], [])
        assert result == 0

    def test_single_isolated_node(self) -> None:
        """Single node with no edges has 1 component."""
        node = GraphNode(
            id=uuid4(),
            label="A",
            entity_type="character",
            status="draft",
            degree=0,
        )
        result = count_connected_components([node], [])
        assert result == 1

    def test_fully_connected(self) -> None:
        """All nodes connected = 1 component."""
        a, b, c = uuid4(), uuid4(), uuid4()
        nodes = [
            GraphNode(id=a, label="A", entity_type="character", status="draft", degree=2),
            GraphNode(id=b, label="B", entity_type="character", status="draft", degree=2),
            GraphNode(id=c, label="C", entity_type="character", status="draft", degree=2),
        ]
        edges = [
            GraphEdge(id=uuid4(), source=a, target=b, rel_type="ally"),
            GraphEdge(id=uuid4(), source=b, target=c, rel_type="ally"),
        ]
        result = count_connected_components(nodes, edges)
        assert result == 1

    def test_two_disconnected_groups(self) -> None:
        """Two separate groups = 2 components."""
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
        nodes = [
            GraphNode(id=a, label="A", entity_type="character", status="draft", degree=1),
            GraphNode(id=b, label="B", entity_type="character", status="draft", degree=1),
            GraphNode(id=c, label="C", entity_type="location", status="draft", degree=1),
            GraphNode(id=d, label="D", entity_type="location", status="draft", degree=1),
        ]
        edges = [
            GraphEdge(id=uuid4(), source=a, target=b, rel_type="ally"),
            GraphEdge(id=uuid4(), source=c, target=d, rel_type="contains"),
        ]
        result = count_connected_components(nodes, edges)
        assert result == 2
