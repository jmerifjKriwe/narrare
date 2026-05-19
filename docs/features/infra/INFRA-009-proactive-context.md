---
id: INFRA-009
title: "Proactive Context Loading"
status: planned
area: infra
mvp: false

ui_tooltip: "Automatically suggest relevant KB entries based on chapter content."
ui_help_short: |
  Automatically suggests relevant KB entries when you open a chapter, based on your writing patterns.
  Anticipates what you need before you start writing.
ui_help_long: |
  Proactive Context Loading watches what you write and anticipates what you need. When you open a chapter, the system analyzes its content, finds the most relevant Knowledge Base entries, and presents them before you start writing. Over time, it learns which KB entries you actually use and prioritizes them in future suggestions.
ui_available_in: ["editor", "cli", "mcp", "api"]

service: packages/core/context/proactive_service.py
contract: packages/core/context/contracts.py#ProactiveContextService
router: apps/api/routers/context/proactive.py
prompt: ""
requires: []
---

# [INFRA-009] — Proactive Context Loading

## What it does

Automatically suggests relevant Knowledge Base entries when a writer opens a chapter. It ranks suggestions based on semantic relevance to the chapter text, historical usage patterns, and recency, learning from implicit and explicit user feedback over time.

## Why it exists

Writers shouldn't have to manually search for and pin relevant character profiles or locations every time they write a scene. Proactive Context Loading removes this friction by surfacing the right context exactly when it's needed, preventing consistency errors and saving time.

## How it works (User perspective)

1. The writer opens a chapter in the editor.
2. The "Proactive Suggestions" panel appears, listing 5-10 highly relevant KB entries.
3. The writer can view snippets, accept (pin) useful entries, or dismiss irrelevant ones.
4. Over time, the system learns from the writer's accept/dismiss behavior to improve future recommendations.

## How it works (Technical)

**Entry point:** `apps/api/routers/context/proactive.py` → `POST /api/v1/context/proactive/{chapter_id}`
**Service:** `ProactiveContextService.suggest()`
**Contract:** `ProactiveContextServiceProtocol`
**Streaming:** no

Uses a three-stage pipeline:
1. Content analysis (entity/theme extraction)
2. KB search (pgvector embedding search + graph traversal)
3. Learning and prioritization (weights relevance, usage frequency, and recency)

## Constraints & Edge Cases

- Requires chapters to have some text or valid frontmatter for initial accurate suggestions.
- The usage weighting takes time (several chapters) to become highly personalized.
- Feedback data is stored locally per project.

## Related Features

- [INFRA-003](../infra/INFRA-003-context-assembly.md) — The core context assembly system
- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Used for semantic matching of entries

## Status & History

- `2026-05-19` — Added to registry
