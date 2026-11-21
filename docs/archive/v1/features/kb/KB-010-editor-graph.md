---
id: KB-010
title: "Editor-Integrated Knowledge Graph"
status: idea
area: kb
mvp: false

ui_tooltip: "See entity relationships while you write."
ui_help_short: |
  A compact knowledge graph overlay in the editor sidebar that shows relevant
  entity connections while you write, helping you maintain consistency.
ui_help_long: |
  While writing, the Knowledge Graph sidebar shows which characters, locations,
  and concepts are connected. Hover over a node to see its details without
  leaving the editor.
ui_available_in: [editor]

service: ~
contract: ~
router: ~
prompt: ~
requires: [KB-008, WRITE-001]
---

# KB-010 — Editor-Integrated Knowledge Graph

## What it does

Shows a compact, interactive knowledge graph visualization in the editor's
metadata sidebar, displaying entities relevant to the current chapter.

## Why it exists

Writers currently must switch between the editor and the Worldbuilding view
to check entity details or relationships. Context switching breaks flow.

## How it works (User perspective)

1. Writer opens the editor metadata sidebar
2. A mini knowledge graph shows entities mentioned in the current chapter
3. Clicking a node shows entity details in an inline panel
4. Relationships between entities are shown as edges

## How it works (Technical)

Not yet specified. Would use existing `KnowledgeGraphView` component with
chapter-scoped filtering.

## Constraints & Edge Cases

- Graph must load fast enough not to block writing
- Large entity sets need clustering/filtering
- Touch device support needed

## Related Features

- [KB-008](KB-008-knowledge-graph.md) — Full knowledge graph view
- [WRITE-014](../writing/WRITE-014-context-inspector.md) — Context inspector shows what AI uses

## Status & History

- `2026-06-02` — Added as idea from CR-07 UX audit finding
