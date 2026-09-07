"""KB graph visualization Pydantic schemas.

Request/response models for the graph endpoint.
Field names MUST match frontend TypeScript types (RULE-17).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict, Field

# --- Graph Node ---


class GraphNode(BaseModel):
    """A single entity in the graph visualization.

    Maps 1:1 to a KBEntry, but only includes fields needed for rendering.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    label: str
    entity_type: str
    status: str = "draft"
    tags: list[str] | None = None
    metadata: dict[str, object] | None = Field(
        validation_alias="metadata_",
        default=None,
    )
    # Computed: number of relationships this entity participates in
    degree: int = 0


# --- Graph Edge ---


class GraphEdge(BaseModel):
    """A single relationship in the graph visualization.

    Maps 1:1 to a KBRelationship, but only includes fields needed for rendering.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    source: uuid.UUID  # Maps to KBRelationship.source_id
    target: uuid.UUID  # Maps to KBRelationship.target_id
    label: str | None = None
    rel_type: str
    direction: str = "directed"
    weight: float = 1.0  # For visual thickness; always 1.0 for now


# --- Graph Statistics ---


class GraphStats(BaseModel):
    """Computed statistics about the graph."""

    node_count: int
    edge_count: int
    isolated_count: int  # Nodes with degree 0
    connected_components: int
    entity_type_counts: dict[str, int]  # {"character": 12, "location": 5, ...}
    rel_type_counts: dict[str, int]  # {"ally": 8, "enemy": 3, ...}


# --- Graph Filter ---


class GraphFilter(BaseModel):
    """Optional filter to reduce graph scope."""

    entity_types: list[str] | None = None  # Filter to specific entity types
    rel_types: list[str] | None = None  # Filter to specific relationship types
    max_nodes: int = Field(default=500, ge=1, le=1000)
    max_edges: int = Field(default=2000, ge=1, le=5000)
    include_deprecated: bool = False  # ADR-085 §9(c): deprecated hidden unless asked


# --- Graph Response ---


class GraphResponse(BaseModel):
    """Full graph data response for visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


# --- Shortest Path Response ---


class ShortestPathResponse(BaseModel):
    """Response for shortest path query."""

    path: list[uuid.UUID] | None  # None if no path exists
    length: int | None  # Number of hops; None if no path
    entity_names: list[str] | None  # Human-readable path: ["A", "→", "B", "→", "C"]
