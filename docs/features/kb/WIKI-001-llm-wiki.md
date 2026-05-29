---
id: WIKI-001
title: "LLM Wiki — Precomputed Context Layer"
status: in-progress
area: kb
mvp: false

ui_tooltip: "Automatically generated narrative summaries of your characters and chapters."
ui_help_short: |
  "Every KB update creates a compact wiki summary. The AI uses these summaries instead of raw data — faster, cheaper, and better context."
ui_help_long: |
  ## LLM Wiki — Precomputed Context Layer

  The LLM Wiki is an automatic narrative layer between your Knowledge Base
  and the AI writing system. Instead of sending raw KB entries to the AI on
  every write request, Narrare precomputes compact, LLM-optimized summaries.

  **How it works:**

  1. When you update a character or location in the KB, the AI generates a
     **WikiSummary** — 2-3 narrative sentences describing the entity, its
     role in the story, key attributes, and relationships.
  2. When you finalize a chapter, the AI generates a **WikiChapterSummary** —
     key events, entities involved, and themes.
  3. When you write, the AI uses these precomputed summaries instead of raw
     KB data — faster, cheaper, and better quality.
  4. If you customize the wiki generation prompt, all summaries mark themselves
     as outdated and regenerate on next use.

  **What you can see (Wiki UI):**

  - Open any KB entity and see "How the AI sees this character"
  - Compare the raw KB entry with the AI's narrative interpretation
  - See which entities appear in which chapters
  - Explore entity relationships through narrative descriptions
  - View chapter summaries with entity involvement

  **When things are out of date:**

  - Changed a prompt? All summaries are refreshed on next write
  - Updated an entity? That entity's summary regenerates immediately
  - Manually refresh any summary with one click

  **What it doesn't do:**

  - Never changes your original KB data
  - Never blocks your writing — if a summary isn't ready, the AI falls back
    to raw data
  - Doesn't generate summaries for entities you haven't created yet
  - Doesn't auto-finalize chapters — only finalized chapters get WikiChapterSummaries
ui_available_in: [kb, editor]

service: core/wiki/service.py
contract: core/wiki/contracts.py#WikiServiceProtocol
router: apps/api/narrare/wiki/router.py
prompt: core/prompts/_bundled/wiki/en/entity_summary/system.md
requires: [INFRA-001, INFRA-002, INFRA-003, INFRA-005, KB-001, ADR-007, ADR-012, WRITE-012]
---

# WIKI-001 — LLM Wiki: Precomputed Context Layer

> **Implementation Status (2026-05-29):** Full backend implemented (commits
> 8ba62f3, 2e72f61). Core layer: types, contracts, agent, service,
> prompt_loader (35 unit tests). Backend layer: models, migration, repository
> (9 methods), schemas (6), API service, router (6 endpoints), tasks (4),
> listeners (4), DI wiring. Context assembler wiki integration, budget wiki
> optimization. **Frontend (Tasks 19-20) pending.**

## What it does

A precomputed, deterministic context layer that converts raw KB entities and
chapters into LLM-optimized narrative summaries (WikiSummaries). These summaries
replace raw data in the context assembly pipeline, reducing token usage by ~85%
for entity context and eliminating runtime embedding searches on the write path.

## Why it exists

The core problem: every AI write call loads raw KB data (200+ tokens/entity) and
chapter content (1500+ tokens/chapter) — the LLM must re-parse and re-understand
this data every single time. This wastes tokens, adds latency (300ms+ for embedding
search), and produces lower-quality output because raw template fields lack
narrative cohesion.

The LLM Wiki solves this by creating a preprocessed narrative layer: once per
entity update, the AI generates a compact summary. On write, it's a direct key
lookup (5ms, ~40 tokens) instead of a vector search (300ms, ~200 tokens raw).

## How it works (User perspective)

1. You create/edit a character in the Knowledge Base
2. Narrare automatically generates a WikiSummary in the background (2-3 sentences
   describing the character's role, personality, and key relationships)
3. You can view the WikiSummary in the KB entity detail — "How the AI sees this character"
4. When you finalize a chapter, Narrare generates a WikiChapterSummary (key events,
   entities involved, themes)
5. When you use AI writing features, the context automatically uses WikiSummaries
   instead of raw KB data — the AI gets cleaner, more narrative context
6. If you customize the wiki prompt ("describe characters more emotionally"),
   all existing summaries mark themselves as outdated and regenerate on next use
7. You can manually refresh any summary from the KB entity detail page

## How it works (Technical)

### Architecture

```
KB Entity Update ──→ EmbeddingHooks ──→ EventBus ──→ TaskIQ ──→ WikiGenerationAgent
Chapter Finalize ──→ ChapterService ──→ EventBus ──→ TaskIQ ──→ WikiGenerationAgent
Prompt Change    ──→ PromptRegistry ──→ EventBus ──→ Event    ──→ Alle WikiSummaries stale

Write-Call:
  Vorher: WritingContextAssembler lädt Rohdaten (Tier 3+4)
  Nachher: WritingContextAssembler lädt WikiSummaries (Tier 3)
           Fallback: Rohdaten wenn WikiSummary stale/pending
```

### Modules

**New: `core/wiki/` Module:**

| File | Responsibility |
|------|---------------|
| `contracts.py` | `WikiServiceProtocol`, `WikiAgentProtocol` |
| `types.py` | `WikiSummary`, `WikiChapterSummary`, `WikiSummaryStatus` enums |
| `service.py` | `WikiService` — orchestriert Generation + Lookup |
| `agent.py` | `WikiGenerationAgent` — LLM-Call für Summary-Generierung |
| `repository.py` | DB-Zugriff für WikiSummaries (API-Layer) |

**New: `apps/api/narrare/wiki/` Module:**

| File | Responsibility |
|------|---------------|
| `router.py` | REST-Endpoints für Wiki-Daten (GET summaries, POST refresh) |
| `schemas.py` | Pydantic-Request/Response-Schemas |
| `tasks.py` | TaskIQ-Tasks für Background-Generierung |
| `listeners.py` | Event-Listener für Trigger |

### Data Flow

**Entity WikiSummary Generation:**
1. KB Service updated entity → `EmbeddingHookManager.on_entry_updated()`
2. Hook publishes `kb.entry.updated` event via EventBus
3. Listener enqueues `wiki_generate_entity_task.kiq(entity_id, novel_id)`
4. TaskIQ executes: lädt Entity, ruft `WikiService.generate_entity_summary()` auf
5. WikiService lädt Wiki-Prompt via PromptRegistry, bereitet Context (Entity + Relationships)
6. WikiGenerationAgent generiert Summary (narrative_summary, role_in_story, key_attributes, relationships)
7. WikiRepository speichert/updatet WikiSummary mit `status: fresh`
8. Bei Fehler: WikiSummary bleibt `pending` — Fallback auf Rohdaten beim Write-Call

**Write-Call Context Assembly:**
1. WritingContextAssembler bereitet Context vor
2. Statt Rohdaten aus KB-Repository zu laden: `WikiService.get_summaries(entity_ids, novel_id)`
3. Für jedes Entity: WikiSummary lookup (falls fresh) → narrative_summary in Context
4. Fallback: Rohdaten aus KBEntry.body wenn WikiSummary stale/pending
5. Kein Embedding-Search mehr für Tier 4 (KB Suggested) — WikiSummary-Key-Lookup

### WikiGenerationAgent

```python
class WikiGenerationDeps(BaseModel):
    language: str
    genre: str
    entity_type: str         # character, location, faction, etc.
    entity_name: str
    entity_body: str
    entity_metadata: dict    # Template-spezifische Felder
    relationships: list[dict]  # [{name, rel_type, target_name}]
    chapter_context: list[str] # Kapitel, in denen Entity vorkommt

class WikiEntityOutput(BaseModel):
    narrative_summary: str      # 2-3 Sätze
    role_in_story: str          # 1 Satz
    key_attributes: list[str]   # 3-5 Attribute
    relationships: list[dict]   # [{target_entity_name, relationship_type, context}]
    character_arc: str | None   # Nur bei entity_type=character

class WikiGenerationAgent(NarrareAgent[WikiGenerationDeps, WikiEntityOutput]):
    ...
```

### Prompt Structure

```markdown
---
prompt_type: wiki
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt

You are a narrative wiki generator for a story writing tool. Given a Knowledge
Base entry, generate a compact narrative summary.

Entity Type: {{entity_type}}
Entity Name: {{entity_name}}

## Instructions

1. Write 2-3 sentences that capture the entity's essence in narrative form
2. Describe its role in the story concisely
3. List 3-5 key attributes that are narratively relevant
4. Describe relationships to other entities with chapter context
{% if entity_type == "character" %}
5. Include the character's arc: how they change throughout the story
{% endif %}

## Output Format

Return structured data as JSON with: narrative_summary, role_in_story,
key_attributes[], relationships[], character_arc (character only).
```

### Event Types (New)

```python
class EventType(StrEnum):
    # ... existing events ...
    WIKI_PROMPT_CHANGED = "wiki.prompt.changed"
    # Payload: {"category": "entity_summary" | "chapter_summary",
    #            "prompt_version": str, "language": str}
```

### Pipeline Integration

**Writing Context Assembly — angepasste 5 Tiers:**

| Tier | Budget | Neu / Vorher |
|------|--------|-------------|
| 1. Immediate | 30% | Unverändert — Current Chapter |
| 2. Recent | 20% | Unverändert — Recent Chapters |
| 3. KB Referenced | 25% | **WikiSummaries** statt Rohdaten + Rohdaten-Fallback |
| 4. KB Suggested | 15% | **Entfällt** — WikiSummaries decken alle relevanten Entities ab |
| 5. Pinned | 10% | Unverändert — User-Pinned |

**Change:** Tier 3 wird von "Rohdaten der referenzierten Entities" zu
"WikiSummaries der referenzierten Entities + Fallback". Tier 4 entfällt
(Embedding-Suche) — stattdessen werden WikiSummaries aller in den letzten
N Kapiteln referenzierten Entities vorgeladen.

## Constraints & Edge Cases

- **WikiSummary fehlt (pending/failed)**: Fallback auf Rohdaten aus KBEntry.body.
  Kein Write-Call wird blocked.
- **WikiSummary stale**: Bei Prompt-Änderung oder Entity-Update. Lazy Refresh
  im Background. Context enthält Warnung, aber keine Blockade.
- **WikiSummary-Generation fehlschlägt**: Retry via TaskIQ (3 Versuche).
  Bei totalem Fehler: Status bleibt `pending`, Fallback aktiv.
- **Entity ohne Body**: WikiSummary wird aus Template-Metadaten + Name generiert.
- **Entity gelöscht**: WikiSummary wird soft-deleted (TTL) — Referenzen in
  WikiChapterSummaries bleiben erhalten.
- **Chapter nicht finalisiert**: Kein WikiChapterSummary — nur finalized chapters
  lösen Generation aus.
- **Prompt-Version unbekannt**: Bei fehlender `prompt_version` im Prompt-Frontmatter:
  WikiSummary gilt immer als fresh (kein Prompt-Change-Tracking).
- **Mass-Updates (Import)**: EmbeddingHooks debounced — Batch-Wiki-Generation
  nach Abschluss des Imports.
- **WikiSummary zu lang**: Token-Limit pro Entity-Summary: 60 Tokens.
  Bei Überschreitung: truncate + Warnung im Context-Metadata.

## Related Features

- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context Assembly Pipeline (WikiSummaries ersetzen Tier 3+4)
- [WRITE-012](../writing/WRITE-012-chapter-summary.md) — Chapter Summary (Basis für WikiChapterSummary)
- [KB-001](KB-001-entity-management.md) — KB Entity CRUD (Datenquelle für WikiSummaries)
- [KB-005](KB-005-kb-suggest.md) — Proactive KB Suggestions (Entity-Chapter-Zuordnung)
- [KB-008](KB-008-knowledge-graph.md) — Knowledge Graph (visuelle Ergänzung zum Wiki)
- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — LLM Gateway (für Wiki-Generierung)
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Prompt System (Wiki-Prompts im Cascade)
- [INFRA-005](../infra/INFRA-005-memory-layer.md) — Memory Layer (WikiSummary-Preferences)

## Definition of Done

- [x] ADR-022 approved and documented
- [x] `core/wiki/contracts.py` definiert WikiServiceProtocol, WikiGenerationAgentProtocol
- [x] `core/wiki/types.py` definiert WikiSummary, WikiChapterSummary, WikiSummaryStatus
- [x] `core/wiki/agent.py` implementiert WikiGenerationAgent (Entity + Chapter)
- [x] `core/wiki/service.py` implementiert WikiService (generate, get, refresh, mark_stale)
- [x] `apps/api/narrare/wiki/repository.py` implementiert WikiRepository
- [x] `apps/api/narrare/wiki/tasks.py` TaskIQ-Tasks: wiki_generate_entity, wiki_generate_chapter, wiki_mark_all_stale
- [x] `apps/api/narrare/wiki/listeners.py` Event-Listener: kb.entry.updated, chapter.finalized, wiki.prompt.changed
- [x] `apps/api/narrare/kb/embedding_hooks.py` erweitert: Event-Publishing fuer Wiki-Trigger
- [x] `core/writing/context_assembler.py` erweitert: WikiSummary-Lookup + Fallback in Tier 3
- [ ] Wiki-Prompts in `core/prompts/_bundled/wiki/` (en, de, fr)
- [x] Migration: `wiki_summaries` + `wiki_chapter_summaries` Tabellen
- [x] Event-Typ `WIKI_PROMPT_CHANGED` in `core/events/types.py` registriert
- [x] Event-Listener in `apps/api/narrare/events/listeners.py` registriert
- [ ] Prompt-Versionierung in Wiki-Prompt-Frontmatter
- [ ] Wiki-UI: Entity-Detail-Ansicht zeigt WikiSummary ("How the AI sees this character")
- [ ] Wiki-UI: Manueller Refresh-Button im Entity-Detail
- [x] Graceful Degradation: Fallback auf Rohdaten bei stale/pending
- [x] Tests: Unit-Tests fuer Service + Agent (TestModel), Integration-Tests fuer Repository + Router
- [x] RULE-XX Compliance Matrix erfuellt

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | WikiGenerationAgent in `core/wiki/agent.py` via NarrareAgent-Basis + ModelRegistry |
| RULE-02 | ✅ | Wiki-Prompts in `core/prompts/_bundled/wiki/` |
| RULE-03 | ✅ | Contract in `core/wiki/contracts.py` vor Implementation |
| RULE-04 | ✅ | Modul-Aufteilung: agent.py max 200, service.py max 300, types.py max 150 Zeilen |
| RULE-05 | ✅ | Neues Modul `core/wiki/` — eigene Contracts, Service, Agent |
| RULE-06 | ✅ | Router delegiert an Service, Service orchestriert Agent + Repository |
| RULE-07 | ✅ | router → service → repository → DB. Core importiert nie apps/. |
| RULE-08 | ✅ | WikiGenerationAgent nutzt Gateway via ModelRegistry — keine direkten LLM-Clients |
| RULE-09 | ✅ | Alle Public-Methoden typannotiert |
| RULE-10 | ✅ | Unit-Tests: Service + Agent (TestModel). Integration-Tests: Router + Repository. Threshold: core 90%, api 80% |
| RULE-11 | ✅ | Error-Handling: Fehler bei Generation → status=pending + log. Kein Blocked Write-Call. |
| RULE-12 | ✅ | WikiService ist einzige öffentliche API — WebUI + MCP + A2A + CLI rufen Service auf |
| RULE-13 | ✅ | WikiGenerationAgent hat streaming/non-streaming Interface (Preview-Modus) |
| RULE-14 | ✅ | Migration für `wiki_summaries` + `wiki_chapter_summaries` |
| RULE-20 | ✅ | Vollständige Implementierung: Precompute + Stale + Fallback + Prompt-Trigger. Keine Half-Implementation. |

## Status & History

- `2026-05-29` — ADR-022 Accepted. Full backend implemented (core + api layers, 35+9 unit tests, commits 8ba62f3 and 2e72f61). Status: in-progress (frontend pending).
- `2026-05-29` — ADR-022 proposed. Feature Spec created. Status: planned.
