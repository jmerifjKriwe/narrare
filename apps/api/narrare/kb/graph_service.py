"""KB graph visualization service — business logic.

Transforms KB entries and relationships into graph elements
suitable for visualization. No LLM calls — pure data transformation.

Both operations gate on novel ownership at service entry (IDOR fix S9):
the caller must own ``novel_id`` BEFORE any entry, relationship, or
adjacency data is read. Foreign and unknown novels are indistinguishable
(``NotFoundError`` → 404).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare.kb._novel_gate import verify_novel_owned
from narrare.kb.graph_schemas import (
    GraphEdge,
    GraphFilter,
    GraphNode,
    GraphResponse,
    GraphStats,
    ShortestPathResponse,
)
from narrare.kb.graph_utils import bfs_shortest_path, count_connected_components
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.kb.contracts import (
        KBRepositoryProtocol,
        RelationshipRepositoryProtocol,
    )
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)


class GraphService:
    """Business logic for KB graph visualization.

    Serializes KB entries and relationships into graph elements
    (nodes + edges) for frontend visualization. Computes statistics
    and supports BFS shortest path finding.

    Args:
        kb_repo: KB entry repository (graph nodes).
        rel_repo: Relationship repository (graph edges + adjacency).
        novel_repo: Novel repository — the novel ownership gate (IDOR
            fix S9); both reads verify the caller owns the novel first.
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        rel_repo: RelationshipRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._novel_repo = novel_repo

    async def get_graph(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        filter: GraphFilter | None = None,
    ) -> GraphResponse:
        """Serialize all KB entries and relationships as graph elements.

        Ownership gate first (IDOR fix S9): the caller must own
        ``novel_id`` — BEFORE any entry, relationship, or adjacency
        read. Foreign and unknown novels are indistinguishable.

        Args:
            novel_id: The novel whose KB to visualize.
            user_id: Caller identity — the ownership gate input.
            filter: Optional filter to reduce the graph scope.

        Returns:
            GraphResponse with nodes, edges, and computed statistics.

        Raises:
            NotFoundError: Novel not found or not owned by the caller.
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        max_nodes = filter.max_nodes if filter else 500

        # 1. Fetch all entries for the novel (up to max_nodes). Deprecated
        # entries are non-authoritative (ADR-085 §6.7/§9(c)) and stay
        # hidden unless the filter explicitly requests them.
        entries, total_count = await self._kb_repo.list_entries(
            novel_id=novel_id,
            page=1,
            page_size=max_nodes,
            include_deprecated=filter.include_deprecated if filter else False,
        )

        # 2. Apply entity_types filter if provided
        if filter and filter.entity_types:
            entries = [e for e in entries if e.entity_type in filter.entity_types]

        # 3. Fetch all relationships for the novel
        relationships = await self._rel_repo.list_all_for_novel(novel_id)

        # 4. Build adjacency map for degree computation
        adjacency = await self._rel_repo.get_adjacency_map(novel_id)

        # 5. Build node ID set for edge filtering
        node_ids: set[uuid.UUID] = {e.id for e in entries}

        # 6. Build nodes with degree from adjacency map
        nodes: list[GraphNode] = []
        for entry in entries:
            degree = len(adjacency.get(str(entry.id), set()))
            nodes.append(
                GraphNode(
                    id=entry.id,
                    label=entry.name,
                    entity_type=entry.entity_type,
                    status=entry.status,
                    tags=entry.tags,
                    metadata=entry.metadata_,
                    degree=degree,
                )
            )

        # 7. Build edges (filtered by rel_types and node membership)
        rel_type_filter = filter.rel_types if filter else None
        edges: list[GraphEdge] = []
        for rel in relationships:
            # Only include edges where both endpoints are in the node set
            if rel.source_id not in node_ids or rel.target_id not in node_ids:
                continue
            if rel_type_filter and rel.rel_type not in rel_type_filter:
                continue
            edges.append(
                GraphEdge(
                    id=rel.id,
                    source=rel.source_id,
                    target=rel.target_id,
                    label=rel.label,
                    rel_type=rel.rel_type,
                    direction=rel.direction,
                )
            )

        # 8. Apply max_edges filter
        max_edges = filter.max_edges if filter else 2000
        if len(edges) > max_edges:
            edges = edges[:max_edges]

        # 9. Compute statistics
        entity_type_counts: dict[str, int] = {}
        for node in nodes:
            entity_type_counts[node.entity_type] = entity_type_counts.get(node.entity_type, 0) + 1

        rel_type_counts: dict[str, int] = {}
        for edge in edges:
            rel_type_counts[edge.rel_type] = rel_type_counts.get(edge.rel_type, 0) + 1

        isolated_count = sum(1 for n in nodes if n.degree == 0)
        connected_components = count_connected_components(nodes, edges)

        stats = GraphStats(
            node_count=len(nodes),
            edge_count=len(edges),
            isolated_count=isolated_count,
            connected_components=connected_components,
            entity_type_counts=entity_type_counts,
            rel_type_counts=rel_type_counts,
        )

        logger.info(
            "kb_graph_computed",
            novel_id=str(novel_id),
            node_count=stats.node_count,
            edge_count=stats.edge_count,
            total_entries=total_count,
        )

        return GraphResponse(nodes=nodes, edges=edges, stats=stats)

    async def get_shortest_path(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> ShortestPathResponse:
        """Find the shortest path between two entities via BFS.

        Ownership gate first (IDOR fix S9): the caller must own
        ``novel_id`` — BEFORE the source/target entry load, so foreign
        entity ids are not enumerable either.

        Args:
            novel_id: The novel whose KB to search.
            user_id: Caller identity — the ownership gate input.
            source_id: Starting entity ID.
            target_id: Target entity ID.

        Returns:
            ShortestPathResponse with path, length, and entity names.

        Raises:
            NotFoundError: Novel not owned by the caller, or source or
                target entry not found in the novel.
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        # Validate that both entities exist in the novel
        source = await self._kb_repo.get_by_id(source_id)
        if source is None or source.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(source_id))

        target = await self._kb_repo.get_by_id(target_id)
        if target is None or target.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(target_id))

        # BFS on adjacency map
        adjacency = await self._rel_repo.get_adjacency_map(novel_id)

        # Convert string keys to UUIDs
        adj: dict[uuid.UUID, set[uuid.UUID]] = {}
        for k, v in adjacency.items():
            adj[uuid.UUID(k)] = {uuid.UUID(n) for n in v}

        # Check if source and target are in the graph
        all_node_ids: set[uuid.UUID] = set(adj.keys())
        for neighbors in adj.values():
            all_node_ids.update(neighbors)

        if source_id not in all_node_ids:
            return ShortestPathResponse(path=None, length=None, entity_names=None)
        if target_id not in all_node_ids:
            return ShortestPathResponse(path=None, length=None, entity_names=None)

        # BFS shortest path
        path = bfs_shortest_path(adj, source_id, target_id)

        if path is None:
            return ShortestPathResponse(path=None, length=None, entity_names=None)

        # Build entity names — fetch all entries for the novel. Deprecated
        # entries stay hidden (default visibility, ADR-085 §9(c)); a path
        # touching a skipped-collision loser edge falls back to its raw id.
        entries, _ = await self._kb_repo.list_entries(
            novel_id=novel_id,
            page_size=1000,
        )
        name_map: dict[uuid.UUID, str] = {e.id: e.name for e in entries}

        entity_names: list[str] = []
        for i, entity_id in enumerate(path):
            entity_names.append(name_map.get(entity_id, str(entity_id)))
            if i < len(path) - 1:
                entity_names.append("→")

        return ShortestPathResponse(
            path=path,
            length=len(path) - 1,
            entity_names=entity_names,
        )
