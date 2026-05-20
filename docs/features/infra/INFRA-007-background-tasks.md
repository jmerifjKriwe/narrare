---
id: INFRA-007
title: "Background Tasks"
status: in progress
area: infra
mvp: false

ui_tooltip: "Monitor and manage asynchronous background processing tasks."
ui_help_short: |
  Monitor and manage background processing tasks such as embedding generation and knowledge graph processing.
  These tasks run asynchronously so you can continue writing without waiting.
ui_help_long: |
  Narrare processes several tasks in the background using Celery workers, including embedding generation, knowledge graph processing, and chapter summarization.
  The Background Tasks panel shows queue status, coverage statistics, and allows you to retry failed tasks.
ui_available_in: ["editor", "cli", "mcp"]

service: packages/core/tasks/task_service.py
contract: packages/core/tasks/contracts.py
router: apps/api/routers/tasks.py
prompt: ""
requires: []
---

# [INFRA-007] — Background Tasks

## What it does

Monitors and manages asynchronous background processing tasks such as embedding generation, knowledge graph processing, and chapter summarization without blocking the writing experience.

## Why it exists

Expensive operations like embedding generation and graph traversal take time and should not interrupt the creative flow. Background Tasks allows Narrare to perform these heavy tasks asynchronously while giving the writer visibility into their progress.

## How it works (User perspective)

1. The writer performs an action (e.g., saves a chapter, updates a character).
2. Narrare offloads processing to background workers.
3. The writer opens the Background Tasks panel to see live counts of pending, processing, done, and failed tasks.
4. The writer can manually trigger a retry of failed tasks or monitor embedding coverage.

## How it works (Technical)

**Entry point:** `apps/api/routers/tasks.py`
**Service:** Background task processing via Celery or similar async queues.
**Contract:** `TaskServiceProtocol`
**Streaming:** no

Exposes endpoints for queue status, statistics, and reprocessing.

## Constraints & Edge Cases

- Failed tasks are automatically retried with exponential backoff.
- Large imports may heavily load the background workers.

## Related Features

- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Embeddings generated via background tasks
- [KB-008](../kb/KB-008-knowledge-graph.md) — Knowledge graph extraction handled in the background

## Status & History

- `2026-05-19` — Added to registry
