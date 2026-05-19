---
id: INFRA-008
title: "MCP Integration"
status: planned
area: infra
mvp: false

ui_tooltip: "Connect Claude Desktop and other MCP clients to Narrare."
ui_help_short: |
  Use Narrare's full power directly in Claude Desktop and other MCP-compatible tools.
  Connect Narrare's API as an MCP server to access writing, analysis, and KB features.
ui_help_long: |
  MCP (Model Context Protocol) lets you connect Narrare to Claude Desktop and other AI tools. Instead of switching between your writing app and Claude, you can ask Claude to continue writing, manage your knowledge base, or check consistency -- all from within the conversation.
  Narrare exposes dozens of MCP tools organized into categories like Knowledge Base, Writing, Context, Analysis, and more.
ui_available_in: ["mcp"]

service: tools/mcp-server/narrare_mcp/server.py
contract: ""
router: ""
prompt: ""
requires: []
---

# [INFRA-008] — MCP Integration (Claude Desktop)

## What it does

Exposes Narrare's full suite of capabilities (writing, KB CRUD, analysis) as tools via the Model Context Protocol (MCP), allowing external clients like Claude Desktop to interact natively with Narrare projects.

## Why it exists

Many writers use tools like Claude Desktop for brainstorming and assistance. By exposing Narrare via MCP, writers can leverage their novel's contextual Knowledge Base and specialized endpoints directly within their favorite LLM interfaces, bridging the gap between chat assistants and structured writing software.

## How it works (User perspective)

1. The user configures Claude Desktop with the Narrare MCP server using an authentication token.
2. The user chats with Claude and asks it to "create a new character" or "beta read chapter 5".
3. Claude automatically invokes the corresponding MCP tools exposed by Narrare.
4. Narrare processes the requests and returns structured results directly into the chat.

## How it works (Technical)

**Entry point:** `tools/mcp-server/narrare_mcp/server.py`
**Service:** MCP Server wrapping Narrare API endpoints.
**Streaming:** stdio or http transport modes.

The MCP server connects to the running Narrare API, bridging standard MCP tool call requests to standard HTTP API calls.

## Constraints & Edge Cases

- Requires a valid authentication token (`narrare auth login`).
- Requires the Narrare API to be running and accessible by the MCP server.
- AI-powered tools executed via MCP consume API calls to the LLM provider configured in Narrare (or the client, depending on architecture).

## Related Features

- [INFRA-006](../infra/INFRA-006-a2a-integration.md) — A2A Integration
- [ASSIST-003](../ai_assist/ASSIST-003-chat.md) — AI Chat Assistant within Narrare itself

## Status & History

- `2026-05-19` — Added to registry
