---
id: KB-006
title: "Worldbuilding Assistant"
status: planned
area: kb
mvp: false

ui_tooltip: "AI helps build and connect your story's world, factions, and systems."
ui_help_short: |
  Create rich, coherent worlds with AI assistance. Build locations, factions,
  magic systems, and technologies that connect naturally. The AI suggests
  connections, identifies gaps, and helps maintain consistency.
ui_help_long: |
  ## Worldbuilding Assistant

  The Worldbuilding Assistant helps you create and connect the elements that
  make your story world feel real and lived-in.

  **What you can build:**

  **Locations** 📍
  - Cities, buildings, infrastructure
  - Natural terrain, landmarks
  - Magical spaces, underground, mobile locations

  **Factions** 🏛️
  - Political entities, governments, movements
  - Military organizations, armies
  - Social groups, religions, cultures

  **Objects** ⚔️
  - Weapons, artifacts, tools
  - Vehicles, mounts
  - Technological devices

  **Systems** ⚙️
  - Magic systems with rules and costs
  - Technologies and their implications
  - Economies, laws, social hierarchies

  **Timelines** 📅
  - World history before your story
  - Chronology of events
  - Character histories and backstories

  **AI assistance:**
  - Suggest connections between entities
  - Identify gaps in your worldbuilding
  - Flag inconsistencies (geography, politics, technology)
  - Generate names and details
  - Explore implications of your choices

  **Worldbuilding view:**
  Visual browser showing all non-character entities. Filter by type, search by
  name, explore relationships. Click any entity to see details and connections.

  **Best practices:**
  - Start broad (geography, major factions) before details
  - Document rules clearly for systems
  - Show world through story, not info-dumps
  - Focus on story-relevant areas first

  The more interconnected your worldbuilding, the richer your story becomes.
ui_available_in: [kb]

service: kb/worldbuilding_service.py
contract: kb/contracts.py#WorldbuildingProtocol
router: kb/router.py
prompt: core/prompts/_bundled/kb/en/worldbuild
requires: [KB-001]
---

# KB-006 — Worldbuilding Assistant

## What it does

Specialized KB interface for worldbuilding entities (locations, factions, objects,
systems, timelines). Provides AI-assisted creation, gap identification, connection
suggestions, and consistency checking for story world elements.

## Why it exists

Characters get most of the attention, but the world they inhabit is equally
important. Writers struggle with worldbuilding consistency — forgetting
geography, contradicting political relationships, or leaving systems undefined.
The Worldbuilding Assistant makes building coherent worlds easier.

## How it works (User perspective)

1. Open Knowledge Base → "Worldbuilding" tab
2. See all non-character entities organized by type
3. Create new entities with AI assistance:
   - Describe what you want
   - AI asks clarifying questions
   - AI generates structured entry
4. Explore relationships in visual graph view
5. Click "Find Gaps" — AI identifies what's missing:
   - Locations without factions
   - Factions without territories
   - Systems without rules
6. Click "Check Consistency" — find contradictions

The worldbuilding view focuses on connections and implications — how a magic
system affects politics, how geography influences trade routes, etc.

## How it works (Technical)

**Entry point:** `kb/router.py` → Worldbuilding-specific routes
**Service:** `WorldbuildingService` in `kb/worldbuilding_service.py`
**Contract:** `WorldbuildingProtocol` in `kb/contracts.py`
**LLM Intents:** `LLMIntent.KB_CREATE`, `LLMIntent.KB_IMPROVE`

**Worldbuilding-specific features:**

**Gap detection:**
- Analyze existing entities for missing connections
- Identify undefined elements (faction with no territory, system with no rules)
- Suggest entities to create based on story needs
- Prioritize by story relevance (entities used in chapters first)

**Connection suggestions:**
- Find relationships between entities (location controlled by faction)
- Explore implications (if magic has cost, how does society adapt?)
- Generate network of connections

**Consistency checking:**
- Geography: distances, terrain consistency
- Politics: faction relationships, territorial claims
- Economics: trade routes, resource distribution
- Technology/magic: system rules and implications

**Specialized templates per type:**
- Location: terrain, climate, population, government, connections
- Faction: goals, structure, resources, enemies, allies
- Object: appearance, properties, history, owner
- System: rules, costs, limitations, implications
- Timeline: events, dates, participants, consequences

## Constraints & Edge Cases

- Gap detection requires at least 3 entities of any type to work well
- Connection suggestions may propose relationships you intentionally omitted
- Consistency checking limited to explicit facts (won't catch everything)
- Large worlds (100+ entities) may have slower gap analysis
- AI may suggest genre-inappropriate elements (user controls genre)

## Related Features

- [KB-001](KB-001-entity-management.md) — Base entity CRUD
- [KB-008](KB-008-knowledge-graph.md) — Visual relationship graph
- [KB-004](KB-004-kb-consistency.md) — Consistency checking
- [PLAN-004](../planning/PLAN-004-timeline.md) — Timeline management

## Status & History

- `project-init` — Added to registry as planned feature
