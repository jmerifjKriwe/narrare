---
id: INFRA-006
title: "A2A Integration"
status: planned
area: infra
mvp: false

ui_tooltip: "Connect AI agents to Narrare's writing capabilities via A2A protocol."
ui_help_short: |
  Narrare supports the Agent2Agent (A2A) protocol.
  This enables AI agents to collaborate with Narrare's novel-writing capabilities.
ui_help_long: |
  A2A is an open protocol that standardizes agent-to-agent communication. While MCP connects agents to tools, A2A connects agents to other agents — enabling conversational, stateful interactions.
  Your AI agent discovers Narrare via its Agent Card, sends tasks, and processes results iteratively.
ui_available_in: ["api", "cli"]

# Implementation paths intentionally empty — A2A is planned (post-MVP),
# blocked on Q-002 (A2A streaming decision). No skeleton exists yet; paths
# will be set when the adapter spec is written. See AUFG-01-03 / AUFG-03-04.
service: ""
contract: ""
router: ""
prompt: ""
requires: []
---

# [INFRA-006] — A2A Integration

## What it does

Narrare supports the Agent2Agent (A2A) protocol, enabling external AI agents to collaborate with Narrare's novel-writing capabilities, tools, and Knowledge Base.

## Why it exists

To allow external, third-party, or personalized AI agents to natively access and orchestrate Narrare's writing and analysis capabilities in a conversational and stateful manner.

## How it works (User perspective)

1. The writer or developer starts the A2A server.
2. An external AI agent discovers Narrare via its Agent Card at /.well-known/agent-card.json.
3. The agent sends a task with a `skill_id` in the metadata.
4. Narrare processes the task and returns results as artifacts, supporting multi-turn interactions.

## How it works (Technical)

**Entry point:** _planned_ — no implementation exists yet. The future A2A
adapter will live under `apps/api/narrare/a2a/` following the current
router schema (`apps/api/narrare/<domain>/router.py`), not the legacy
`apps/api/routers/` schema.
**Service:** A2A integration server handling standardized requests.
**Streaming:** yes (for stateful interactions) — pending Q-002 decision.

Narrare exposes skills covering the full novel-writing workflow to external agents (writing, KB CRUD, analysis, etc.).

## Constraints & Edge Cases

- Status: **planned, blocked on [Q-002](../../architecture/questions/INDEX.md)** (A2A streaming decision). No server skeleton exists yet.
- Requires the A2A server to be running (`just run-a2a`) — recipe to be added with the implementation.
- Relies on external AI agents understanding and supporting the A2A protocol.

## Related Features

- [INFRA-008](../infra/INFRA-008-mcp-integration.md) — MCP Integration (similar tool-exposure interface)

## Status & History

- `2026-05-19` — Added to registry
