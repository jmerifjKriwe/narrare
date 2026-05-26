"""KB graph visualization routes — thin delegation to GraphService.

No business logic here (RULE-06). All logic lives in graph_service.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_graph_service
from narrare.kb.graph_schemas import (
    GraphFilter,
    GraphResponse,
    ShortestPathResponse,
)
from narrare.kb.graph_service import GraphService

router = APIRouter(tags=["kb"])


@router.get(
    "/novels/{novel_id}/kb/graph",
    response_model=GraphResponse,
)
async def get_graph(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: GraphService = Depends(get_graph_service),
    entity_types: str | None = Query(
        default=None,
        description="Comma-separated entity types to include",
    ),
    rel_types: str | None = Query(
        default=None,
        description="Comma-separated relationship types to include",
    ),
    max_nodes: int = Query(default=500, ge=1, le=1000),
    max_edges: int = Query(default=2000, ge=1, le=5000),
) -> GraphResponse:
    """Get the complete graph for a novel's KB.

    Returns nodes (KB entries), edges (relationships), and computed statistics.
    Supports optional filtering by entity types and relationship types.
    """
    filter = GraphFilter(
        entity_types=entity_types.split(",") if entity_types else None,
        rel_types=rel_types.split(",") if rel_types else None,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )
    return await service.get_graph(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        filter=filter,
    )


@router.get(
    "/novels/{novel_id}/kb/graph/shortest-path",
    response_model=ShortestPathResponse,
)
async def get_shortest_path(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    source_id: uuid.UUID = Query(description="Source entity ID"),
    target_id: uuid.UUID = Query(description="Target entity ID"),
    service: GraphService = Depends(get_graph_service),
) -> ShortestPathResponse:
    """Find the shortest path between two entities via BFS.

    Returns the ordered list of entity IDs forming the path,
    or null if no path exists.
    """
    return await service.get_shortest_path(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        source_id=source_id,
        target_id=target_id,
    )
