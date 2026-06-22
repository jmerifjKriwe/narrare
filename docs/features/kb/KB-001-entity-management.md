---
id: KB-001
title: "KB Entity Management"
status: implemented
area: kb
mvp: true

ui_tooltip: "Create and manage characters, locations, factions, and story elements."
ui_help_short: |
  The Knowledge Base (KB) is where you define the people, places, and things
  that populate your story. Organized entries ensure the AI remembers details
  consistently and can suggest relevant context when you write.
ui_help_long: |
  ## Knowledge Base Entity Management

  Your Knowledge Base is the structured memory of your story world. Every
  character, location, faction, object, system, and timeline lives here —
  organized, searchable, and available to the AI whenever it writes.

  **Entity Types:**

  **Characters** 👤
  The people who populate your story.
  - Identity: Name, aliases, age, role
  - Appearance: Physical description, distinctive features
  - Personality: Traits, motivations, fears, goals
  - Background: History, relationships, formative events
  - Voice: Speech patterns, vocabulary, verbal tics
  - Arc: Character development trajectory

  **Locations** 📍
  Places where scenes occur.
  - Built: Cities, buildings, infrastructure
  - Natural: Terrain, water features, landmarks
  - Special: Magical spaces, underground, mobile

  **Factions** 🏛️
  Organized groups with goals and structures.
  - Political: Governments, movements, treaties
  - Military: Armies, militias, guards
  - Social: Religions, economic groups, cultures

  **Objects** ⚔️
  Significant items with properties and histories.
  - Weapons, artifacts, tools
  - Vehicles, mounts, flying machines
  - Technological devices

  **Systems** ⚙️
  Abstract structures that define how your world works.
  - Magic systems with rules and costs
  - Technologies and capabilities
  - Economies, legal systems, social hierarchies

  **Timelines** 📅
  Temporal structures and event sequences.
  - World history before story
  - Story chronology
  - Character histories

  **Creation Methods:**
  - **AI Interview**: Guided questions to develop rich entries
  - **Manual Entry**: Direct input with structured fields
  - **From Templates**: Quick creation from archetypes

  **Best Practices:**
  - Start with core entities (protagonist, key locations)
  - Use AI interviews for deep development
  - Link related entities for better context
  - Keep entries updated as story evolves
ui_available_in: [kb]

service: kb/service.py
contract: kb/contracts.py#KBServiceProtocol
router: kb/router.py
prompt: core/prompts/_bundled/kb
requires: [INFRA-001, INFRA-002, INFRA-003]
---

# KB-001 — KB Entity Management

## What it does

CRUD operations for Knowledge Base entities across 6 types (characters, locations,
factions, objects, systems, timelines). Provides structured storage, search,
relationships, and AI-assisted creation through guided interviews.

## Why it exists

Without a Knowledge Base, the AI has no persistent memory of your story world.
It would forget character details, contradict location descriptions, and miss
opportunities to reference established facts. The KB ensures consistency and
enables context-aware AI assistance.

## How it works (User perspective)

1. Click "New Entry" in Knowledge Base panel
2. Choose entity type (Character, Location, etc.)
3. Select creation method:
   - **AI Interview**: Answer questions, AI builds structured entry
   - **Manual**: Fill in fields directly
   - **Template**: Start from archetype
4. Add relationships to other entities
5. Save — entry is now available to all AI features

Edit anytime. Changes reflect immediately in AI context. Search by name,
tags, or content. Link entities together for rich relationship graphs.

## How it works (Technical)

**Entry point:** `kb/router.py` → `POST /api/v1/kb/entities`
**Service:** `KBService` in `kb/management_service.py`
**Contract:** `KBServiceProtocol` in `kb/contracts.py`
**Models:** SQLAlchemy models in `kb/models.py`
**Repository:** `KBRepository` in `kb/repository.py`
**LLM Intent:** `LLMIntent.KB_CREATE`, `LLMIntent.KB_IMPROVE`

**Entity schema (common fields):**
```python
class KBEntry:
    id: UUID
    entity_type: EntityType  # character, location, etc.
    name: str
    content: str  # Markdown with YAML frontmatter
    metadata: dict  # type-specific fields
    relationships: list[Relationship]
    tags: list[str]
    created_at: datetime
    updated_at: datetime
```

**AI Interview flow:**
1. User initiates interview for entity type
2. Service generates interview questions based on type
3. User answers questions (iterative)
4. AI structures responses into entry fields
5. User reviews and edits
6. Entry saved to database

**Search capabilities:**
- Name search (exact match, fuzzy match)
- Full-text search (content)
- Tag filter
- Entity type filter
- Relationship traversal (find connected entities)

## Constraints & Edge Cases

- Maximum entry size: 100KB content
- Relationship depth limited to 5 hops for performance
- Circular relationships allowed but warned
- Deleted entities: relationships cascade or preserve based on user choice
- AI interview requires LLM to be available
- Very large KBs (1000+ entries) may have slower search
- **KB lifecycle (rename / deprecate / delete) is observer-notified** per
  [ADR-050](../../architecture/decisions/ADR-050-cross-feature-context-contracts.md).
  Consumers (Timeline, Storyboard, Chapter frontmatter) register a
  `KBEntityLifecycleObserver` and are notified when an entity is
  renamed, deprecated, or hard-deleted. Hard delete remains hard
  delete (no `deleted_at` column); consumers that need tombstone
  semantics implement them in their own storage and surface a
  `RefIntegrityIssue(reason="deleted_ref_without_tombstone")`.

## Related Features

- [KB-002](KB-002-kb-session.md) — Interactive sessions use these entities
- [KB-005](KB-005-kb-suggest.md) — Suggestions search these entities
- [KB-008](KB-008-knowledge-graph.md) — Visualizes entity relationships
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context includes KB entries
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Writing consumes KB context
- [ADR-050](../../architecture/decisions/ADR-050-cross-feature-context-contracts.md) — Cross-feature ref lifecycle contract. KB entity lifecycle changes (rename, deprecate, hard delete) emit observer events to all registered consumers.

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-24` — Marked as implemented. CRUD, search, relationships, templates, @mentions, 8 entity types, frontend editor all present. AI Interview creation mode moves to KB-002.
- `2026-06-18` — ADR-050 specified the cross-feature ref lifecycle contract. KB entity lifecycle (rename, deprecate, delete) will emit `KBEntityLifecycleObserver` events once Phase C of ADR-050 lands. Until then, hard delete stays destructive and consumers must rely on read-side `CrossFeatureRefIndex` checks at consistency-check time.
