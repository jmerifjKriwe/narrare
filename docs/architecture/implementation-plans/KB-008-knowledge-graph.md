# KB-008: Knowledge Graph Visualization — Architecture Specification

> **Status**: Draft
> **Area**: KB / Graph Visualization
> **Depends on**: KB-001 (entity CRUD), KB-006 (worldbuilding)
> **Author**: Architecture Specialist
> **Date**: 2026-05-26

---

## Table of Contents

1. [Executive Summary & Decision](#1-executive-summary--decision)
2. [Root Cause & Motivation](#2-root-cause--motivation)
3. [Alternatives Considered](#3-alternatives-considered)
4. [Contracts](#4-contracts)
5. [Module Map](#5-module-map)
6. [Data Flow](#6-data-flow)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Performance Considerations](#8-performance-considerations)
9. [RULE-XX Compliance Matrix](#9-rule-xx-compliance-matrix)
10. [Work Plan](#10-work-plan)

---

## 1. Executive Summary & Decision

### Decision: Thin Backend Serialization + Cytoscape.js Frontend

KB-008 is a **visualization feature** — the backend serializes existing KB data as graph
elements (nodes + edges), and the frontend renders them with Cytoscape.js. No LLM calls,
no new domain logic, no new database tables.

| Aspect | Approach |
|--------|----------|
| **Backend** | Single `GET /novels/{id}/kb/graph` endpoint. `GraphService` serializes KB entries as nodes and relationships as edges using existing repos. |
| **Frontend** | Cytoscape.js component with force-directed (cola), hierarchical (dagre), and concentric layouts. Click/drag/filter/search interaction. |
| **New dependency** | `cytoscape` + `cytoscape-dagre` + `dagre` (npm packages) |
| **No LLM** | Pure data serialization — no PromptComposer, no ModelRegistry, no agents |
| **No SSE** | REST-only — graph data is a single request/response, not a streaming operation |
| **Path finding** | BFS shortest path — pure algorithm, no backend needed |

### Key Architectural Insight

The graph visualization is a **view** on KB data, not a separate domain. Entries ARE nodes.
Relationships ARE edges. The `GraphService` doesn't create new data — it transforms existing
KB entries and relationships into the Cytoscape.js element format. This means:

1. **No new database tables** — all data comes from `kb_entries` and `kb_relationships`.
2. **No new repository** — `GraphService` uses existing `KBRepositoryProtocol` and
   `RelationshipRepositoryProtocol`.
3. **No cross-module imports** — graph files live in `apps/api/narrare/kb/` alongside
   the data they serialize.

---

## 2. Root Cause & Motivation

### Symptom

Writers using the KB browser see entries as a flat list. They cannot see how entities connect
at a glance. When a novel has 50+ characters, locations, and factions, understanding the
relationship network requires mentally tracking dozens of connections — an impossible task
for complex worlds.

### Root Cause (2x Why)

1. **Why is this a problem?** The list-based KB browser presents entities in isolation.
   Relationships are visible only one-at-a-time in the detail panel. There is no way to
   see the *shape* of the world — which entities are hubs, which are isolated, how factions
   cluster together.

2. **Why does the list view fail?** Because relationships are inherently *graph-structured*
   data. A list view is the wrong abstraction for network data. The correct visualization
   is a node-link diagram where proximity and connection encode meaning.

### Design Principle

> The graph is a *lens* on existing KB data, not a new data model. Every node corresponds
> to a `KBEntry`. Every edge corresponds to a `KBRelationship`. The graph view and the
> list view show the same data through different lenses.

---

## 3. Alternatives Considered

### Option A — Separate `/graph` Module (REJECTED)

Create a new `apps/api/narrare/graph/` module with its own service, contracts, and router.

| Pro | Con |
|-----|-----|
| Clean namespace separation | **Violates RULE-05**: Graph data IS KB data. A separate module would import from `kb/`, creating cross-module coupling for data that belongs to one domain |
| Could grow into a full knowledge graph engine | **Violates RULE-06**: The graph service has one job — serialize KB data. A whole module for one thin service is over-engineering |
| - | **YAGNI**: The module map lists `graph/` as "Entities, relationships, facts" — but those ARE KB entries and relationships. No separate domain exists |

**Verdict**: REJECTED — the graph visualization is a view on KB data, not a separate domain.

### Option B — Add Graph Endpoint to KB Module (SELECTED)

Add `graph_service.py`, `graph_contracts.py`, `graph_schemas.py`, and `router_graph.py`
to the existing `apps/api/narrare/kb/` module.

| Pro | Con |
|-----|-----|
| Uses existing repos directly — no cross-module imports | KB module already has 52 files |
| Single domain — entries, relationships, and their graph view are one concern | Need to be disciplined about file sizes (RULE-04) |
| Simpler DI — same session, same repos | |
| Follows existing patterns (like `router_relationships.py`, `router_consistency.py`) | |
| No new database tables or migrations | |

**Verdict**: SELECTED — the graph visualization is a view on KB data. The service is thin
(~80 lines), the router is thin (~40 lines), and the schemas are straightforward (~60 lines).
This follows the established pattern of sub-feature files within the KB module.

### Option C — Client-Side Only (REJECTED)

Skip the backend endpoint entirely. Fetch all entries and relationships from existing
endpoints and build the graph client-side.

| Pro | Con |
|-----|-----|
| No backend changes needed | **Performance**: Two separate API calls (entries + relationships per entry) vs. one optimized call. For 200 entries with 5 relationships each, that's 1 + 200 = 201 API calls to build the full graph |
| - | **Data volume**: Existing endpoints return full entry bodies (including `body` text that can be 10KB+). The graph only needs `id`, `name`, `entity_type`, and `metadata` for nodes |
| - | **No stats**: Client would need to compute node degree, connected component count, etc. The backend can do this efficiently in one query |
| - | **No filtering**: Backend can filter by entity type before serialization, reducing payload |

**Verdict**: REJECTED — a dedicated endpoint is more efficient and provides a cleaner
contract between frontend and backend.

---

## 4. Contracts

### 4.1 Graph Service Protocol

**Location**: `apps/api/narrare/kb/graph_contracts.py` (new)

```python
"""KB graph visualization service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.graph_schemas import (
        GraphEdge,
        GraphFilter,
        GraphNode,
        GraphResponse,
        GraphStats,
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
    ) -> list[uuid.UUID] | None:
        """Find the shortest path between two entities via BFS.

        Args:
            novel_id: The novel whose KB to search.
            user_id: The user requesting the path.
            source_id: Starting entity ID.
            target_id: Target entity ID.

        Returns:
            Ordered list of entity IDs forming the shortest path,
            or None if no path exists.
        """
        ...
```

### 4.2 Graph Schemas

**Location**: `apps/api/narrare/kb/graph_schemas.py` (new)

```python
"""KB graph visualization Pydantic schemas.

Request/response models for the graph endpoint.
Field names MUST match frontend TypeScript types (RULE-17).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field


# --- Graph Node ---

class GraphNode(BaseModel):
    """A single entity in the graph visualization.

    Maps 1:1 to a KBEntry, but only includes fields needed for rendering.
    """

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
```

### 4.3 Frontend TypeScript Types

**Location**: `packages/web/lib/api/kb-graph.ts` (new)

```typescript
/**
 * KB Graph API client — typed wrappers for graph visualization endpoints.
 *
 * Field names MUST match backend Pydantic schemas (RULE-17).
 */

import { fetchApi } from "./client";
import type { KBEntityType } from "./kb";

// --- Graph Node ---

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  status: string;
  tags: string[] | null;
  metadata: Record<string, unknown> | null;
  degree: number;
}

// --- Graph Edge ---

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string | null;
  rel_type: string;
  direction: string;
  weight: number;
}

// --- Graph Statistics ---

export interface GraphStats {
  node_count: number;
  edge_count: number;
  isolated_count: number;
  connected_components: number;
  entity_type_counts: Record<string, number>;
  rel_type_counts: Record<string, number>;
}

// --- Graph Filter ---

export interface GraphFilter {
  entity_types?: string[];
  rel_types?: string[];
  max_nodes?: number;
  max_edges?: number;
}

// --- Graph Response ---

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

// --- Shortest Path Response ---

export interface ShortestPathResponse {
  path: string[] | null;
  length: number | null;
  entity_names: string[] | null;
}

// --- API functions ---

export const kbGraphApi = {
  /** Fetch full graph data for a novel's KB. */
  getGraph: (novelId: string, filter?: GraphFilter) => {
    const searchParams = new URLSearchParams();
    if (filter?.entity_types?.length) {
      searchParams.set("entity_types", filter.entity_types.join(","));
    }
    if (filter?.rel_types?.length) {
      searchParams.set("rel_types", filter.rel_types.join(","));
    }
    if (filter?.max_nodes) {
      searchParams.set("max_nodes", String(filter.max_nodes));
    }
    if (filter?.max_edges) {
      searchParams.set("max_edges", String(filter.max_edges));
    }
    const qs = searchParams.toString();
    return fetchApi<GraphResponse>(`/novels/${novelId}/kb/graph${qs ? `?${qs}` : ""}`);
  },

  /** Find shortest path between two entities. */
  getShortestPath: (novelId: string, sourceId: string, targetId: string) =>
    fetchApi<ShortestPathResponse>(
      `/novels/${novelId}/kb/graph/shortest-path?source_id=${sourceId}&target_id=${targetId}`,
    ),
};
```

---

## 5. Module Map

### 5.1 New Files

Files are listed in implementation order (Layer Ordering).

| # | Layer | File | Purpose | Est. Lines |
|---|-------|------|---------|-----------|
| 1 | Backend | `apps/api/narrare/kb/graph_contracts.py` | Protocol definition for GraphService | ~40 |
| 2 | Backend | `apps/api/narrare/kb/graph_schemas.py` | Pydantic request/response models | ~80 |
| 3 | Backend | `apps/api/narrare/kb/graph_service.py` | GraphService — serialize KB data as graph elements + BFS path finding | ~120 |
| 4 | Backend | `apps/api/narrare/kb/router_graph.py` | FastAPI routes (thin delegation) | ~50 |
| 5 | Backend | `apps/api/narrare/kb/dependencies.py` | Add `get_graph_service()` factory | ~15 |
| 6 | Frontend | `packages/web/lib/api/kb-graph.ts` | API types + client functions | ~80 |
| 7 | Frontend | `packages/web/lib/hooks/useKBGraph.ts` | TanStack Query hooks for graph data | ~60 |
| 8 | Frontend | `packages/web/components/studio/kb/KnowledgeGraphView.tsx` | Main graph visualization component | ~250 |
| 9 | Frontend | `packages/web/components/studio/kb/KnowledgeGraphControls.tsx` | Layout selector, filter panel, search | ~150 |
| 10 | Frontend | `packages/web/components/studio/kb/KnowledgeGraphPathPanel.tsx` | Shortest path result display | ~80 |
| 11 | Frontend | `packages/web/components/studio/kb/graph-layouts.ts` | Cytoscape layout configuration objects | ~60 |
| 12 | Frontend | `packages/web/components/studio/kb/graph-styles.ts` | Cytoscape stylesheet (node/edge styling by entity type) | ~80 |
| 13 | Frontend | `packages/web/components/studio/kb/graph-utils.ts` | BFS path finding, node filtering, degree computation | ~80 |

### 5.2 Modified Files

| # | File | Change | Reason |
|---|------|--------|--------|
| M1 | `packages/web/components/studio/WorldBuilding.tsx` | Add "Graph" tab state + render `KnowledgeGraphView` | Frontend integration |
| M2 | `packages/web/components/studio/kb/KBCategorySidebar.tsx` | Add "Graph" tab button | Frontend integration |
| M3 | `packages/web/lib/api/kb.ts` | No changes needed — graph types are in separate file | — |
| M4 | `packages/web/messages/en/studio.json` | Add graph-related i18n keys (RULE-16) | i18n |
| M5 | `packages/web/messages/de/studio.json` | Add graph-related i18n keys | i18n |
| M6 | `packages/web/messages/fr/studio.json` | Add graph-related i18n keys | i18n |
| M7 | `packages/web/lib/i18n/request.ts` | No change needed — `studio` namespace already registered | — |
| M8 | `packages/web/package.json` | Add `cytoscape`, `cytoscape-dagre`, `dagre` dependencies | New dependency |

### 5.3 Module Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      apps/api/narrare/kb/                           │
│                                                                      │
│  router_graph.py ──→ graph_service.py                                │
│                          │                                           │
│                          ├──→ KBRepositoryProtocol (list_entries)    │
│                          │    (existing, unchanged)                  │
│                          │                                           │
│                          └──→ RelationshipRepositoryProtocol         │
│                               (list_for_entry, get_adjacency_map)    │
│                               (existing, unchanged)                   │
│                                                                      │
│  graph_contracts.py ← Protocol definition                            │
│  graph_schemas.py   ← Request/response models                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      packages/web/                                   │
│                                                                      │
│  WorldBuilding.tsx                                                   │
│    ├── KBCategorySidebar.tsx  (add "Graph" tab)                      │
│    ├── KBEntryList + KBDetailPanel  (existing, unchanged)            │
│    └── KnowledgeGraphView.tsx  (new — replaces columns 2+3)        │
│         ├── KnowledgeGraphControls.tsx  (layout, filter, search)    │
│         ├── KnowledgeGraphPathPanel.tsx  (shortest path display)    │
│         ├── graph-layouts.ts  (Cytoscape layout configs)            │
│         ├── graph-styles.ts   (Cytoscape visual styles)             │
│         └── graph-utils.ts    (BFS, filtering, degree)              │
│                                                                      │
│  lib/api/kb-graph.ts  ← API client                                  │
│  lib/hooks/useKBGraph.ts  ← TanStack Query hooks                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 Key Principle: Thin Backend, Rich Frontend

```
GET /novels/{id}/kb/graph
        │
        ▼
┌────────────────────────────────────────┐
│  router_graph.py  (thin — RULE-06)     │
│  service.get_graph(novel_id, user_id) │
└──────────┬─────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  graph_service.py: get_graph()                            │
│                                                           │
│  1. Fetch all entries for novel                           │
│     kb_repo.list_entries(novel_id, page_size=max_nodes)  │
│                                                           │
│  2. Fetch adjacency map                                  │
│     rel_repo.get_adjacency_map(novel_id)                  │
│                                                           │
│  3. Fetch all relationships                              │
│     For each entry: rel_repo.list_for_entry(entry_id)     │
│     (or: single query for all rels in novel)              │
│                                                           │
│  4. Build GraphNode list                                 │
│     - id, label, entity_type, status, tags, metadata      │
│     - degree = len(adjacency[entry_id])                   │
│                                                           │
│  5. Build GraphEdge list                                 │
│     - id, source, target, label, rel_type, direction      │
│                                                           │
│  6. Compute stats                                        │
│     - node_count, edge_count, isolated_count              │
│     - connected_components (via BFS)                       │
│     - entity_type_counts, rel_type_counts                 │
│                                                           │
│  7. Apply filter (if provided)                           │
│     - Filter nodes by entity_type                         │
│     - Filter edges by rel_type                            │
│     - Remove orphaned edges (source/target not in nodes)  │
│                                                           │
│  8. Return GraphResponse                                 │
└──────────────────────────────────────────────────────────┘
```

---

## 6. Data Flow

### 6.1 Graph Data Fetch Flow

```
User opens "Graph" tab in WorldBuilding
        │
        ▼
┌────────────────────────────────┐
│  WorldBuilding.tsx              │
│  sets viewMode = "graph"       │
│  renders KnowledgeGraphView    │
└──────────┬─────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  useKBGraph(novelId, filter)   │
│  → kbGraphApi.getGraph(...)    │
└──────────┬─────────────────────┘
           │ GET /novels/{id}/kb/graph?entity_types=character,location
           ▼
┌────────────────────────────────┐
│  router_graph.py               │
│  → service.get_graph(...)      │
└──────────┬─────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  GraphService.get_graph()                                │
│  → KBRepositoryProtocol.list_entries()                  │
│  → RelationshipRepositoryProtocol.get_adjacency_map()   │
│  → Build nodes, edges, stats                             │
│  → Return GraphResponse                                  │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  KnowledgeGraphView.tsx        │
│  Renders Cytoscape component   │
│  with nodes, edges, layout     │
└────────────────────────────────┘
```

### 6.2 Shortest Path Flow

```
User clicks "Find Path" → selects two entities
        │
        ▼
┌────────────────────────────────────────┐
│  KnowledgeGraphPathPanel.tsx            │
│  → kbGraphApi.getShortestPath(...)     │
└──────────┬─────────────────────────────┘
           │ GET /novels/{id}/kb/graph/shortest-path?source_id=X&target_id=Y
           ▼
┌────────────────────────────────────────┐
│  GraphService.get_shortest_path()      │
│  → BFS on adjacency map               │
│  → Return ShortestPathResponse        │
└────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│  KnowledgeGraphView.tsx                │
│  Highlights path nodes and edges       │
│  in the Cytoscape instance             │
└────────────────────────────────────────┘
```

### 6.3 Node Click Flow

```
User clicks a node in the graph
        │
        ▼
┌────────────────────────────────────────┐
│  KnowledgeGraphView.tsx                │
│  onNodeClick(nodeId)                   │
│  → Highlight connected edges           │
│  → Dim unconnected nodes               │
│  → Show entity details in side panel   │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│  useKBEntry(novelId, nodeId)           │
│  → kbApi.getEntry(novelId, nodeId)     │
│  → Display in KBDetailPanel            │
└────────────────────────────────────────┘
```

### 6.4 Edge Click Flow

```
User clicks an edge in the graph
        │
        ▼
┌────────────────────────────────────────┐
│  KnowledgeGraphView.tsx                │
│  onEdgeClick(edgeId)                   │
│  → Show relationship details popup     │
│  → Offer "Edit" or "Delete" actions    │
└────────────────────────────────────────┘
```

---

## 7. Frontend Architecture

### 7.1 Cytoscape.js Integration

**New dependencies** (added to `packages/web/package.json`):

| Package | Version | Purpose |
|---------|---------|---------|
| `cytoscape` | ^3.31 | Core graph rendering engine |
| `cytoscape-dagre` | ^2.5 | Hierarchical (DAG) layout extension |
| `dagre` | ^0.8 | Underlying DAG layout algorithm |

**NOT included** (unnecessary):

| Package | Why NOT |
|---------|---------|
| `cytoscape-cola` | The built-in `cose` layout is sufficient for force-directed. Cola adds 200KB for marginal improvement. |
| `cytoscape-cose-bilkent` | High-quality but 300KB+ — overkill for ≤500 nodes. |
| `cytoscape-panzoom` | Can be added later if needed. Scroll zoom + drag pan are built-in. |

**Layout strategy**:

| Layout | Implementation | When to use |
|--------|---------------|-------------|
| Force-directed | Cytoscape built-in `cose` layout | Default — organic, shows clusters |
| Hierarchical | `cytoscape-dagre` extension | When user selects "Hierarchical" — top-down by entity type |
| Concentric | Cytoscape built-in `concentric` layout | When user selects "Concentric" — hubs in center |
| Manual | User drag positions, stored in component state | When user drags nodes — positions are ephemeral (not persisted) |

### 7.2 Component Architecture

```
WorldBuilding.tsx
├── viewMode: "list" | "graph"  (new state)
│
├── viewMode === "list" (existing behavior)
│   ├── KBCategorySidebar
│   ├── KBEntryList
│   └── KBDetailPanel | KBAssistedCreationPanel | WorldbuildingAnalysisPanel | ConsistencyCheckPanel
│
└── viewMode === "graph" (new)
    ├── KBCategorySidebar (with "Graph" tab active)
    └── KnowledgeGraphView
        ├── Cytoscape instance (full height)
        ├── KnowledgeGraphControls (overlay, top-right)
        │   ├── Layout selector (cose / dagre / concentric)
        │   ├── Entity type filter (checkboxes)
        │   ├── Relationship type filter (checkboxes)
        │   └── Search input (find and highlight entity)
        ├── KnowledgeGraphPathPanel (overlay, bottom)
        │   └── Source/target selectors + "Find Path" button
        └── Side panel (conditional)
            └── KBDetailPanel (reused from list view)
```

### 7.3 State Management

All graph state is local to `KnowledgeGraphView` — no Zustand store needed.

```typescript
// KnowledgeGraphView internal state
const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
const [layout, setLayout] = useState<"cose" | "dagre" | "concentric">("cose");
const [entityTypeFilter, setEntityTypeFilter] = useState<Set<string>>(new Set());
const [relTypeFilter, setRelTypeFilter] = useState<Set<string>>(new Set());
const [searchQuery, setSearchQuery] = useState("");
const [pathResult, setPathResult] = useState<ShortestPathResponse | null>(null);
```

### 7.4 Cytoscape Stylesheet

**Location**: `packages/web/components/studio/kb/graph-styles.ts`

Node colors by entity type (matching existing `TYPE_ICONS` color scheme):

| Entity Type | Node Color | Shape |
|-------------|-----------|-------|
| character | `hsl(220, 70%, 55%)` (blue) | ellipse |
| location | `hsl(142, 50%, 45%)` (green) | rectangle |
| faction | `hsl(280, 60%, 55%)` (purple) | hexagon |
| concept | `hsl(30, 80%, 55%)` (orange) | diamond |
| object | `hsl(190, 60%, 50%)` (teal) | round-rectangle |
| setting | `hsl(45, 70%, 55%)` (amber) | triangle |
| system | `hsl(0, 60%, 55%)` (red) | octagon |
| timeline | `hsl(260, 50%, 55%)` (indigo) | veeline |

Edge styles:
- Default: `#999` color, 2px width, solid line
- Selected: `#3b82f6` (primary blue), 4px width
- Path highlight: `#f59e0b` (amber), 3px width, dashed line
- Directed: arrow on target end
- Mutual: no arrow

### 7.5 Performance: Level of Detail

When zoomed out (zoom < 0.5), simplify the graph:
- Hide edge labels
- Reduce node labels to first 3 characters
- Dim isolated nodes (opacity 0.3)

When zoomed in (zoom >= 0.5), show full detail:
- Full node labels
- Edge labels on hover
- All nodes at full opacity

This is handled in the Cytoscape stylesheet with zoom-dependent selectors:

```typescript
// In graph-styles.ts
{
  selector: "node",
  style: {
    label: "data(label)",
    "text-wrap": "ellipsis",
    "text-max-width": "80px",
    "font-size": "12px",
  },
},
{
  selector: "node[degree = 0]",
  style: {
    opacity: 0.4,
  },
},
```

---

## 8. Performance Considerations

### 8.1 Hard Limits

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Max nodes | 500 | Cytoscape.js performance degrades noticeably above 500 nodes |
| Max edges | 2000 | Edge rendering is more expensive than node rendering |
| Response payload | ~2MB | 500 nodes × ~200 bytes + 2000 edges × ~100 bytes ≈ 300KB JSON |
| Initial render | < 3 seconds | Target for 500-node graph with `cose` layout |

### 8.2 Backend Optimization

The `GraphService.get_graph()` method uses two efficient queries:

1. **`KBRepositoryProtocol.list_entries(novel_id, page_size=max_nodes)`** — Single paginated
   query. For the graph, we request all entries up to `max_nodes` in one call.

2. **`RelationshipRepositoryProtocol.get_adjacency_map(novel_id)`** — Single query that
   returns all relationships for the novel as `(source_id, target_id)` pairs. This is
   already optimized in the existing repository.

3. **Relationship details** — For edge labels and types, we need the full relationship
   objects. We add a new repository method `list_all_for_novel(novel_id)` that fetches
   all relationships for a novel in a single query (instead of N queries per entry).

**New repository method** (added to `RelationshipRepositoryProtocol`):

```python
async def list_all_for_novel(
    self,
    novel_id: uuid.UUID,
) -> list[KBRelationship]:
    """List all relationships for a novel in a single query.

    Used by GraphService to build edges efficiently.
    """
    ...
```

This is the only change to existing contracts — a single new method on an existing
protocol. No breaking changes.

### 8.3 Frontend Optimization

| Technique | Implementation |
|-----------|---------------|
| Lazy loading | Graph data fetched only when "Graph" tab is activated |
| Debounced resize | Cytoscape `resize()` debounced at 150ms |
| Level of detail | Simplified labels when zoom < 0.5 |
| Filter before render | Apply entity_type and rel_type filters before passing to Cytoscape |
| Memoized elements | `useMemo` for Cytoscape element array to prevent re-renders |
| Virtual viewport | Cytoscape only renders visible elements (built-in) |

### 8.4 Large Graph Warning

When the backend detects more than 500 entries for a novel, the `GraphStats` will include
a `node_count` that exceeds the filter's `max_nodes`. The frontend should display a warning:

> "This world has {node_count} entities. Showing the first {max_nodes}. Use filters to
> focus on specific entity types."

---

## 9. RULE-XX Compliance Matrix

| Rule | Status | How KB-008 Satisfies It |
|------|--------|-------------------------|
| **RULE-01b** | ✅ | No LLM calls. `GraphService` is pure data serialization — no agents, no models, no gateway. |
| **RULE-02** | ✅ | No prompts needed. Graph visualization is data transformation, not generation. |
| **RULE-03** | ✅ | `GraphServiceProtocol` in `graph_contracts.py` written before implementation. |
| **RULE-04** | ✅ | File sizes respected: service ~120 lines, router ~50 lines, schemas ~80 lines, contracts ~40 lines. |
| **RULE-05** | ✅ | Module boundaries: graph files in `apps/api/narrare/kb/` (same domain). No cross-module imports. |
| **RULE-06** | ✅ | One responsibility per file: router (delegates), service (serializes), schemas (models), contracts (protocols). |
| **RULE-07** | ✅ | Dependency direction: router → service → repos. No imports from apps/ to core/. |
| **RULE-08** | ✅ | No new external services. Cytoscape.js is a client-side library (npm dependency). |
| **RULE-09** | ✅ | All public functions fully typed. No `Any` in contracts. |
| **RULE-10** | ✅ | Tests planned: service unit tests, router integration tests, frontend component tests. |
| **RULE-11** | ✅ | All exception paths: log with structlog, raise typed errors. No bare `except: pass`. |
| **RULE-12** | ✅ | Service layer is the only public API. `GraphServiceProtocol` callable from WebUI, MCP, A2A, CLI. |
| **RULE-13** | ✅ | Not applicable — graph data is a single request/response, not a streaming operation. No SSE needed. |
| **RULE-14** | ✅ | No database model changes. No new tables. |
| **RULE-16** | ✅ | Frontend i18n: new translations for graph UI text in all 3 locales. |
| **RULE-17** | ✅ | API-Frontend contract: TypeScript types in `kb-graph.ts` match Pydantic schemas in `graph_schemas.py`. |
| **RULE-18** | ✅ | No hardcoded configuration. Layout options are user-selected, not hardcoded. |
| **RULE-19** | ✅ | `SessionDep` used in `dependencies.py` factory. |
| **RULE-20** | ✅ | Complete implementation: no stubs, no TODOs, no half-implementations. |

---

## 10. Work Plan

### 10.1 Layer Ordering

Implementation follows the dependency chain: **Backend → Frontend**.

| Phase | Step | Task | Files | Depends On | Est. Complexity |
|-------|------|------|-------|------------|-----------------|
| **Backend** | B1 | Define `GraphServiceProtocol` | `graph_contracts.py` | — | ★☆☆ (definitional) |
| **Backend** | B2 | Define graph schemas | `graph_schemas.py` | B1 | ★☆☆ (definitional) |
| **Backend** | B3 | Add `list_all_for_novel` to `RelationshipRepositoryProtocol` | `contracts.py` (modify) | — | ★☆☆ (add one method) |
| **Backend** | B4 | Implement `list_all_for_novel` in `RelationshipRepository` | `relationship_repository.py` (modify) | B3 | ★☆☆ (one query) |
| **Backend** | B5 | Implement `GraphService` | `graph_service.py` | B1, B2, B3 | ★★☆ (serialization + BFS) |
| **Backend** | B6 | Add `get_graph_service` to `dependencies.py` | `dependencies.py` (modify) | B5 | ★☆☆ (wiring) |
| **Backend** | B7 | Implement router | `router_graph.py` | B5, B6 | ★☆☆ (thin router) |
| **Backend** | B8 | Write service unit tests | `tests/unit/api/narrare/kb/test_graph_service.py` | B5 | ★★☆ (testing) |
| **Backend** | B9 | Write router integration tests | `tests/integration/api/narrare/kb/test_router_graph.py` | B7 | ★★☆ (testing) |
| **Frontend** | F1 | Add Cytoscape dependencies | `package.json` (modify) | — | ★☆☆ (npm install) |
| **Frontend** | F2 | Define TypeScript types + API client | `kb-graph.ts` | B2 | ★☆☆ (definitional) |
| **Frontend** | F3 | Create TanStack Query hooks | `useKBGraph.ts` | F2 | ★☆☆ (hooks) |
| **Frontend** | F4 | Create graph styles | `graph-styles.ts` | — | ★★☆ (styling) |
| **Frontend** | F5 | Create graph layouts | `graph-layouts.ts` | — | ★☆☆ (config) |
| **Frontend** | F6 | Create graph utilities (BFS, filtering) | `graph-utils.ts` | — | ★★☆ (algorithm) |
| **Frontend** | F7 | Create `KnowledgeGraphControls` | `KnowledgeGraphControls.tsx` | F4, F5 | ★★☆ (UI) |
| **Frontend** | F8 | Create `KnowledgeGraphPathPanel` | `KnowledgeGraphPathPanel.tsx` | F2, F6 | ★★☆ (UI) |
| **Frontend** | F9 | Create `KnowledgeGraphView` | `KnowledgeGraphView.tsx` | F2-F8 | ★★★ (main component) |
| **Frontend** | F10 | Integrate into `WorldBuilding.tsx` | `WorldBuilding.tsx` (modify) | F9 | ★★☆ (integration) |
| **Frontend** | F11 | Add "Graph" tab to `KBCategorySidebar` | `KBCategorySidebar.tsx` (modify) | F10 | ★☆☆ (button) |
| **Frontend** | F12 | Add i18n translations | `messages/{en,de,fr}/studio.json` | F10 | ★☆☆ (text) |

### 10.2 Dependency Graph

```
B1 ──→ B2 ──→ B5 ──→ B6 ──→ B7
                ↑                │
B3 ──→ B4 ─────┘                │
                                 │
B8 (after B5)                   B9 (after B7)

F1 ──→ (independent, npm install)

B2 ──→ F2 ──→ F3
F4 ──→ F7
F5 ──→ F7
F6 ──→ F8

F2 + F3 + F4 + F5 + F6 + F7 + F8 ──→ F9 ──→ F10 ──→ F11 + F12
```

### 10.3 Parallelization Opportunities

| Batch | Tasks | Specialist |
|-------|-------|------------|
| **Batch 1** | B1, B2, B3, F1 | Backend (contracts) + Frontend (npm install) |
| **Batch 2** | B4, B5, F2, F3, F4, F5, F6 | Backend (service) + Frontend (types, hooks, utils) |
| **Batch 3** | B6, B7, B8, F7, F8 | Backend (router + tests) + Frontend (controls, path panel) |
| **Batch 4** | B9, F9 | Backend (integration tests) + Frontend (main component) |
| **Batch 5** | F10, F11, F12 | Frontend (integration + i18n) |

### 10.4 Estimated Total Complexity

| Layer | Files | Est. Lines | Complexity |
|-------|-------|-----------|------------|
| Backend | 4 new, 3 mod | ~305 lines + ~150 lines tests | ★★☆ |
| Frontend | 8 new, 3 mod | ~760 lines | ★★★ |
| **Total** | **12 new, 6 mod** | **~1215 lines** | |

### 10.5 Definition of Done

- [ ] `GraphServiceProtocol` defined in `graph_contracts.py`
- [ ] `GraphResponse`, `GraphNode`, `GraphEdge`, `GraphStats`, `GraphFilter` schemas defined
- [ ] `list_all_for_novel` added to `RelationshipRepositoryProtocol` and implemented
- [ ] `GraphService.get_graph()` serializes entries + relationships as graph elements
- [ ] `GraphService.get_shortest_path()` implements BFS path finding
- [ ] `GET /novels/{id}/kb/graph` endpoint returns `GraphResponse`
- [ ] `GET /novels/{id}/kb/graph/shortest-path` endpoint returns `ShortestPathResponse`
- [ ] TypeScript types in `kb-graph.ts` match Pydantic schemas (RULE-17)
- [ ] Cytoscape.js renders graph with `cose`, `dagre`, and `concentric` layouts
- [ ] Node click highlights connections and shows entity details
- [ ] Edge click shows relationship details with edit/delete options
- [ ] Entity type filter works (checkboxes in controls)
- [ ] Relationship type filter works
- [ ] Search highlights matching entity
- [ ] Shortest path visualization works
- [ ] "Graph" tab in KBCategorySidebar switches to graph view
- [ ] i18n translations added for all 3 locales
- [ ] All RULE-XX constraints satisfied (see compliance matrix)
- [ ] No workarounds, no TODOs, no half-implementations

---

## Appendix A: BFS Shortest Path Algorithm

The shortest path algorithm is a standard BFS on the adjacency map. It runs on the
backend (not client-side) because:

1. The adjacency map is already loaded by `GraphService.get_graph()`.
2. Backend BFS is O(V + E) — fast for ≤500 nodes.
3. The result is small (a list of UUIDs) — no performance concern.
4. Keeping it server-side means MCP and A2A clients can also use it.

```python
from collections import deque

async def get_shortest_path(
    self,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> list[uuid.UUID] | None:
    """BFS shortest path between two entities."""
    adjacency = await self._rel_repo.get_adjacency_map(novel_id)

    # Convert string keys to UUIDs
    adj: dict[uuid.UUID, set[uuid.UUID]] = {}
    for k, v in adjacency.items():
        adj[uuid.UUID(k)] = {uuid.UUID(n) for n in v}

    if source_id not in adj and source_id not in {n for ns in adj.values() for n in ns}:
        return None  # Source not in graph
    if target_id not in adj and target_id not in {n for ns in adj.values() for n in ns}:
        return None  # Target not in graph

    visited: set[uuid.UUID] = {source_id}
    queue: deque[tuple[uuid.UUID, list[uuid.UUID]]] = deque([(source_id, [source_id])])

    while queue:
        current, path = queue.popleft()
        if current == target_id:
            return path

        for neighbor in adj.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None  # No path exists
```

## Appendix B: Cytoscape.js Dependency Justification

### Why Cytoscape.js?

| Criterion | Cytoscape.js | D3-force | vis-network | Sigma.js |
|-----------|-------------|----------|-------------|----------|
| Bundle size | ~300KB | ~50KB (force only) | ~200KB | ~150KB |
| Layout algorithms | 10+ built-in + extensions | Manual | 4 built-in | 2 built-in |
| Node/edge interaction | Rich event system | Manual | Good | Limited |
| TypeScript support | Official types | Official types | Community | Community |
| Performance (500 nodes) | Good | Good | Good | Excellent |
| Documentation | Excellent | Excellent | Good | Fair |
| Community | Large | Large | Medium | Small |
| React integration | `react-cytoscapejs` wrapper | Manual | Manual | Manual |

**Decision**: Cytoscape.js. It provides the best balance of layout options, interaction
support, and documentation. The bundle size is acceptable for a feature that loads
on-demand (only when the "Graph" tab is activated).

### Why NOT react-cytoscapejs?

The `react-cytoscapejs` wrapper adds a React component abstraction over Cytoscape, but:

1. It re-renders the entire Cytoscape instance on every prop change, which is slow for
   500+ elements.
2. It doesn't expose the full Cytoscape API (e.g., `cy.elements().layout()` for
   re-running layouts).
3. Direct Cytoscape usage with `useRef` + `useEffect` gives full control and better
   performance.

**Decision**: Use Cytoscape directly via `useRef` + `useEffect`, not the React wrapper.
This follows the same pattern as TipTap (direct API, not a React abstraction).

## Appendix C: SSE Streaming — Not Applicable

KB-008 does NOT use SSE streaming. Rationale:

1. **Not a generation feature**: Graph data is a single request/response — all data is
   available immediately. There is no streaming generation like LLM output.
2. **Not a long-running operation**: For ≤500 nodes, serialization takes <100ms.
3. **RULE-13 compliance**: `GraphServiceProtocol.get_graph()` returns `GraphResponse`
   directly. If streaming were needed in the future (e.g., for progressive loading of
   very large graphs), the method could accept `stream: bool` without breaking callers.
4. **No incremental data**: The graph is either complete or not — there's no partial
   state that benefits from streaming.

---

> **Specification approved by**: Architecture Specialist
> **Date**: 2026-05-26
> **Next review**: After GraphService implementation (Step B5)
