<!-- Context: narrare-dev/concepts/project-vision | Priority: critical | Source: docs/reference/project-vision.md | Updated: 2026-06-12 -->

# Project Vision

> Complete reference: `docs/reference/project-vision.md`

## One Sentence

Narrare is an AI-assisted writing environment that helps authors write better stories — **without replacing the author**.

## Why Narrare Exists

Writers face three challenges that current AI tools don't solve:

1. **Cognitive overhead** — Tracking 30 characters, their histories, their contradictions. The tavern on the east side in chapter 2 somehow appears on the west side in chapter 14.
2. **The blank page** — Getting unstuck when the last sentence stopped making sense.
3. **The loneliness** — Most writers write alone. A writing partner who has read everything, remembers it all, and gives honest feedback at 2am does not exist.

Current tools either generate for you (replacing), require manual context pasting (no memory), offer generic feedback (no context), or break flow with clunky interfaces.

## What Narrare Is

A **writing environment** (not just a tool) — a space that knows your world, your history, your style. Available when needed, invisible when not.

- **Knowledge Base** — Living document of every character, location, faction. AI helps build it and reads it before every interaction.
- **Writing Context** — Before generating anything, Narrare assembles: KB entries, chapter summaries, style profile, narrative voice.
- **Editor** — Inline suggestions, voice checks, consistency analysis — on demand, never pushed.
- **Feedback Layer** — Beta reader simulation, POV analysis, readability — in context of your specific manuscript.
- **Planning Layer** — Scene planning, gap analysis, timeline tracking, structure visualization.

## What Narrare Is Not

- **Not an AI that writes your book** — Generates when asked, never auto-completes
- **Not a cloud service** — Runs locally, your data on your machine, AI calls to your provider
- **Not one-size-fits-all** — Prompts customizable per-project/per-user/per-feature, models configurable per task

## Target Users

**Primary:** Serious hobby or independent authors who have a story they care about, take writing seriously, and found existing AI tools too generic.

**Secondary:** Professional authors who want cognitive overhead reduction, consistency checking, and 2am feedback — not generation.

**Not:** Users who want AI to "write me a story about dragons."

## The KB — Core to Everything

Without the KB, Narrare is just another LLM wrapper. With it, Narrare has persistent, structured knowledge of your specific story world assembled into context for every AI operation.

Three layers:
1. **Structured entities** — Explicitly managed: characters, locations, factions, objects. Type-specific templates, status lifecycle.
2. **Knowledge Graph** — Auto-maintained: facts extracted from chapters and KB entries. Nodes are entities, edges are relationships.
3. **Memory** — Accumulated: writing preferences, rejected suggestions, style patterns. Managed via mem0. Persists across sessions.

## Interface Strategy

| Phase | Interface | Status |
|-------|-----------|--------|
| Phase 1 | WebUI (browser-based, full-featured) | **Current** |
| Phase 2 | MCP (tools for AI coding assistants) | Planned |
| Phase 3 | A2A (agent-to-agent collaboration) | Planned |
| Phase 4 | CLI (terminal workflow) | Possible |

Architecture: Phases 2–4 add transport adapters, not new services.

## Design Principles

1. **Writer's flow is sacred** — Everything on demand, nothing pushed
2. **Local first** — Manuscript and KB on your machine
3. **Customizable at every level** — Prompts, models, templates, personas
4. **Transparent AI** — Author always knows when AI is involved, every action explicit and undoable
5. **Graceful degradation** — Editor works without AI provider, session runs without mem0, writing works without KB

**Related**: `narrare-dev/lookup/feature-index`, `narrare-dev/lookup/mvp-plan`, `narrare-dev/lookup/tech-stack`
