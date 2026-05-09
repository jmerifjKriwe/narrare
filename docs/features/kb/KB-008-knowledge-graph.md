---
id: KB-008
title: "Knowledge Graph Visualization"
status: planned
area: kb
mvp: false

ui_tooltip: "Visual browser of entity relationships in your story world."
ui_help_short: |
  Explore your story world as an interactive graph. See how characters
  connect to locations, factions to each other, and how everything relates.
  Click nodes to view entries, drag to rearrange, zoom to explore.
ui_help_long: |
  ## Knowledge Graph Visualization

  The Knowledge Graph is a visual map of your story world — every character,
  location, faction, and connection displayed as an interactive network.

  **What you can do:**

  **Explore connections**
  - Click any entity to see its relationships
  - Highlight paths between entities (show how X connects to Y)
  - Filter by type (show only characters, only locations)
  - Find isolated entities (missing connections)

  **Understand your world**
  - See faction alliances and conflicts at a glance
  - Track character relationship networks
  - Visualize location connections and travel routes
  - Identify entities that are hubs (many connections)

  **Edit relationships**
  - Click connection lines to edit relationships
  - Drag to create new connections between entities
  - Right-click to delete relationships

  **Layout options:**
  - **Force-directed**: Entities repel/attract based on relationships
  - **Hierarchical**: Top-down by entity type
  - **Concentric**: Most connected entities in center
  - **Manual**: Arrange entities yourself

  **Navigation:**
  - Scroll to zoom in/out
  - Click and drag to pan
  - Double-click entity to open its KB entry
  - Search to find and highlight entities

  **Export:**
  - Save graph as PNG for reference
  - Export as SVG for editing
  - Print for offline planning

  The graph updates automatically as you add or edit KB entries.

  *Note: Performance optimized for up to 500 entities. Larger worlds may be
  slow to render — use filters to focus on specific areas.*
ui_available_in: [kb]

service: graph/service.py
contract: graph/contracts.py#GraphServiceProtocol
router: graph/router.py
prompt: ~
requires: [KB-001]
---

# KB-008 — Knowledge Graph Visualization

## What it does

Interactive visualization of KB entities and their relationships. Force-directed
graph layout with filtering, path highlighting, and direct manipulation. Powered
by Cytoscape.js with PostgreSQL backend.

## Why it exists

Text-based KB browsing misses the big picture. Writers struggle to remember
how everyone connects — which factions are allied, which characters know each
other, how locations relate. Visual graph makes connections obvious and helps
discover gaps.

## How it works (User perspective)

1. Open Knowledge Base → "Graph" tab
2. See all entities as nodes, relationships as lines
3. Interact:
   - Click entity → highlight connections, show details
   - Drag entity → reposition (stays where you put it)
   - Scroll → zoom in/out
   - Click + drag background → pan
4. Use controls:
   - Filter by entity type
   - Search for entity (highlights it)
   - Choose layout (force, hierarchical, manual)
   - Export as image

Click any entity to open its full KB entry. Click any relationship line to
edit or delete it.

## How it works (Technical)

**Entry point:** `graph/router.py` → `GET /api/v1/graph/nodes`, `GET /api/v1/graph/edges`
**Service:** `GraphService` in `graph/service.py`
**Frontend:** Cytoscape.js for rendering
**Data source:** KB entries and relationships from KB-001

**Graph elements:**
```python
class GraphNode:
    id: UUID  # KB entry ID
    label: str  # Entity name
    type: EntityType  # character, location, etc.
    metadata: dict  # Additional display info

class GraphEdge:
    id: str
    source: UUID  # From entity ID
    target: UUID  # To entity ID
    label: str  # Relationship type
    weight: float  # For visual thickness
```

**Layout algorithms:**
- **Force-directed**: Cytoscape's cola layout — physics-based
- **Hierarchical**: Dagre layout — topological
- **Concentric**: Custom — by connection count
- **Manual**: User positions saved to database

**Performance:**
- Lazy loading: fetch only visible entities for large graphs
- Level of detail: simplify labels when zoomed out
- Pagination: max 500 nodes rendered at once
- Clustering: group highly-connected subgraphs

**Path highlighting:**
Find shortest path between two entities using BFS. Highlight path nodes
and edges in distinct color. Display path length and relationship sequence.

## Constraints & Edge Cases

- **Node limit:** 500 nodes maximum for performance (UI warning)
- **Edge limit:** 2000 edges maximum (filter by relationship type if exceeded)
- **Rendering:** Requires WebGL (most modern browsers)
- **Mobile:** Touch gestures supported but limited screen space
- **Large graphs:** Initial render may take 5-10 seconds
- **Memory:** Browser tab may use 500MB+ for large graphs

## Related Features

- [KB-001](KB-001-entity-management.md) — Data source
- [KB-006](KB-006-worldbuilding.md) — Worldbuilding context
- [CONS-001](../consistency/CONS-001-checker.md) — Relationship consistency

## Status & History

- `project-init` — Added to registry as planned feature
