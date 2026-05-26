"""KB graph visualization service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.graph_schemas import (
        GraphFilter,
        GraphResponse,
        ShortestPathResponse,
    )


@runtime_checkable
class GraphServiceProtocol(Protocol):
    """Protocol for KB graph data serialization.

    Transforms KB entries and relationships into graph elements
    suitable for visualization. No LLM calls — pure data transformation.
    """

    async def get_graph(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        filter: GraphFilter | None = None,
    ) -> GraphResponse:
        """Serialize all KB entries and relationships as graph elements.

        Args:
            novel_id: The novel whose KB to visualize.
            user_id: The user requesting the graph (for authorization).
            filter: Optional filter to reduce the graph scope.

        Returns:
            GraphResponse with nodes, edges, and computed statistics.
        """
        ...

    async def get_shortest_path(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> ShortestPathResponse:
        """Find the shortest path between two entities via BFS.

        Args:
            novel_id: The novel whose KB to search.
            user_id: The user requesting the path.
            source_id: Starting entity ID.
            target_id: Target entity ID.

        Returns:
            ShortestPathResponse with path, length, and entity names.
        """
        ...
