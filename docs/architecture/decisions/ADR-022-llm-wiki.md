# ADR-022: LLM Wiki — Precomputed Context Layer

**Status**: Accepted
**Date**: 2026-05-29
**Implemented**: 2026-05-29
**Decision Maker**: Architecture Agent

## Context

### Symptom

Jeder Write-Call lädt rohe KB-Entity-Daten (200+ Tokens/Entity) und Chapter-Inhalte (1500+ Tokens/Kapitel) in den Context Assembly. Das LLM muss diese Rohdaten jedes Mal neu "verstehen" — es gibt keine vorverarbeitete, LLM-optimierte Zwischenschicht.

Aktuelle Metrik pro Write-Call (gemittelt):
- 6-12 KB Entities geladen → ~1200–2400 Tokens Rohdaten
- 3-5 Recent Chapters geladen → ~4500–7500 Tokens Inhalt
- Embedding-Search für Suggested Entities → ~300ms Latenz
- **Total: ca. 6000–10000 Tokens, 300ms+ Suchzeit** bevor der erste LLM-Call startet

### Root Cause 1

Der `WritingContextAssembler` (`core/writing/context_assembler.py`) formatiert Rohdaten 1:1 in den Prompt. Entity-Body, Frontmatter, Chapter-Content — alles unverarbeitet. Es existiert keine vorverarbeitete, LLM-optimierte Beschreibungsebene zwischen Rohdaten und Prompt.

### Root Cause 2

Das `ChapterSummary` (WRITE-012) existiert bereits (`core/agents/summary_agent.py`) und produziert LLM-optimierte Zusammenfassungen (~80 Tokens statt 1500+). Es wird aber nur für den Storyboard-Sync genutzt — nicht für den Writing-Context. Damit ist ein erheblicher Teil der Token-Optimierung bereits implementiert, aber ungenutzt.

### Root Cause 3

Embedding-Suche zur Laufzeit (Tier 4: KB Suggested) ist langsam (~300ms) und nicht-deterministisch. Unterschiedliche Embedding-Modelle oder Content-Änderungen können unterschiedliche Ergebnisse liefern. Für den Write-Call brauchen wir deterministischen Key-Lookup — die Embedding-Suche sollte nur bei der WikiSummary-Generierung (Background-Task) eingesetzt werden.

### Existing Assets (Wiederverwendung)

| Asset | Ort | Nutzung im Wiki |
|-------|-----|-----------------|
| `ChapterSummaryAgent` | `core/agents/summary_agent.py` | Basis für WikiChapterSummary — Prompt erweitern, Output erweitern |
| `ProactiveContextService` | `core/context/proactive_service.py` | Entity-Chapter-Zuordnung für Wiki-Refresh |
| `EmbeddingHookManager` | `apps/api/narrare/kb/embedding_hooks.py` | Trigger-Pattern für Wiki-Generierung bei KB-Änderungen |
| `WritingContextAssembler` | `core/writing/context_assembler.py` | 5-Tier-Pipeline — WikiSummaries ersetzen Tier 3+4 |
| `TokenBudgetManager` | `core/writing/budget.py` | Token-Budget für WikiSummaries im Context |
| `PromptComposer` | `core/prompts/composer.py` | Variable-Substitution für Wiki-Generation-Prompts |
| `PromptRegistry` | `core/prompts/registry.py` | Wiki-Generation-Prompts im Cascade |
| `LLMGateway` / `ModelRegistry` | `core/llm/` | LLM-Calls für Wiki-Generierung |
| `KBEntry` Model | `apps/api/narrare/kb/models.py` | Entity-Rohdaten für Summary-Generierung |
| `EventBus` | `core/events/` | Prompt-Änderungs-Events (wiki.prompt.changed) |

## Decision Drivers

- **Token-Reduktion**: Entity-Rohdaten (~200 Tokens) durch narrative Summaries (~40 Tokens) ersetzen
- **Determinismus**: Embedding-Suche zur Laufzeit eliminieren — direkter Key-Lookup statt Vektor-Suche
- **Prompt-Responsivität**: Änderungen am Wiki-Generation-Prompt markieren abhängige Summaries als stale
- **Nebenprodukt: Wiki-UI**: Autoren sehen, "wie die AI ihre Welt versteht"
- **Bessere Context-Qualität**: LLM-optimierte, kuratierte Beschreibungen statt roher Template-Daten
- **Inkrementelle Einführung**: Jede Wiki-Tabelle kann unabhängig aktiviert werden (Entity, Chapter, Character-Arc)

## Options Considered

### Option A: LLM Wiki als präcomputierter Context-Layer **(vorgeschlagen)**

**Description**: Ein neuer `core/wiki/` Module Layer, der zwischen Rohdaten (KB Entities, Chapters) und dem Context Assembly System sitzt. Bei Entity-Änderung → TaskIQ-Task → WikiSummary generieren (einmaliger LLM-Call, ~40 Output-Tokens). Bei Write-Call → WikiSummary-Lookup (5ms, ~1000 Tokens statt 6000+). Bei Prompt-Änderung → Event → Alle abhängigen Summaries stale markieren.

**Architecture Pattern:**
```
KB Entity Update → EventBus → TaskIQ → WikiAgent → WikiSummary (stored)
Chapter Finalize → EventBus → TaskIQ → WikiAgent → WikiChapterSummary (stored)
Prompt Change   → EventBus → Event     → alle WikiSummaries stale

Write-Call:
  Bisher: Embedding-Search + Rohdaten laden (300ms, 6500 Tokens)
  Neu:    WikiSummary-Lookup (5ms, 1000 Tokens)
```

**Pros:**
- Drastische Token-Reduktion (~85% weniger Tokens für Entity-Kontext)
- Embedding-Suche nur noch in Background-Tasks, nicht auf dem Write-Pfad
- Determinismus: Key-Lookup statt Vektor-Suche zur Laufzeit
- Prompt-sensitiv: WikiSummaries haben `depends_on.wiki_prompt_version`
- Nebenprodukt Wiki-UI für Autoren
- Wiederverwendung von ChapterSummary (WRITE-012) als Basis
- Inkrementell einführbar (Entity → Chapter → Character-Arc)

**Cons:**
- Zusätzlicher LLM-Call pro Entity-Update (ca. 200 Output-Tokens)
- Stale-Summaries bei Prompt-Änderung — Refresh nötig
- Neues Datenmodell + Migration erforderlich
- Neues Event-Type (`wiki.prompt.changed`) erforderlich

### Option B: Live-Context-Assembly mit Embedding-Search optimieren

**Description**: Status Quo verbessern — Embedding-Search effizienter machen, Token-Budget optimieren, Rohdaten komprimieren. Keine neue Infrastruktur.

**Pros:**
- Keine neuen Datenmodelle, keine Migration
- Keine zusätzlichen LLM-Calls
- Keine Stale-Problematik (immer live)
- Minimaler Implementierungsaufwand

**Cons:**
- Embedding-Suche bleibt auf dem kritischen Pfad (300ms)
- Rohdaten bleiben unverarbeitet — LLM muss jedes Mal "verstehen"
- Keine Token-Reduktion (6000+ Tokens bleiben)
- Keine Wiki-UI für Autoren
- ChapterSummary bleibt ungenutzt für Writing-Context
- **Verstösst gegen RULE-20 (No half-implementations)**: ChapterSummary existiert, wird aber nicht für seinen primären Use-Case genutzt

### Option C: KB-008 Knowledge Graph um Wiki-Features erweitern

**Description**: Den bestehenden Knowledge Graph (KB-008) um narrative Beschreibungen erweitern. Jeder Graph-Knoten erhält ein `narrative_summary`-Feld. Die Graph-Datenbank (Neo4j oder pgvector) wird zum primären Context-Layer.

**Pros:**
- Graph-Struktur für Beziehungen bleibt erhalten
- Eine visuelle + narrative Query-Schnittstelle
- Kein neues Modul

**Cons:**
- KB-008 ist ein Frontend-Feature (Visualisierung) — es hat keinen Service-Layer für Context-Lookup
- Graph-DB (Neo4j) ist neue Infrastruktur-Dependency → ADR und Evaluierung nötig
- Embedding-Suche im Graph ist komplexer als Key-Lookup
- KB-008 ist aktuell "planned" — auf ein nicht implementiertes Feature aufzusetzen ist riskant
- **Verstösst gegen RULE-20**: KB-008 existiert nur als Spec, nicht implementiert

## Decision

**We choose Option A — LLM Wiki als präcomputierter Context-Layer.**

Die Token-Reduktion (~85%), der Determinismus (keine Embedding-Suche auf dem Write-Pfad), und die Prompt-Responsivität sind die entscheidenden Faktoren. Option B optimiert das falsche Problem (Latenz statt Token-Menge) und Option C setzt auf ein nicht implementiertes Feature auf.

### Rationale

1. **Token-Reduktion ist der primäre Hebel**: Jeder Write-Call spart ~5000 Tokens. Bei 50 Write-Calls/Stunde sind das 250K Tokens/Stunde — ~$3-5/Stunde allein an Input-Token-Kosten. Das Wiki amortisiert sich in wenigen Wochen.

2. **Determinismus verbessert UX**: Der gleiche Write-Call liefert immer den gleichen Context (gleiche WikiSummaries). Embedding-Suche kann bei Content-Änderungen zwischen Calls unterschiedliche Entities vorschlagen — das macht Debugging und Testing schwerer.

3. **Prompt-Responsivität ist kritisch**: Wenn der Autor den Wiki-Generation-Prompt anpasst ("beschreibe Charaktere emotionaler"), müssen alle Summaries sofort aktualisiert werden. Der `depends_on.wiki_prompt_version`-Mechanismus stellt das sicher — kein Live-System kann das leisten.

4. **Wiederverwendung von ChapterSummary**: Der ChapterSummaryAgent existiert und produziert bereits LLM-optimierte Zusammenfassungen. Das Wiki nutzt ihn als Basis und erweitert ihn um Entities, Key-Events und Themes. Das macht die Implementierung deutlich kleiner.

5. **Inkrementelle Einführung**: Wir starten mit `WikiSummary` (Entity-Summary) und `WikiChapterSummary` (Chapter-Summary). Character-Arcs, Plot-Summaries und Location-Histories kommen später — ohne Breaking Changes.

## Consequences

### Positive

- **Token-Reduktion**: ~85% weniger Tokens für Entity-Kontext im Write-Call
- **Latenz**: Embedding-Suche vom kritischen Pfad entfernt — Write-Call startet 300ms früher
- **Determinismus**: Gleicher Input → gleicher Wiki-Context → gleicher Write-Output (bei gleichem Model)
- **Prompt-Responsivität**: Prompt-Änderungen propagieren via `wiki_prompt_version`
- **Wiki-UI**: Autoren sehen, wie die AI ihre Welt versteht — bessere Kontrolle über den Context
- **Wiederverwendung**: ChapterSummary als Basis, EmbeddingHooks als Trigger-Pattern
- **Event-kompatibel**: Nutzt bestehenden EventBus (ADR-012) und TaskIQ (ADR-007)

### Negative

- **Zusätzliche LLM-Costs**: Pro Entity-Update ein Wiki-Generation-Call (~200 Output-Tokens) — amortisiert sich durch Token-Einsparung bei Write-Calls
- **Stale-Summaries**: Bei Prompt-Änderung werden alle Summaries stale — müssen lazy refreshed werden
- **Neue Datenmodelle**: `WikiSummary` + `WikiChapterSummary` + Migration
- **Neuer Event-Type**: `wiki.prompt.changed` muss registriert werden
- **Agent-Neubau**: WikiGenerationAgent (erweitert ChapterSummaryAgent)

### Risks

| Risiko | Mitigation |
|--------|------------|
| Stale Summaries liefern veralteten Context | `status: stale` → Warnung im Context, Lazy-Refresh beim nächsten Write-Call |
| Wiki-Generation schlägt fehl | Fallback auf Rohdaten (Graceful Degradation) — kein Blocked Write-Call |
| Prompt-Change-Ereignis geht verloren | Prompt-Version im WikiSummary gespeichert — Refresh beim nächsten Zugriff |
| Entity-Update-Flut (viele Änderungen schnell hintereinander) | Debounce-Mechanismus in EmbeddingHooks — keine parallelen Tasks für gleiches Entity |
| WikiSummary-Speicher wächst unbegrenzt | TTL-basierte Cleanup-Task veraltetete Summaries (nicht referenzierte Entities) |

## Constraints Affected

- **RULE-01b**: WikiGenerationAgent lebt in `core/agents/` — konform
- **RULE-02**: Wiki-Generation-Prompt in `core/prompts/_bundled/wiki/` — konform
- **RULE-03**: Contract in `core/wiki/contracts.py` vor Implementation — konform
- **RULE-04**: Modul-Aufteilung: `wiki_agent.py` max 200 Zeilen, `wiki_service.py` max 300 Zeilen
- **RULE-05**: Neues Domain-Modul `core/wiki/` mit eigenem Contract, Service, Agent
- **RULE-06**: Eine Verantwortung pro Datei — Agent generiert, Service orchestriert
- **RULE-07**: router → service → repo → DB. Core importiert nie apps/.
- **RULE-10**: Unit-Tests für Service + Agent. Integration-Tests für Router + DB-Zugriff.
- **RULE-12**: Service Layer ist einzige öffentliche API — WikiService wird von WritingContextAssembler aufgerufen
- **RULE-13**: WikiSummary-Generation hat streaming/non-streaming Interface (Preview-Feature)
- **RULE-20**: Kein Half-Implementation — WikiSummary + WikiChapterSummary + Stale-Handling + Prompt-Trigger
- **RULE-14**: Migration für `wiki_summaries` + `wiki_chapter_summaries` Tabellen

## Compliance

- [X] Does not violate any RULE-XX without an approved exception
- [X] Compatible with four-client model (WebUI, MCP, A2A, CLI) — WikiService als Service Layer
- [X] Dependency direction maintained (RULE-07) — core/wiki/ importiert core/llm/, core/prompts/
- [X] Streaming/Non-Streaming shared interface (RULE-13)
- [X] Contract-First (RULE-03) — contracts.py vor service.py
- [X] Kein Half-Implementation (RULE-20) — vollständiger Precomputed Context Layer inkl. Stale-Handling

## Data Model

### WikiSummary (pro Entity + Novel)

```python
class WikiSummaryStatus(StrEnum):
    PENDING = "pending"    # generation queued but not yet complete
    FRESH = "fresh"        # up to date
    STALE = "stale"        # depends_on changed — needs refresh

class WikiSummary(Base):
    __tablename__ = "wiki_summaries"

    id: UUID                  # PK
    novel_id: UUID            # FK → novels.id
    entity_id: UUID           # FK → kb_entries.id

    # Core content (LLM-generated)
    narrative_summary: str    # 2-3 Sätze, ~40 Tokens
    role_in_story: str | None # Charakter-Rolle / Zweck / Funktion
    key_attributes: list[str] # Wichtige Eigenschaften
    relationships: list[dict] # [{"entity_id": UUID, "rel_type": str, "context": str}]
    chapter_references: list[UUID]  # Chapters in denen Entity vorkommt
    character_arc: str | None # Nur für entity_type=character

    # Dependency tracking for stale detection
    depends_on: dict = {
        "entity_content_hash": str,   # Hash des aktuellen KBEntry.body
        "wiki_prompt_version": str,   # Version des Wiki-Generation-Prompts
        "template_version": str | None, # KB-Template-Version
        "chapter_states": [UUID],     # Chapter-IDs zum Zeitpunkt der Generierung
    }

    # Status
    status: WikiSummaryStatus  # fresh | stale | pending
    version: int               # Increment bei jeder Regenerierung
    content_hash: str          # Hash des generierten Inhalts (für Cache-Vergleich)

    # Timestamps
    generated_at: datetime     # Wann zuletzt generiert
    refreshed_at: datetime | None  # Wann zuletzt validiert
    created_at: datetime
    updated_at: datetime

    # Unique constraint: ein WikiSummary pro Entity pro Novel
    __table_args__ = (
        UniqueConstraint("novel_id", "entity_id", name="uq_wiki_summary_entity"),
    )
```

### WikiChapterSummary (erweitert WRITE-012)

```python
class WikiChapterSummary(Base):
    __tablename__ = "wiki_chapter_summaries"

    id: UUID
    chapter_id: UUID           # FK → chapters.id

    # Erweiterte Summary (über ChapterSummary hinaus)
    narrative_summary: str     # ~60 Tokens, LLM-optimiert
    key_events: list[str]      # Wichtige Ereignisse in diesem Kapitel
    entities_involved: list[dict]  # [{"entity_id": UUID, "role": str, "significance": float}]
    themes: list[str]          # Themen/Subplots
    emotional_arc: str | None  # Emotionale Entwicklung im Kapitel

    # Dependency tracking
    chapter_content_hash: str
    wiki_prompt_version: str
    status: WikiSummaryStatus  # fresh | stale | pending
    version: int
```

### Event: wiki.prompt.changed

```python
class EventType(StrEnum):
    # ... existing events ...
    WIKI_PROMPT_CHANGED = "wiki.prompt.changed"
    # Payload: {"category": str, "prompt_version": str, "language": str}
```

## Core Architecture Changes

### New Module: `core/wiki/`

```
packages/core/narrare_core/wiki/
├── __init__.py              # Public exports
├── contracts.py             # WikiServiceProtocol, WikiAgentProtocol
├── service.py               # WikiService — Orchestrierung
├── agent.py                 # WikiGenerationAgent — LLM-Calls
├── types.py                 # WikiSummary, WikiChapterSummary, Status enums
├── repository.py            # DB-Access (API-layer)
└── prompts/
    └── _bundled/
        └── wiki/
            ├── en/
            │   ├── entity_summary/system.md    # Entity → WikiSummary
            │   └── chapter_summary/system.md   # Chapter → WikiChapterSummary
            ├── de/
            └── fr/
```

### Integration Points

**KB Service** (`apps/api/narrare/kb/service.py`):
- Nach Entity-Update: `EventBus.publish("kb.entry.updated", {entity_id, novel_id})`

**Chapter Service** (`apps/api/narrare/chapters/service.py`):
- Nach Chapter-Finalize: `EventBus.publish("chapter.finalized", {chapter_id, novel_id})`

**Listener** (`apps/api/narrare/events/listeners.py`):
- `kb.entry.updated` → `wiki_generate_entity_task.kiq(entity_id, novel_id)`
- `chapter.finalized` → `wiki_generate_chapter_task.kiq(chapter_id, novel_id)`
- `wiki.prompt.changed` → `wiki_mark_all_stale_task.kiq(prompt_version, category)`

**WritingContextAssembler** (`core/writing/context_assembler.py`):
- Neuer Wiki-Tier zwischen Immediate + Recent:
  - 5th: WikiSummaries (von Entity-IDs → narrative Summaries)
  - Fallback: Rohdaten, wenn WikiSummary stale oder pending

### Trigger-Matrix

| Ereignis | Refresh | Strategie | Notiz |
|----------|---------|-----------|-------|
| KB-Entity bearbeitet (body/content) | ✅ Single-Entity | On-Change via EmbeddingHooks | content_hash geändert → WikiSummary neu generieren |
| KB-Entity bearbeitet (nur metadata) | ❌ Kein Refresh | Nicht nötig | WikiSummary hängt nur von body + beziehungen ab |
| KB-Entity gelöscht | ✅ Adjacent-Update | On-Change | Nachbar-Entities' relationships updaten |
| Kapitel finalisiert | ✅ ChapterSummary + Entity-Matrix | On-Change via Chapter Service | Neue Entity-Referenzen extrahieren |
| Wiki-Generation-Prompt geändert | ✅ ALLE WikiSummaries | Event: PromptChanged | `wiki_prompt_version` inkrementieren, alle stale |
| KB-Template erweitert | ✅ Nur betroffene Entity-Typen | On-Change | `template_version` in dependencies |
| Beziehung hinzugefügt/entfernt | ✅ Beide Enden + Adjacent | On-Change via Relationship Service | relationships-Feld updaten |
| User klickt Refresh | ✅ Single-Entity | On-Demand | Status forced fresh |
| Kapitel-Content geändert (nicht finalisiert) | ❌ Kein Refresh | Nicht nötig | Nur finalisierte Kapitel erzeugen Summaries |

### Prompt-Abhängigkeitsmodell

```
Wiki Generation Prompt (wiki/{lang}/entity_summary/system.md)
    ↓ prompt_version: "1.2.3"
    ↓
WikiSummary.depends_on.wiki_prompt_version == "1.2.3"
    ↓ Bei Änderung ≠ current
WikiSummary.status = stale
    ↓ Beim nächsten Write-Call
Lazy Refresh im Background
```

**Versionierung des Wiki-Prompts:**
- Jeder Wiki-Prompt hat eine `prompt_version` im Frontmatter (z.B. `1.2.3`)
- Bei Deployment einer Prompt-Änderung: `EventBus.publish("wiki.prompt.changed", {"prompt_version": "1.3.0"})`
- Listener markiert alle WikiSummaries mit `depends_on.wiki_prompt_version < "1.3.0"` als stale
- Stale Summaries werden beim nächsten Zugriff lazy refreshed (Background-Task, nicht Blocking)

**Version comparison:** Semantisch (major.minor.patch):
- **Patch** (1.2.3 → 1.2.4): Typo-Fix, kein Content-Unterschied → kein Refresh zwingend
- **Minor** (1.2.3 → 1.3.0): Prompt-Verbesserung → alle Summaries stale
- **Major** (1.0.0 → 2.0.0): Breaking Change → alle Summaries stale + force refresh

### Graceful Degradation für Write-Call

Wenn `WikiSummary.status == stale || pending`:
1. Log: `wiki_summary_stale`, entity_id, novel_id, status
2. Fallback auf Rohdaten (KBEntity.body + Template-Metadata)
3. Background: TaskIQ-Task für Refresh enqueue
4. Context enthält Warnung: `context_metadata.wiki_summaries_stale = [entity_ids]`

Kein Write-Call wird blocked. Das Wiki ist ein Optimierungs-Layer, keine harte Dependency.

## Review Trigger

- [ ] Wenn die Token-Reduktion < 50% der erwarteten ~85% liegt
- [ ] Wenn WikiSummary-Refresh-Rate > 10% aller Write-Calls (zu viele stale Summaries)
- [ ] Wenn der Prompt-Versionierungs-Mechanismus sich als zu komplex erweist
- [ ] Wenn pydantic-ai Agents als Alternative zu TaskIQ für Background-Generierung evaluiert werden sollen
- [ ] Nach 3 Monaten Produktion: Ist die Token-Einsparung die zusätzliche LLM-Komplexität wert?

## Implementation Notes

The following implementation decisions were made during the backend build (commits 8ba62f3, 2e72f61):

1. **REPLACE strategy confirmed.** Architecture evaluation concluded that merge semantics are unnecessary for a KB-derived cache layer. WikiSummaries are always regenerated whole — `REPLACE` on conflict is correct and simpler than merge.

2. **Cross-entity staleness via JSONB containment.** The `depends_on` column uses PostgreSQL's `@>` operator to detect staleness across entity relationships. When an entity changes, a single query finds all WikiSummaries whose `depends_on` JSONB contains a reference to that entity. Inspired by Karpathy's approach to dependency tracking.

3. **system_mode flag for background task ownership.** Background tasks (TaskIQ workers) operate without a user session. A `system_mode` boolean on service calls bypasses ownership checks, allowing the wiki service to regenerate summaries for any entity regardless of the user context.

4. **ChapterWikiService extracted (RULE-04).** The initial service grew beyond the file-size limit. `ChapterWikiService` was extracted from `WikiService` to handle all chapter-summary operations independently, keeping each file under 300 lines.

5. **WikiSystemAccessors mixin.** A mixin class provides system-level repository access for background tasks. This avoids duplicating ownership-bypass logic across the wiki tasks and listeners.

6. **WikiIndexResponse schema.** A dedicated response schema for the wiki overview endpoint returns entity counts, staleness ratios, and generation status — supporting the future Wiki UI dashboard without requiring per-entity queries.

7. **TokenBudgetManager wiki_optimized allocation.** The token budget manager gained a `wiki_optimized` allocation strategy that shifts 5% from `kb_referenced` to `immediate` tier, reflecting the reduced token footprint when WikiSummaries replace raw KB data in the context.

## Glossary Entries

**WikiSummary**: Eine LLM-generierte, präcomputierte narrative Zusammenfassung einer KB-Entity. Enthält 2-3 Sätze Beschreibung, Rolle in der Story, Schlüsselattribute und Beziehungen. Status: fresh, stale, oder pending.

**WikiChapterSummary**: Eine erweiterte Kapitelzusammenfassung (über ChapterSummary hinaus) mit Key-Events, beteiligten Entitäten und Themen. Wird beim Finalisieren eines Kapitels generiert.

**Stale (WikiSummary)**: Status eines WikiSummary, dessen Abhängigkeiten (Prompt-Version, Entity-Content, Template-Version) sich seit der Generierung geändert haben. Stale Summaries lösen einen Lazy-Refresh beim nächsten Zugriff aus.
