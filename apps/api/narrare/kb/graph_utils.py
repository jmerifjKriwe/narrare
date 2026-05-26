"""KB graph utility functions — pure algorithms with no I/O or dependencies.

Extracted from graph_service.py to keep file sizes within limits (RULE-04).
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from narrare.kb.graph_schemas import GraphEdge, GraphNode


def bfs_shortest_path(
    adjacency: dict[uuid.UUID, set[uuid.UUID]],
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> list[uuid.UUID] | None:
    """BFS shortest path between two entities.

    Args:
        adjacency: Adjacency map from entity ID to connected entity IDs.
        source_id: Starting entity ID.
        target_id: Target entity ID.

    Returns:
        Ordered list of entity IDs forming the shortest path,
        or None if no path exists.
    """
    if source_id == target_id:
        return [source_id]

    visited: set[uuid.UUID] = {source_id}
    queue: deque[tuple[uuid.UUID, list[uuid.UUID]]] = deque([(source_id, [source_id])])

    while queue:
        current, path = queue.popleft()
        for neighbor in adjacency.get(current, set()):
            if neighbor in visited:
                continue
            new_path = [*path, neighbor]
            if neighbor == target_id:
                return new_path
            visited.add(neighbor)
            queue.append((neighbor, new_path))

    return None


def count_connected_components(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> int:
    """Count connected components using union-find.

    Args:
        nodes: List of graph nodes.
        edges: List of graph edges.

    Returns:
        Number of connected components.
    """
    if not nodes:
        return 0

    parent: dict[uuid.UUID, uuid.UUID] = {n.id: n.id for n in nodes}

    def find(x: uuid.UUID) -> uuid.UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression
            x = parent[x]
        return x

    def union(a: uuid.UUID, b: uuid.UUID) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for edge in edges:
        if edge.source in parent and edge.target in parent:
            union(edge.source, edge.target)

    return len({find(n.id) for n in nodes})
