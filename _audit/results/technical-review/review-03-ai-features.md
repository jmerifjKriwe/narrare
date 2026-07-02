# Review 03 – AI-Features & Prompting

> Aktualisiert am 2026-06-29 durch NarrareCoreSpecialist (Core/Backend/Prompting/Agents).
> **Abschnitte 7 (WebUI) und 8 (TipTap) sowie die AI-Features-Gesamtbewertung
> am 2026-06-29 durch `NarrareFrontendSpecialist` finalisiert** (Frontend-
> Evidenz: Komponenten-/State-Struktur, AI-UX-Lifecycle, AIAnnotation-Mark-
> System, GhostText, Slash-Commands, connectSSE/AbortController/Partial-Output).
> Grundlage: `_audit/results/technical-review/review-00-kontext.md`,
> `review-01-architektur.md`, `review-02-testing.md`, `docs/_shared/CONSTRAINTS.md`
> als SSOT, ADRs 015/024/026/034/037/043/046/048/049/052/054/055, Code-Graph
> (26.084 Nodes, Stand 2026-06-29) und Checker-Evidenz aus Review 01/02.
> Kein Commit, kein `--no-verify`. Nur diese Ergebnisdatei geschrieben.

## Methodik & ausgeführte Prüfungen

- **Graph-first ausgeführt:** `get_minimal_context`, `get_architecture_overview`
  (truncated, ausgewertet), `semantic_search_nodes` für `PromptComposer`,
  `NarrareAgent`, `ModelRegistry`, `query_graph children_of` für `agents/base.py`.
  Embeddings sind nicht gebaut (Graph meldet Embeddings: 0), daher
  Keyword/Hybrid-Suche genutzt.
- **Gezielte Reads:** `agents/base.py`, `agents/capabilities/{meta,universal_rules,
  observability,__init__}.py`, `prompts/{composer,routes,route_table}.py`,
  `llm/{intents,model_routing}.py`, `chat/chat_agent.py`,
  `writing/pipeline_interview.py`, `agents/writing_graph.py` (Head),
  `kb/assist_service.py`, `prompts/{service,live_test_service}.py`.
- **Verzeichnis-/Grep-Evidenz:** `find`/`rg` über `apps/`, `packages/`,
  `docs/features/`, `.opencode/`, `.agents/`, `.claude/` zur Verifikation
  von MCP/A2A-Implementierungsstatus, Skill-/Command-Struktur und
  Agent-Vererbung.
- **Checker ausgeführt:** `just check-adoption` (PASS, 0.97,
  ADR-046 compliant). `check-prompts-strict`, `check-configuration-matrix`,
  `check-streaming`, `check-ai-ux` wurden in Review 01/02 bereits frisch
  ausgeführt und sind dort dokumentiert (alle grün); dieser Review
  übernimmt diese Evidenz und fokussiert auf AI/Prompting-spezifische
  Code-Pfade.
- **Nicht ausgeführt:** Vollständige Unit-/Eval-Suites (in Review 02
  dokumentiert), Integration/E2E (Docker-only), Frontend-Testsuite.

---

## 1. Prompt-System für Nutzer

**Bewertung:** ⭐⭐⭐⭐⭐ `Reife, mehrschichtige Prompt-Governance mit stellarer maschineller Absicherung`

**Befunde:**

- **Architektur (RULE-02/02a/02b):** Prompt-Erstellung ist exklusiv in
  `packages/core/narrare_core/prompts/` gekapselt. `PromptComposer.build()`
  (`composer.py:63-186`) ist der einzige Assemblierungspunkt: er löst die
  Route über `resolve_prompt_route()` (`routes.py:42`) auf, füttert die
  Variable Engine (`prepare_variables_for_template` + `substitute` strict)
  und erzeugt ein `ComposedPrompt{system, user, first_message}`. Services
  übergeben nur Laufzeit-Input (`agent.run(prompt=...)`), niemals
  Inline-System-/Task-Anweisungen — in Stichproben über
  `kb/assist_service.py`, `chat/chat_agent.py`, `writing/suggest_service.py`,
  `analysis/services/readability_service.py`, `consistency/consistency_orchestrator.py`
  bestätigt (alle nehmen `PromptComposer` via DI und reichen `composed.system`
  an den Agent weiter).
- **Content-Kategorien (ADR-026 / RULE-02a) sind sauber getrennt:**
  - **Garantiert (Capability):** `NarrareMeta`, `NarrareUniversalRules`,
    `NarrareObservability` werden in `NarrareAgent.__init__`
    (`base.py:127-132`) **immer** injected — nicht in Templates
    dupliziert. `meta.py` und `universal_rules.py` laden synchron aus
    `_bundled/{meta,universal}/{lang}/system.md` mit EN-Fallback und
    leerem String als Graceful-Degradation (RULE-11).
  - **Anpassbar (Cascade):** `PromptRegistry.resolve()` löst
    bundled → DB-Override auf. Nutzer können über
    `PromptManagementService` (`core/prompts/management.py`, via
    `apps/api/narrare/prompts/service.py` als dünner API-Wrapper)
    Prompts listen, ansehen, überschreiben, diffen und live testen
    (PROMPT-003 / `live_test_service.py`).
  - **Dynamisch (`@agent.instructions` / Deps):** KB-Inhalt, Style-Profile,
    Voice-Profile, recent_chapters, world_context etc. laufen als
    Runtime-Variablen über `PromptContext`/Deps, nicht als hardcodierte
    Instruktionen. `_COMMON_OPTIONAL_VARIABLES` (`route_table.py:69-85`)
    deklariert diese explizit als optional, sodass die Variable Engine sie
    leer rendert, statt zu crashen (RULE-11).
- **Routeable Intents (ADR-037/046/049):** `route_table.py` ist die
  einzige SSOT für Intent→Category/Mode-Mappings. `NON_ROUTEABLE_INTENTS`
  (SENTIMENT, GENERATE, TITLE_GENERATE, RESEARCH) und
  `CONTEXT_MODE_REQUIRED_INTENTS` (KB_CREATE, EXTRACT) sind explizit
  gouvernement. `just check-adoption` meldet: **ADR-046 prompt-path
  compliance: all intents compliant**; ADR-048 Mode 2: keine Issues;
  Adoption-Debt-Ratchet: 1 current / 1 baseline / 0 new / 0 resolved.
  Die 1 current Debt ist dokumentiert und nicht neu.
- **Prompt-Manifest (ADR-037):** `scripts/architecture/prompt-surface-manifest.yaml`
  existiert und wird von `_checkers/_check_prompt_surface.py`,
  `_check_prompt_orphan.py`, `_check_prompt_identity.py`,
  `_check_variables.py`, `_check_intents.py` durchgesetzt — das ist
  maschinelle RULE-22-Coherence (Runtime↔Governance), nicht nur Doku.
- **Prompt-Qualität (Stichprobe):** Bundled-Prompt-Struktur folgt dem
  9-teiligen Skeleton aus `prompt-standards.md` (Role/Output/Do-NOT/
  Injection/Runtime-Input-Contract/Formality-Register, XML-Wrapping).
  Intents in `intents.py` tragen explizite Scope-/NOT-Scope-Dokumentation
  pro Wert — das ist vorbildliche Prompt-Spezifikation auf Enum-Ebene.
  `check-prompts-strict` validiert 48/48 System-Prompts, Warning-Ratchet 0.
- **Mehrsprachigkeit:** Meta/Universal sind mehrsprachig (en/de/fr);
  Feature-Prompts sind bewusst EN-only (Policy-konform, per
  `check-locale-sync` 42 Gruppen synced, 0 drifted).
- **Konsistenz über Einstiegspunkte:** API + WebUI nutzen denselben
  PromptComposer-Cascade-Pfad. CLI existiert nicht als Produkt-CLI;
  MCP/A2A sind nicht implementiert (siehe Abschnitte 5/6), sodass die
  Frage der Prompt-Konsistenz über CLI/MCP/A2A aktuell nichtstellbar ist.
  Die Core-seitige Vorbeugung (Services setzen auf Contracts auf, nicht
  auf Router-Factories) ist vorhanden.
- **Kleinstes Restrisiko (kein eigener AUFG, da adoption-konform
  dokumentiert):** `kb/assist_service.py:195-202` fängt einen Fehler der
  Invocation-Composition mit breitem `except Exception` ab und fällt
  zurück auf direkten `composer.build()`. Das ist dokumentierte
  Graceful-Degradation, umgeht aber ADR-048 Mode-1-Validation/Evidence
  für diesen Pfad. Siehe AUFG-03-02 für die architektonische Aufräumarbeit.

---

## 2. Agent-System während der Entwicklung

**Bewertung:** ⭐⭐⭐⭐⭐ `Hierarchisch, SSOT-diszipliniert, effizient im Context-Window`

**Befunde:**

- **Hierarchie der Dev-Anweisungen:** Root `AGENTS.md` (Orchestrator)
  delegiert sauber an `packages/core/AGENTS.md`, `apps/api/AGENTS.md`,
  `tests/AGENTS.md`. CONSTRAINTS.md ist autoritative SSOT; abgeleitete
  Kontext-Dateien referenzieren die Doku statt sie zu reproduzieren
  (§8 SSOT-Hierarchy wird explizit in jeder AGENTS.md genannt).
- **`.opencode/context/narrare-dev/`:** 35 extrahierte Kontext-Dateien
  mit `Priority`/`Source`/`Updated`-Metadaten, alle <200 Zeilen
  (Context-Window-effizient). Strukturiert in `constraints/`, `concepts/`,
  `standards/`, `processes/`, `guides/`, `domain/`, `lookup/`, `templates/`,
  `examples/`, plus `navigation.md`. Qualität der Extrakte hoch — z. B.
  `constraints/rules.md` (Stand 2026-06-17) referenziert CONSTRAINTS.md
  (995 Zeilen) korrekt als Source.
- **`.opencode/commands/`:** 6 Commands (`recall`, `remember`,
  `opsx-{propose,explore,apply,archive}`) — schlank, keine redundanten
  Skripte.
- **Skills (zwei bewusst getrennte Locations, kein Overlap):**
  - `.opencode/skills/` (6): opencode-native Werkzeuge (`context7`,
    OpenSpec-Flow, `task-management`).
  - `.agents/skills/` (21): cross-plattform Skills (`building-pydantic-ai-agents`,
    `mem0`, `frontend-design`, `logfire-*`, Vercel-/Tailwind-/Shadcn-Pattern,
    Memory-Tools). Diese Trennung ist korrekt — `.opencode/` ist
    Tooling-spezifisch, `.agents/` ist plattformunabhängig.
- **`.claude/`:** Nicht vorhanden (Projekt nutzt opencode, nicht Claude
  Code nativ). Kein Befund — nur der Vollständigkeit halber erwähnt, da
  der Review-Prompt `.claude/commands` abfragt.
- **Konsistenz:** Keine widersprüchlichen Agent-Anweisungen gefunden.
  Root AGENTS.md Trigger-Erkennung (z. B. „neues modul → narrare-architecture")
  ist mit den `.opencode/agents/`-Definitionen kohärent. Die
  Architektur-Regeln in extrahierten Kontext-Dateien stimmen mit
  CONSTRAINTS.md überein (Stichprobe RULE-01b/02/02a).
- **Aktualität:** `constraints/rules.md` und `lookup/*` sind aktuell
  (Stand Juni 2026). Die in Review 02 festgestellte Drift in
  `processes/quality-gates.md` (60%-Coverage-Übergang) bleibt als
  AUFG-02-04 bestehen und wird hier nicht erneut geführt.

| Datei/Verzeichnis | Inhalt | Qualität | Anmerkung |
|---|---|---|---|
| `AGENTS.md` (root) | Orchestrator: Rollen, Trigger-Routing, 6 Subagents, 5 Skills, 23 RULE-XX-Kurzregeln | ⭐⭐⭐⭐⭐ | Delegiert sauber; CONSTRAINTS.md als SSOT klar markiert |
| `packages/core/AGENTS.md` | Core-Layer: Agents-first-Pattern, Capabilities-Tabelle, „Neuen Agent hinzufügen"-Schritte | ⭐⭐⭐⭐⭐ | Architektonisch mustergültig; zeigt Meta/Universal/Feature-Aufteilung |
| `apps/api/AGENTS.md` | Service-Layer: Agent-First-Pattern mit Code-Beispiel, Repository-Pattern, RULE-11 | ⭐⭐⭐⭐⭐ | Direkt umsetzbar; ❌-Beispiele für RULE-01b/02-Verstöße |
| `.opencode/context/narrare-dev/` | 35 extrahierte Kontext-Dateien, alle <200 Zeilen, mit Source/Priority-Metadaten | ⭐⭐⭐⭐⭐ | Context-Window-effizient; referenziert Doku statt reproduziert |
| `.agents/skills/building-pydantic-ai-agents/` | Pydantic-AI v1 Patterns (TestModel, FunctionModel, Capabilities, Hooks, ProcessHistory) | ⭐⭐⭐⭐⭐ | Deckt bekannte Gotchas ab (`@agent.tool` vs `@agent.tool_plain`, Model-String-Provider-Prefix) |
| `.agents/skills/mem0/` | mem0 OSS / AsyncMemory Patterns | ⭐⭐⭐⭐ | Referenz `client/python.md` lädt AsyncMemory OSS korrekt |
| `.opencode/commands/` | 6 Commands (recall, remember, opsx-*) | ⭐⭐⭐⭐ | Schlank; keine Redundanz |
| `.opencode/skills/` | 6 opencode-native Skills (context7, openspec, task-management) | ⭐⭐⭐⭐ | Korrekt von `.agents/skills/` getrennt |

---

## 3. Agent-System während der Tool-Nutzung

**Bewertung:** ⭐⭐⭐⭐⭐ `Konsequente NarrareAgent-Vererbung, ModelRegistry-only, pydantic-graph-Orchestrierung`

**Befunde:**

- **Vererbung (ADR-026):** Alle 26 produktiven Agent-Klassen erben von
  `NarrareAgent[DepsT, OutputT]` (grep über `packages/core`):
  `ChatAgent`, `ChapterSummaryAgent`, `DraftAgent`, `OutlineAgent`,
  `ReviewAgent`, `KBAgent`, `KBAssistAgent`, `KBImproveAgent`,
  `KBMergeAgent`, `ExtractionAgent`, `ReadabilityAgent`, `TimelineAgent`,
  `CharacterArcAgent`, `TemporalExtractionAgent`, `FactExtractorAgent`,
  `ConsistencyAgent`, `StorySuggestAgent`, `CoreferenceAgent`,
  `BetaReaderAgent`, `WorldbuildingAgent`, `PreferenceAnalysisAgent`,
  `PromptLiveTestAgent`, `CharacterVoiceAgent`, `POVDetectionAgent`,
  `InlineSuggestAgent`, `WikiGenerationAgent`. Keine Ausnahme gefunden.
  Damit erhält **jeder** produktive LLM-Aufruf automatisch
  `NarrareObservability` + `NarrareUniversalRules` + `NarrareMeta`.
- **RULE-01b-Durchsetzung:** `scripts/architecture/agent_checks.py:78-112`
  flaggt rohe `Agent(...)`-Konstruktor-Aufrufe außerhalb `core/agents/`.
  Einzige genehmigte Ausnahmen (in `pyproject.toml` und CONSTRAINTS.md §7
  dokumentiert, Review 01 bestätigt): `llm/gateway.py` (Convenience
  `run()` ADR-015) und Wiki-Agent-Adapter. Keine neue Exception.
- **ModelRegistry-only:** `ModelRegistry.get_model()` (`gateway.py:87-121`)
  ist der einzige Weg zu einem `Model`. Services nehmen
  `ModelRegistry` + `ResolvedModelConfig` via DI (Stichprobe über alle
  `__init__`-Signaturen der obigen Agent-Services bestätigt). Die
  Kaskade `project_intent → project_category → user_intent → user_category
  → user_default → ConfigurationError` ist in `model_routing.py:7-9`
  dokumentiert; Resolver ist Service-Layer, Gateway ruft nie direkt.
- **Spezialisierung:** Narrare hat fachlich spezialisierte Agenten pro
  Domäne (Schreib-Agent, Review-Agent, KB-Agent, Analyse-Agenten für
  Readability/POV/Coreference/Consistency/BetaReader/CharacterVoice,
  Planning-Agenten für Timeline/CharacterArc/TemporalExtraction,
  Fact-Extractor, Preference-Analysis). Kontext wird typisiert über
  `*Deps`-Dataclasses pro Agent weitergegeben.
- **Multi-Agent-Orchestrierung:** `WritingGraph`
  (`agents/writing_graph.py`) nutzt `pydantic-graph` (GraphBuilder-API)
  für den Workflow `plan_outline → write_draft → review_draft →
  (revise_draft ↔ review) → finalize`. Context-Weitergabe über
  `WritingState` + `WritingDeps`; Agent-Instanziierung über
  `get_or_create_agent` (cached). `AgentRegistry`
  (`agents/registry.py:89-145`) bietet `get_or_create` + `invalidate`
  mit Cache-Key aus (agent_type, model, system_prompt).
- **History/Conversations (ADR-034):** `HistoryPolicy` (NONE für
  Task-Agenten, CONVERSATIONAL für ChatAgent) ersetzt deprecated
  `history_processors`. `ProcessHistory` (`agents/process_history.py`)
  ist die aktuelle API. `StreamEvent.new_messages` wird an
  `ProcessHistory.add()` weitergereicht (`base.py:204-209` Doku-Beispiel).
- **Versionierung:** Feature-Prompts tragen `prompt_version` im
  Frontmatter; Agents sind via Git + Prompt-Versionen versioniert.
  Capability-Inhalte (Meta/Universal) sind ebenfalls frontmatter-versioniert.
- **Einschränkung (siehe AUFG-03-01):** `writing/pipeline_interview.py:58-78`
  umgeht `NarrareAgent` und ruft `pipeline._registry.run()` direkt auf
  (mit `# pyright: ignore[reportPrivateUsage]`). Das ist die „1 inline
  fallback(s)"-Notiz im `check-adoption`-Report für writing/interactive_session.
  Architektonisch inkonsistent: Interview-Fragen erhalten damit **keine**
  NarrareMeta/UniversalRules/Observability-Capabilities und keinen
  Agent-Registry-Cache. `ModelRegistry.run()` ist eine genehmigte
  ADR-015-Exception, sollte aber nicht für neuen feature-Prompt-Pfad
  genutzt werden.

---

## 4. Interview-System

**Bewertung:** ⭐⭐⭐⭐ `Drei-Modi-KB-Interview + Writing-Interview solide; ein Architektur-Pfad inkonsistent`

**Befunde:**

- **KB-Assist-Interview (`kb/assist_service.py`):** Drei Modi über
  `KBAssistAgent` — `interview` (eine wichtigste Frage nach der anderen,
  Intent `KB_INTERVIEW`), `suggest` (Feld-Vorschlag, `KB_SUGGEST`),
  `enhance` (Bulk-Generierung, `KB_ENHANCE`). Intent-Mapping in
  `_INTENT_MAP` (`assist_service.py:42-46`). Deps werden mit
  Template-Struktur + Proactive-Context (World-Context) gebaut.
  Antworten fließen als `existing_fields` in die nächste Runde und als
  Runtime-Kontext in nachfolgende AI-Aufrufe.
- **Writing-Interview (`writing/pipeline_interview.py`):**
  Interview-gestützter Generierungsmodus — generiert Interview-Fragen
  via LLM, die API-Schicht sammelt Antworten und ruft die Pipeline erneut
  im `full_draft`-Modus auf. **Architektur-Schwäche:** nutzt
  `ModelRegistry.run()` direkt statt `NarrareAgent` (siehe AUFG-03-01),
  sodass die Interview-Fragen nicht die garantierten Capabilities
  erhalten. Adoption-Checker führt dies als „1 inline fallback(s)".
- **Frontend-Integration:** `packages/web/components/studio/kb/` enthält
  vollständige Interview-UI (`KBInterviewView`, `InterviewHeader`,
  `InterviewProgressBar`, `InterviewQuestionCard`, `InterviewCompleteState`,
  `InterviewErrorState`) mit Rendering- und Interactions-Tests. Detaillierte
  UX-Bewertung obliegt Frontend-Specialist (Abschnitt 7/8).
- **Interview-Arten:** Aktuell KB-Interview (entity creation) und
  Writing-Interview (chapter generation). Plot-/Weltenbau-/Charakter-Interviews
  als eigenständige Modi existieren nicht als separate Interview-Systeme,
  sondern werden über KB-Assist + jeweilige `entity_type` abgedeckt
  (Charakter-, Orts-, Fraktions-Entitäten im KB).
- **Integration:** KB-Assist ist in den KB-Creation-Flow integriert;
  Writing-Interview ist über `GenerationMode.INTERVIEW` in der
  Writing-Pipeline ansprechbar. API-Endpunkte in `kb/router_sessions.py`
  und Writing-WS-Handler vorhanden.

---

## 5. MCP-Server

**Bewertung:** ⭐⭐⭐⭐ `Bewusst post-MVP geplant; Status korrekt, aber Feature-File referenziert Phantom-Pfade`

**Befunde:**

- **Implementierungsstatus: NICHT IMPLEMENTIERT (bewusst post-MVP).**
  Verifiziert: kein `apps/mcp/`, kein `tools/mcp-server/`, kein
  `FastMCP`/`@mcp.tool`/`mcp.server`-Import irgendwo in `apps/`/`packages/`.
  Review-00 und Feature-Index (`INFRA-008 status: planned`) dokumentieren
  das übereinstimmend. Q-001 (MCP-Auth: Service-Account-Token vs.
  User-Delegated-JWT vs. OAuth) ist offen — korrekt, weil die Entscheidung
  vor Implementierungsbeginn gefällt werden muss.
- **Kein Defekt, sondern Roadmap-Status.** Wird daher nicht als
  Implementierungsfehler geführt.
- **Governance-Risiko (klein):** `docs/features/infra/INFRA-008-mcp-integration.md`
  referenziert `service: tools/mcp-server/narrare_mcp/server.py` und
  erwähnt `narrare auth login` (CLI) — beides existiert nicht. Die
  Feature-Datei beschreibt eine Idee, nicht den Ist-Zustand. Das ist als
  solche gekennzeichnet (`status: planned`), könnte aber beim Lesen
  irreführen. Gleiche Art von Pfad-Phantom wie bei A2A (siehe AUFG-03-03).
- **Tool-Inventar:** nicht anwendbar (nicht implementiert).

| Tool-Name | Beschreibung | Qualität der Beschreibung | Fehlt in anderen Layern? |
|---|---|---|---|
| _n/a_ | MCP-Server nicht implementiert (INFRA-008 `planned`, Q-001 offen) | n/a | n/a |

---

## 6. A2A

**Bewertung:** ⭐⭐⭐⭐ `Bewusst post-MVP geplant; Status-Drift in Feature-Datei ("in progress" vs. Realität)`

**Befunde:**

- **Implementierungsstatus: NICHT IMPLEMENTIERT (bewusst post-MVP).**
  Verifiziert: kein `apps/a2a/`, kein `apps/api/narrare/a2a/`, kein
  A2A-Router, keine `a2a`/`agent-to-agent`-Imports. Q-002 (Streaming:
  ja/nein für A2A) ist offen.
- **Status-Drift (AUFG-03-03):** `docs/features/infra/INFRA-006-a2a-integration.md`
  trägt `status: in progress`, obwohl keine Implementierung existiert.
  Zusätzlich referenziert die Datei Pfade im **alten** Router-Schema
  (`apps/api/routers/a2a.py`, `apps/api/a2a/server.py`) — das aktuelle
  Router-Schema ist `apps/api/narrare/<domain>/router.py`, und
  `apps/api/routers/` existiert gar nicht. Feature-Index führt INFRA-006
  ebenfalls als „in progress", Adapter-Abschnitt im Feature-Index hält
  A2A als Roadmap/Idee. Diese Inkonsistenz ist dokumentiert in Review-00
  CTX-004, aber nicht als AUFG aufgenommen. Siehe AUFG-03-03.
- **Kein Implementierungsfehler.** MCP/A2A sind Architektur-entschieden
  post-MVP. Meldung als Risiko/Statusdrift, nicht als Defekt.
- **Vorbeugung:** Services/Contracts liegen so, dass künftige Adapter
  auf Core/API-Contracts aufsetzen können, ohne Router-Factories zu
  kopieren (Review 01, Abschnitt 3). API-DI-Factories enthalten jedoch
  einige adapterrelevante Wirings (Memory `_persist_adapter`, Writing-Session
  Runtime-Auflösung) — wenn MCP/A2A kommen, sollten diese in
  adapterunabhängige Factorymodule extrahiert werden.

| Tool-Name | Beschreibung | Qualität der Beschreibung | Fehlt in anderen Layern? |
|---|---|---|---|
| _n/a_ | A2A-Server nicht implementiert (INFRA-006 `in progress` laut Feature-File, aber keine Code-Realität; Q-002 offen) | n/a | n/a |

---

## 7. WebUI

> Finalisiert durch `NarrareFrontendSpecialist` (2026-06-29). Core-Sicht
> als Kontext belassen; Frontend-Evidenz (Komponenten-Struktur,
> State-Management, AI-UX-Präsentation) darunter finalisiert.

**Bewertung:** ⭐⭐⭐⭐⭐ `AI-UX-Disziplin ist das Aushängeschild; Komponenten-/State-Struktur sauber und maschinell abgesichert`

**Befunde (Core-Sicht, Kontext):**

- **Backend-Anbindung:** WebUI konsumiert REST + SSE + WebSocket über
  die Domain-Router. `check-streaming` (Review 01) grün: 3 SSE-Endpunkte
  vollständig über `connectSSE()` in
  `packages/web/lib/api/streaming.ts` angebunden (RULE-20).
  `DEFAULT_CONNECT_TIMEOUT_MS = 30_000`, `AbortSignal.any()` für
  Caller-Signal + internes Timeout, `SSEStreamError`-Normalisierung.
- **AI-UX-Gate:** `check-ai-ux` (Review 01/02) grün — 0 Violations,
  3 governed exclusions. Damit ist die AI-Interaktions-Disziplin
  maschinell abgesichert.
- **Writing-Session:** WebSocket-basiert (`router_sessions.py`,
  `ws_turn_service.py`, `ws_session_context.py`,
  `_ws_draft_dispatch.py`). `ws_idle_timeout` ist real verdrahtet
  (Review 01, Abschnitt 5). SSE-fähige AI-Backends haben Frontend-SSE
  (RULE-20 via `check-streaming` erzwungen).
- **Agent-sichtbare Features:** Vollständige API-Abdeckung für
  Write/Extend/Rewrite/Co-Author/Chat/Suggest, Analysis (Readability,
  POV, BetaReader, Consistency, Coreference, CharacterVoice, Sentiment),
  KB (CRUD + Interview/Suggest/Enhance/Extract/Improve/Worldbuild/Merge),
  Planning (Outline/Timeline/CharacterArc/TemporalExtraction).

**Befunde (Frontend-Sicht, finalisiert):**

- **Komponenten-Struktur:** Sauber domänengegliedert unter
  `packages/web/components/studio/{editor,kb,analysis,planning,settings,
  wizard,learning}/`. Pages sind dünne Wrapper (z. B.
  `app/(studio)/page.tsx` → `EditorView`), die nur eine View-Komponente
  rendern (ui-principles §2). `app/(studio)/layout.tsx` implementiert die
  `size-full flex` Shell ohne Header-Bar/Body-Scroll. Schwergewichtige
  Panels sind entlang einer Controller-Hook-Spalte zerlegt (z. B.
  `GenerationPanel.tsx` 166 Zeilen → `generationPanelController.ts`,
  `CoAuthorPanel` → `_components/{useCoAuthorStream,useCoAuthorHandlers,
  useCoAuthorReviewState,...}`). Diese Decomposition ist konsistent und
  hält Panels unter RULE-04.
- **Service-Layer-Konsistenz (lib/api):** 40+ typisierte API-Module
  (`generation-streams.ts`, `suggest.ts`, `coauthor.ts`, `chat.ts`,
  `kb-sessions.ts`, `prompts.ts`, …) trennen Transport/Akkumulation
  sauber vom UI. SSE-Consumer rufen alle `connectSSE()`
  (`streaming.ts:124`); REST-Consumer nutzen den zentralen `apiClient`.
  `streamRewrite`/`streamStyleVariantRegeneration`/`streamExtend`
  (`generation-streams.ts`) teilen sich dasselbe Callback-Muster
  (`onRequestInfo`/`onChunk`/`onComplete`/`onError`) und dieselbe
  `<alternative label="…">`-Tag-Parser-Logik (`parseAlternatives`,
  `generation-streams.ts:109`) — keine Duplikat-Implementierungen.
  `streamRewrite`- und `streamStyleVariantRegeneration`-Rümpfe sind
  fast identisch (jeweils ~60 Zeilen emit/complete-Logik); das ist ein
  kleines, vertretbares DRY-Potenzial, kein Defekt.
- **State-Management-Angemessenheit:** Die dokumentierte Dreiteilung
  (TanStack Query = Server, Zustand = UI, useState = ephemeral) ist
  real gelebt: 100+ `@tanstack/react-query`-Verwendungen
  (queries/mutations über Chapters, KB, Settings, Analysis), 4 schlanke
  Zustand-Stores innerhalb der 150-Zeilen-Store-Grenze
  (`editorStore.ts` 89, `authStore`, `themeStore`, `wizardStore`), und
  komponentenlokales `useState` für ephemere Form-/Selektionszustände.
  **Kleiner Pattern-Smell (kein eigener AUFG):** `editorStore.ts`
  hält neben Panel-Toggles auch imperativ gesetzte Analyse-Ergebnisse
  (`betaReaderResult`, `sentimentResult`, `consistencyResult`) — das ist
  streng genommen server-abgeleiteter State in einem UI-Store. Es ist
  aber mit den Panel-Toggles koordiniert und within-limit; erst bei
  weiterem Zuwachs ein Refactoring-Kandidat (TanStack-Query-Cache).
- **AI-Feature-Präsentation (Streaming/Lade/Fehler-Indikatoren):**
  Das gemeinsame `useAIOperation<T>`-Hook
  (`lib/hooks/use-ai-operation.ts`, dekomponiert in `ai-operation-execute.ts`
  + `ai-operation-lifecycle.ts` + `use-ai-operation.types.ts`) kapselt
  die gesamte §16-Lifecycle-State-Maschine: `idle → loading → streaming
  → complete → error → connection_lost`. Es managt `AbortController`,
  Connection-Loss-Timer (Default 15 s, konfigurierbar), Auto-Retry bei
  Verbindungsverlust (Default 0, konfigurierbar), `operationId`-Race-Schutz
  und ref-stabile Callbacks (`ai-operation-lifecycle.ts:43-193`).
  `mapSSEError` (`ai-error-mapping.ts:72`) mappt HTTP/Network/Parse-Fehler
  auf 7 `aiActions.error*`-i18n-Keys mit `retryable`-Flag
  (401→apiKey, 413→textTooLong, 429→rateLimit, 408→timeout,
  network→connection, parse→parse, default). AbortError wird geschluckt
  (`return null`). **Modell-Komponente `GenerationPanel.tsx` (166 Zeilen):**
  Phase-State-Machine `config → streaming → review → error`,
  Connection-Lost-Banner mit Retry-Button (`aiActions.connectionLost` /
  `.connectionLostRetry`), Fehler-State mit Retry + kontextsensitivem
  Context-Inspector-Hinweis, Keyboard (Escape stop/close,
  Ctrl/Cmd+Enter accept via `lib/ai-action-shortcuts.ts`). Die Partial-Output-
  Erhaltung ist implementiert: Draft bleibt im `review`-State nach
  Verbindungsverlust erhalten (kein Blank-State).
- **AI-Operation-Inventar (§16.9):** `scripts/checks/ai_operation_inventory.yaml`
  dokumentiert **17 AI-Operationen** mit allen §4-Pflichtfeldern
  (transport, lifecycle_owner, loading_feedback, cancel_ui,
  signal_propagation, error_mapping, partial_output, ai_action_i18n,
  deprecated_key_usage, keyboard, tests, aufg_id, status). **14 `compliant`**,
  **3 `governed_exception`** (siehe unten). Das ist die maschinenlesbare
  SSOT für die AI-UX-Compliance, validiert durch `check_10_operation_inventory`.
- **Governed Exclusions (`.ai_interaction_exclude`, 3 Einträge, alle
  ADR-043-konform mit owner/reason/exit/re_evaluated):**
  1. `packages/web/__tests__/connection-lost.test.tsx` (check_5,
     central-test-helper für `useConnectionLost`-Deprecation-Verhalten).
  2. `packages/web/components/studio/editor/extensions/ghost-text-helpers.ts`
     (check_2, non-react-extension — TipTap-Extension läuft außerhalb
     React-Lifecycle, AbortController via Extension-Storage).
  3. `packages/web/lib/hooks/useTimelineExtraction.ts` (check_2,
     non-react-transport — callback-basierte SSE-Akkumulation;
     `useAIOperation` unterstützt kein Callback-SSE; partielle Migration
     angewandt, getrackt in CR-AUFG-07-09).
  Alle drei sind dokumentiert, datiert und haben Exit-Kriterien — keine
  verrotteten Ausnahmen (Check 8 verifiziert das).
- **i18n-Vocabulary (§16.4/§16.8):** `studio.aiActions.*` ist das
  kanonische Vokabular (21 Keys, DE/EN/FR-Parität). 16 deprecated Aliase
  (`aiModal.*`, `generation.stop/accept/reject`, `annotation.*`,
  `rewrite.cancel/replace`, `sessionPanel.addToDraft`, `kb.sessions.*`,
  `learning.rating`, `coAuthor.*`) wurden entfernt; Check 6
  (`check_6_deprecated_alias`) erzwingt deren Abwesenheit. Die
  `i18n-namespace-registry.test.ts` sichert RULE-16 (alle
  `useTranslations`-Namespaces registriert).
- **Frontend-Gates (aus Review 01/02, hier validiert):**
  `check-frontend-size` grün (0 current / 0 baseline),
  `check-streaming` grün, `check-ai-ux` grün (0 Violations),
  `pnpm test` funktional grün (274 Dateien / 2.287 Tests). Die
  Frontend-Test-Laufzeit (182 s) und React-`act(...)`-Warnings sind
  Review-02-Befunde (AUFG-02-03), keine WebUI-Architektur-Defekte.
- **Frontend-spezifischer Befund — File-Size-Gate-Klassifikationslücke
  (AUFG-03-04):** `check_frontend_file_size.py:_limit_for` klassifiziert
  nach Dateiname: `use*.ts` → Hook (150), `*Store.ts` → Store (150),
  sonst `.ts` → typescript (400). Hook-Dateien, die ohne `use`-Präfix
  benannt sind (`TipTapEditorController.ts`, `generationPanelController.ts`),
  entkommen damit der 150-Zeilen-Hook-Grenze und werden als 400-Zeilen-
  typescript-Datei bewertet. Konkret: `TipTapEditorController.ts` = 400
  Zeilen (exakt an der typescript-Grenze; `lines > limit` ist `400 > 400` =
  False), `generationPanelController.ts` = 268 Zeilen (deutlich über
  Hook-150, aber unter typescript-400). Beide exportieren Hooks
  (`useTipTapEditorController`, `useGenerationPanelController`). Siehe
  AUFG-03-04 für die Gate-Logik und AUFG-01-03 für die Modularisierung.

---

## 8. TipTap & Editor-AI-Integration (Das Herzstück)

> Finalisiert durch `NarrareFrontendSpecialist` (2026-06-29). Core-Sicht
> als Kontext belassen; Frontend-Evidenz (AI↔ProseMirror-Dokumentmodell,
> Ghost-Text-Injektion, Magic-Menü-Kapselung, Accept/Reject-UX,
> connectSSE/AbortController/Partial-Output/Retry) darunter finalisiert.

**Bewertung:** ⭐⭐⭐⭐⭐ `State-of-the-Art Editor-AI-Integration; AIAnnotation-Mark-System + GhostText-Dekorationen + useContinueStream sind vorbildlich gekapselt`

**Befunde (Core-Sicht, Kontext):**

- **Streaming-Architektur (RULE-13/20):** Streaming- und
  Nicht-Streaming-Pfade teilen sich dieselbe Service-Signatur; SSE ist
  der Transport für AI-Antworten. `connectSSE()` mit `AbortSignal.any()`
  ist die zentrale SSE-Hilfsfunktion. AI-Backends (Writing, Chat,
  Live-Test) exponieren SSE; `check-streaming` stellt die
  Frontend-Anbindung sicher. Eine Trennung „AI-Stream blockiert UI"
  ist über SSE architektureseitig ausgeschlossen.
- **Inline-Suggest (`inline_suggest_agent.py` / `suggest_service.py`):**
  Es existiert ein AI-Inline-Suggest-Pfad über `InlineSuggestAgent`
  (Intent `SUGGEST`, Mode `inline_suggest`) — die TipTap-seitige
  Injizierung als Ghost-Text/Inline-Suggestion ist Frontend-Aufgabe
  (unten finalisiert).

**Befunde (Frontend-Sicht, finalisiert):**

- **AI-Response ↔ ProseMirror-Dokumentmodell — das `AIAnnotation`-System
  (`extensions/AIAnnotation.ts` 345 Zeilen + `aiAnnotationApi.ts`):**
  AI-generierter Text wird als `aiGenerated`-**Mark** (ProseMirror-Mark
  mit Attributen `requestId`, `source`, `originalText`, `status`,
  `createdAt`) ins Dokument injiziert — kein flüchtiger State, sondern
  Teil des persistenten Dokumentmodells, das Transaktionen überlebt
  (`inclusive: false`, `excludes: "_"`). Der `AIAnnotationTracker`-Plugin
  (`AIAnnotation.ts:281`) erzwingt eine Single-Pending-Mark-Constraint
  (`appendTransaction`: auto-resolvt alle außer der neuesten pending Mark)
  und injiziert eine Floating-Action-Decoration am Mark-Ende
  (`Decoration.widget(to, anchor, {side:1})`). **Modify-Detection**
  (`onUpdate`, `AIAnnotation.ts:322`): vergleicht aktuellen Mark-Text
  gegen `originalText`-Attribut und speichert eine `PendingModification`
  — das ist die zuverlässige Baseline für Accept/Modify/Rating. Da
  TipTaps `Extension.create`-Proxy Closures am Transaktions-Dispatch
  hindert, sind alle Mutationen als Standalone-Funktionen in
  `aiAnnotationApi.ts` mit explizitem `editor`-Parameter ausgelagert;
  Storage-Methoden sind dünne Wrapper via `_editorRef`. Das ist eine
  saubere, dokumentierte architektonische Entscheidung (WRITE-003/D4).
- **Flüssige AI-Injektion via `useContinueStream.ts` (143 Zeilen,
  Modell-Hook):** Kapselt den „Continue Writing"-SSE-Flow und brückt
  ihn in die ProseMirror-Mark-Lebenszyklus: erstes Chunk →
  `notifyData()` (loading→streaming) + `insertAIContent()` (öffnet
  pending Mark); weitere Chunks → `appendToPendingMark()`;
  Complete → `finalizePendingMark(accumulated)` (friert `originalText`-
  Baseline ein für Modify-Detection). Signal-Propagation: `useAIOperation`
  → `streamExtend` → `connectSSE` (Check 7 validiert das). Der Rewrite-
  Flow (`TipTapEditorController.ts:207` `rewriteAiOp`) nutzt denselben
  `useAIOperation`-Lifecycle und akkumuliert `<alternative>`-Tags in den
  `aiSuggestion`-State, der über `replaceSelectionWithAIContent` /
  `insertAIContentAt` injiziert wird.
- **Ghost-Text / Inline-Suggestions (`extensions/GhostText.ts` 299 Zeilen
  + `ghost-text-helpers.ts` / `ghost-text-suggestions.ts` /
  `ghost-text-types.ts` / `ghost-text-error-status.ts`):** Copilot-Stil-
  Inline-Vervollständigung via `ProseMirror Decoration.widget(suggestionPos,
  ghostSpan, {side:1, key:"ghost"})` (`GhostText.ts:284`). Phase-4-Features
  voll implementiert: prefix-basiertes LRU-Caching (`_cacheMaxSize: 50`,
  `_cacheMaxAge: 30_000`), Debounce-Auto-Trigger (≥5 Chars, 800 ms Pause),
  Tiping-Mismatch-Detection (Match → Auto-Advance, Mismatch → Clear),
  Character-Streaming (30 ms/Char), Analytics-Counter
  (accepted/rejected/total). **§16.3 Loading-Feedback:** Fetching-Status-
  Decoration (`ghost-text-fetching` Span) zeigt `fetchingStatusText`
  während Inflight — Text kommt aus React-Options
  (`TipTapEditorController.ts:146` `t("aiActions.aiThinking")`), kein
  hardcoded English im ProseMirror-DOM (ADR-043 Note 7). **Transienter
  Fehler-Indikator (CR-AUFG-07-15):** bei Non-AbortError-Fetch-Failures
  erscheint eine `ghost-text-error`-Decoration mit
  `t("ghostText.errorUnavailable")`, auto-clear nach 4 s. Die
  SSE-Anbindung läuft über `createSseSuggestionFetcher` (`suggest.ts:40`),
  die `connectSSE` nutzt und `mapSSEError` auf Transport-Ebene anwendet —
  vollständige `useAIOperation`-Migration ist bewusst nicht möglich
  (TipTap-Extension außerhalb React-Lifecycle), als governed exception
  klassifiziert (`.ai_interaction_exclude` #2).
- **Magic-Menü-Kapselung (Slash-Commands,
  `components/studio/editor/slash-commands/`):** Vorbildliche
  Separation-of-Concerns in 7 Dateien: reiner Parser
  (`parser.ts` / `slash-state.ts:resolveSlashState`) → React-Host-Hook
  (`useSlashCommandState.ts` 135 Zeilen, abonniert Editor-Transaktionen,
  bindet selbst keine Key-Handler) → presentational Menu
  (`SlashCommandMenu.tsx` 156 Zeilen, fully-controlled, owns-no-state,
  isst nur während gemountet Nav-/Selection-Keys via
  `event.preventDefault()/stopPropagation()`). Kommando-Registry
  (`registry.ts`), Contract-Typen (`contracts.ts`), Item-Builder
  (`menu-items.ts`). Auf Selektion löscht der Hook das `/query`-Prosa
  sauber via `deleteRange` (`useSlashCommandState.ts:120`).
  Conflict-Garantie (spec §43): der Hook *reagiert* nur auf
  Dokumenttext und stiehlt keine TipTap-Shortcuts; das Menü isst nur
  `ArrowDown/Up/Enter/Escape/Tab` während es offen ist. Das ist die
  korrekte Kapselung für ein In-Editor-Kommando-Palette.
- **Accept/Reject-UX:** Pending `aiGenerated`-Marks tragen die
  Floating-Action-Decoration; `acceptMark(requestId)` / `rejectMark(requestId)`
  (`aiAnnotationApi.ts`) setzen Status → `accepted`/`rejected` und
  triggern Feedback-Callbacks (Rating → `POST /memory/feedback` via
  `ai-rating/adapters/*`). Rewrite/Co-Author bieten
  `accept`/`reject`/`replace`/`insertAsNew`/`acceptAll`/`rejectAll`/
  `applySelected` — alle aus `studio.aiActions.*`. Shared
  Diff-View (`components/shared/ai-diff/AIDiffView` via
  `lib/ai-diff/adapters/{rewrite,coauthor,kb-enhance}.ts`,
  CR-AUFG-07-18) vereinheitlicht die Before/After-Darstellung über
  Writing + KB. Ctrl/Cmd+Enter ist der standardisierte Accept-Shortcut
  (`lib/ai-action-shortcuts.ts`, CR-AUFG-07-13).
- **connectSSE-Nutzung für AI-Endpunkte (RULE-20 / UI §16.1):** Alle
  14 SSE-AI-Operationen im Inventar nutzen `connectSSE()` als einzigen
  Transport — verifiziert via `callers_of connectSSE` und
  `check-streaming`. Der Transport (`streaming.ts:124`) kombiniert
  Caller-Signal + internes Timeout-Signal via `AbortSignal.any()`,
  nutzt native `fetch` + `ReadableStream` (axios kann kein SSE),
  parst Double-Newline- und Single-Line-Events und normalisiert Fehler
  über `normalizeSSEError` → `SSEStreamError{kind: abort|http|network|
  parse|stream}`. `[DONE]`-Frame → `onComplete`. Das ist die zentrale,
  korrekt implementierte SSE-Disziplin, die UI §16.1 maschinell
  durchsetzt.
- **AbortController / Partial-Output / Retry:** `useAIOperation`
  (`ai-operation-lifecycle.ts`) managt den vollständigen
  Connection-Loss-Zyklus: bei jedem `notifyData()`-Chunk wird der
  Connection-Loss-Timer zurückgesetzt (`startConnectionLossTimer`);
  läuft er ab, → `status: connection_lost` + `abort()` + Auto-Retry bis
  `maxConnectionRetries` (via `operationId`-Race-Schutz). **Partial-Output-
  Erhaltung** ist mehrschichtig: AIAnnotation-Marks bleiben im Dokument
  erhalten (Extend/Continue), Chat-/BetaReader-Nachrichten bleiben im
  State, Rewrite-Alternativen bleiben bis Accept/Reject. Beim WebSocket-
  Writing-Session (`useSessionSocket.ts`): Server-seitiger Stop via
  `stop_generation`-Message (ADR-052), Recovery via `?session_id=...`-
  Reattach an gecachten Shared-State, `recoveryState: idle→reconnecting→
  (recovered|recovery_failed)` treibt `SessionReconnectBanner`.
  `partial_prose` wird auf Stop und Disconnect erhalten
  (`SessionTurnStateStore`). Das ist §16.7 (Connection-Lost-Regel) in
  vollem Umfang umgesetzt, nicht nur für SSE sondern auch WebSocket.
- **Hotspot-Risiko (Review 01 AUFG-01-03, Frontend-präzisiert):**
  `TipTapEditorController.ts` ist mittlerweile **400 Zeilen** (war 335
  im Graph-Snapshot von Review 01) und exportiert den zentralen
  Editor-Controller-Hook `useTipTapEditorController` (Graph-Degree 117).
  Der Hook bündelt derzeit: TipTap-`useEditor`-Setup + Extension-Wiring,
  Rewrite-AI-Lifecycle (`rewriteAiOp`), Style-Variant-Regeneration,
  Accept/Reject/Insert-Handler, GhostText-Onboarding-Observation und
  Autosave-Config. Kein aktueller RULE-04-Bruch (siehe AUFG-03-04 zur
  Gate-Klassifikation), aber der zentrale Blast-Radius-Knoten vor weiterer
  Feature-Anlagerung. Die Decomposition-Pattern ist im Projekt bereits
  etabliert (`useContinueStream`, `_components/useCoAuthor*`,
  `generationPanelController`); `useTipTapEditorController` sollte
  analog in Persistence-/Command-/AI-Orchestration-/GhostText-Onboarding-
  Sub-Hooks zerlegt werden, bei stabiler öffentlicher Hook-API. Siehe
  AUFG-01-03 (aktualisiert).

---

## 9. AI-Verbesserungspotenzial für den Nutzer

**Bewertung (aktuelles Unterstützungsniveau):** ⭐⭐⭐⭐ `Breite AI-Abdeckung über Writing/Analysis/KB/Planning; einige 2024/25-Patterns bereits angelegt, andere als Intent/ADR vorbereitet`

**Befunde — bereits vorhanden:**

- **Inline-Suggestions (Copilot-Stil):** teilweise — `InlineSuggestAgent`
  (Intent `SUGGEST`, Mode `inline_suggest`) + `StorySuggestAgent`
  (Mode `story_suggest`). Ausbau zu echten Prosa-Ghost-Text-Suggestions
  ist primär Frontend-Aufgabe (TipTap).
- **Writing-Style-Analyse / Konsistenz:** stark — `CharacterVoiceAgent`
  (ANAL-008, ADR-055) liefert Voice-Profile pro Charakter mit
  Deterministic-Metrics-Hybrid; `ConsistencyAgent` + `FactExtractorAgent`
  (ADR-044) decken Cross-Chapter-Konsistenz mit Provenance ab;
  `BetaReaderAgent` simuliert Leserperspektive über 5 Dimensionen.
- **Charakter-Konsistenz-Tracking:** vorhanden — `CharacterVoiceAgent`
  prüft, ob Figuren typisch sprechen; `ConsistencyAgent` prüft
  Charakter-Konsistenz über Kapitel.
- **Plot-Hole-Detection:** teilweise — `ConsistencyAgent` (Kapitel-Konsistenz
  gegen KB) + `FactExtractorAgent` (Fakten mit Confidence/Provenance)
  sind die Bausteine; eine eigenständige „Plot-Hole-Detection"-Pipeline
  über strukturierte Story-Analyse existiert nicht als isolierter Flow,
  ist aber über die vorhandenen Agents zusammensetzbar.
- **Leser-Perspektiven-Simulation:** vorhanden — `BetaReaderAgent`
  (genre-sensitiv, 5 Dimensionen, mit Textreferenzen).
- **Emotionale Intensitätskurve:** teilweise — `Sentiment`-Intent
  existiert (deterministisch, Non-Routeable); eine Visualisierung über
  das ganze Manuskript ist keine Core-Feature, sondern Frontend/Dashboard.
- **Autonome Research-Agenten:** NICHT vorhanden — `RESEARCH`-Intent ist
  in `NON_ROUTEABLE_INTENTS` („Research synthesis has no bundled
  PromptComposer route yet"). Bewusst verschoben, kein Defekt.

**Befunde — wertvolle Ergänzungen (architektonisch sauber andockbar):**

1. **Autonome Web-Research für Weltenbau-Details** — Mittelaufwand,
   Voraussetzung: Decision ob/sowie Provider für Web-Suche. `RESEARCH`-Intent
   ist als Platzhalter angelegt; eine ADR müsste Cascade + Provider
   festlegen. Kein Quick-Win, da Tool integriert werden muss (kein
   reiner Prompt).
2. **Emotionale Intensitätskurve über Kapitel visualisiert** —
   Geringer/Mittelaufwand, da `Sentiment`-Pipeline vorhanden und
   Recharts im Stack ist. Vor allem Frontend/Aggregation, kein Core-AI-Thema.
3. **Multi-Draft-Vergleich mit AI-Feedback** — Mittelaufwand,新 Intent +
   Template nötig; Architectural sauber andockbar über bestehende
   PromptComposer-Cascade.
4. **Author-Voice-Drift über Manuskript** — ADR-055 D4 hat `VOICE` als
   Multi-Mode-Intent angelegt; `author_voice` (ANAL-007) und
   `voice_drift` (ANAL-009) sind als kommende Modes deklariert. Damit
   ist die architektonische Vorarbeit geleistet — Implementierung
   pending, kein Architekturriskiko.

**Bewertung:** Die AI-Patterns, die 2024/25 für Prosa-Tools State-of-the-Art
sind, sind entweder vorhanden (BetaReader, Voice-Profile, Consistency,
Beta-Reader-Perspektive) oder als Intent/ADR vorbereitet (Author-Voice,
Voice-Drift, Research). Schwäche: keine autonomen Agenten mit
Tool-Nutzung (Web-Research) — bewusst post-MVP, aber ein Differenzierungs-
potenzial gegenüber statischen Schreibtools.

---

## Gesamtbewertung AI-Features & Prompting

**Bewertung:** ⭐⭐⭐⭐⭐
**Vorherige Bewertung:** _keine direkte Vorgängerbewertung für Review 03 in diesem Audit-Zyklus_ | **Trend:** ➡️ Neueinordnung auf hohem Niveau
**Zusammenfassung:** Das AI/Prompting-System ist das architektonische
Aushängeschild von Narrare. PromptComposer-Cascade, Capability-Based
Injection (ADR-026), Routeable-Intent-Governance (ADR-037/046/049),
maschinelle Prompt-Surface/Orphan/Identity/Variable-Checker und
Agent-First-Disziplin (26 Agenten, alle via NarrareAgent, ModelRegistry-only,
RULE-01b durchgesetzt) sind vorbildlich umgesetzt und CI-blockierend
abgesichert. Dev-Agent-Anweisungen sind hierarchisch, SSOT-diszipliniert
und Context-Window-effizient. MCP/A2A sind bewusst post-MVP und als
solche korrekt dokumentiert (Q-001/Q-002 offen). Die verbleibenden
Befunde sind architektonische Konsistenz-Punkte (ein Inline-Fallback im
Writing-Interview, ein Invocation-Fallback im KB-Assist) und eine
Governance-Statusdrift bei A2A („in progress" ohne Code) — keine
fundamentalen Defekte.

**Frontend-Bestätigung (Abschnitte 7/8 finalisiert auf ⭐⭐⭐⭐⭐):**
Die Frontend-Seite des AI-Systems ist ebenso stark wie die Core-Seite —
und das ist die andere Hälfte der Gleichung. Das `useAIOperation`-Hook
(`ai-operation-lifecycle.ts`) implementiert die vollständige §16-Lifecycle-
State-Maschine (idle→loading→streaming→complete→error→connection_lost) mit
AbortController, Connection-Loss-Timer, Auto-Retry und operationId-Race-Schutz.
17 AI-Operationen sind im maschinenlesbaren Inventar
(`ai_operation_inventory.yaml`) mit allen §4-Pflichtfeldern dokumentiert
(14 compliant, 3 ADR-043-governed-exception). `connectSSE()` mit
`AbortSignal.any()` ist der einzige SSE-Transport (RULE-20);
`mapSSEError` mappt auf 7 `aiActions.error*`-i18n-Keys. Das
`AIAnnotation`-Mark-System injiziert AI-Text als persistenten ProseMirror-
Mark mit Modify-Detection; `GhostText` liefert Copilot-Stil-Ghost-Text mit
LRU-Cache, Fetching/Error-Dekorationen und Keyboard-Shortcuts; die
Slash-Command-Architektur (Parser → Hook → presentational Menu) ist vorbildlich
gekapselt. Accept/Reject-UX, Partial-Output-Erhaltung (Marks überleben
Disconnect) und Connection-Lost-Recovery (SSE-Timer-Retry + WebSocket-
Session-Reattach via ADR-052) sind vollständig umgesetzt. `just check-ai-ux`
(11 Gates) und `check-streaming` sichern das maschinell. Frontend-seitige
Befunde sind Nachhaltigkeitspunkte (AUFG-01-03 aktualisiert: `TipTapEditorController.ts`
auf 400 Zeilen gewachsen; AUFG-03-04: File-Size-Gate-Klassifikationslücke
für ohne-`use`-Präfix benannte Hook-Dateien), keine Defekte.

---

## Aufgaben

### [AUFG-03-01] Writing-Interview-Pfad von `ModelRegistry.run()` auf `NarrareAgent` umstellen
**Priorität:** Mittel
**Bereich:** AI / Architektur
**Kontext:** `packages/core/narrare_core/writing/pipeline_interview.py:58-78`
umgeht `NarrareAgent` und ruft `pipeline._registry.run()`
(`ModelRegistry.run()`, genehmigte ADR-015-Convenience-Exception) direkt
auf — mit `# pyright: ignore[reportPrivateUsage]` wegen Zugriffs auf die
private Pipeline-Methode `_build_and_validate_prompt` und `_registry`.
Das ist die „1 inline fallback(s)"-Notiz im `check-adoption`-Report für
`writing/interactive_session`. Architektonische Konsequenz:
Interview-Fragen erhalten **keine** `NarrareMeta`/`NarrareUniversalRules`/
`NarrareObservability`-Capabilities (ADR-026) und werden nicht über den
Agent-Registry-Cache geführt. Adoption ist formal compliant (Ratchet 1
current, dokumentiert), aber der Pfad widerspricht dem Agent-First-Muster,
das alle 26 anderen produktiven Agenten konsequent leben.
**Akzeptanzkriterien:**
- [ ] Interview-Fragen-Generierung läuft über einen `NarrareAgent`-Subtypen
      (z. B. Wiederverwendung von `ChatAgent` oder ein dedizierter
      `InterviewQuestionAgent`), sodass Meta/Universal/Observability
      garantiert injiziert werden.
- [ ] Kein `# pyright: ignore[reportPrivateUsage]` mehr in
      `pipeline_interview.py` für `_registry`/`_build_and_validate_prompt`.
- [ ] `check-adoption`-Report zeigt 0 inline fallback(s) für
      `writing/interactive_session` oder der verbleibende Fallback ist
      mit ADR + Reason im Adoption-Registry explizit gouvernement.
- [ ] Bestehende Writing-/Interview-Tests bleiben grün; neu: Test, dass
      Interview-Antworten unter NarrareMeta/UniversalRules entstehen
      (Capability-Injection-Regressionstest).
**Geschätzter Aufwand:** M

### [AUFG-03-02] KB-Assist Invocation-Fallback semantisch verhärten oder als gouvernierte Ausnahme klassifizieren
**Priorität:** Mittel
**Bereich:** AI / Invocation-Integrity (ADR-048)
**Kontext:** `apps/api/narrare/kb/assist_service.py:185-202` fängt einen
Fehler der `compose_invocation()` (ADR-048 Mode 1: Validation +
Enrichment + Evidence-Recording) mit breitem `except Exception` ab,
loggt nur ein Warning und fällt zurück auf direkten
`self._prompt_composer.build()`. Das ist dokumentierte
Graceful-Degradation (RULE-11: nicht silent), umgeht aber für diesen
Pfad die Invocation-Validation, Enrichment und Evidence-Aufzeichnung.
Damit kann der KB-Assist-Pfad Invocation-Evidence unvollständig
produzieren, ohne dass die Ursache (z. B. Pipeline-Misconfiguration)
fail-fast sichtbar wird. Die `assert invocation_result.composed_prompt
is not None` im Erfolgspfad (Zeile 193) ist außerdem ein Runtime-Assert,
das在生产 Code für echte Fehlerorte ungeeignet ist.
**Akzeptanzkriterien:**
- [ ] Root-Cause-Klassifikation: Welche konkreten Exceptions kann
      `compose_invocation()` werfen, und welche sind echte
      Pipeline-Fehler vs. legitme NotFound-/Validation-Fehler?
- [ ] Fallback ist entweder auf konkrete, benannte Exception-Typen
      eingeschränkt (kein bare `except Exception`) ODER als gouvernierte
      Ausnahme mit Reason im Adoption-/Invocation-Registry klassifiziert.
- [ ] Runtime-`assert` (Zeile 193) ist durch echtes Fehler-Handling
      ersetzt (typed Exception + Logging).
- [ ] Bei Fallback bleibt Evidence-Recording best-effort erhalten oder
      der Fallback wird im Invocation-Evidence-Stream als
      `degraded_mode` markiert.
- [ ] Unit-Test deckt beide Pfade (Erfolg + Fallback) mit konkreten
      Fehlertypen ab.
**Geschätzter Aufwand:** S–M

### [AUFG-03-03] A2A/MCP-Feature-Dateien: Status- und Pfadgenauigkeit korrigieren
**Priorität:** Niedrig
**Bereich:** Governance / Docs
**Kontext:** `docs/features/infra/INFRA-006-a2a-integration.md` trägt
`status: in progress`, obwohl keine Code-Implementierung existiert
(kein `apps/a2a/`, kein A2A-Router, keine Imports). Außerdem
referenziert die Datei Pfade im **alten** Router-Schema
(`apps/api/routers/a2a.py`, `apps/api/a2a/server.py`) — das aktuelle
Schema ist `apps/api/narrare/<domain>/router.py`, und `apps/api/routers/`
existiert gar nicht. `INFRA-008-mcp-integration.md` referenziert analog
`tools/mcp-server/narrare_mcp/server.py` (nicht vorhanden) und ein
`narrare auth login`-CLI (nicht vorhanden). Feature-Index führt INFRA-006
ebenfalls als „in progress", was mit Review-00 CTX-004 und der
Adapter-Roadmap kollidiert. Kein Implementierungsfehler (post-MVP
bewusst), aber eine Governance-Genauigkeit, die beim Lesen irreführt
und „Dokumentiert ≠ Implementiert" unterläuft.
**Akzeptanzkriterien:**
- [ ] `INFRA-006`-Status auf `planned` gesetzt (oder `blocked` auf Q-002),
      konsistent mit Feature-Index-Adapter-Abschnitt und Review-00 CTX-004.
- [ ] Phantom-Pfade in INFRA-006/INFRA-008 entweder entfernt oder als
      „geplant, Pfad noch unverbindlich" markiert; insbesondere keine
      Pfade im alten `apps/api/routers/`-Schema.
- [ ] Feature-Index und Adapter-Abschnitt verwenden dieselbe
      Statussemantik für A2A/MCP wie die Feature-Dateien.
- [ ] Optional: ein `check_feature_path_accuracy`-Skript (oder Erweiterung
      eines bestehenden Drift-Checkers) validiert, dass referenzierte
      `service:`/`router:`/`contract:`-Pfade in Feature-Frontmatter
      existieren oder als `planned` markiert sind.
**Geschätzter Aufwand:** S

### [AUFG-03-04] File-Size-Gate: Hook-Dateien ohne `use`-Präfix entgehen der 150-Zeilen-Hook-Grenze
**Priorität:** Mittel
**Bereich:** Frontend / Governance / Tooling
**Kontext:** `scripts/check_frontend_file_size.py:_limit_for` (Zeilen 52–62)
klassifiziert Dateien nach Dateiname: `use*.ts` → Hook (150-Zeilen-Grenze),
`*Store.ts` → Store (150), `page.tsx` → Page (100), sonstiges `.tsx` →
Component (200), sonstiges `.ts` → typescript (400). Hook-Dateien, die
ein `use*`-Hook-Export enthalten, aber ohne `use`-Präfix benannt sind,
werden als generische 400-Zeilen-typescript-Datei bewertet und entgehen
damit der strengeren 150-Zeilen-Hook-Grenze aus ui-principles §15. Konkret
betroffen (Frontend-Review, Stand 2026-06-29):
- `packages/web/components/studio/editor/TipTapEditorController.ts` =
  400 Zeilen (exportiert `useTipTapEditorController`, Graph-Degree 117);
  exakt an der typescript-400-Grenze (`lines > limit` = `400 > 400` = False →
  kein Violation).
- `packages/web/components/studio/editor/generationPanelController.ts` =
  268 Zeilen (exportiert `useGenerationPanelController`); deutlich über
  Hook-150, aber unter typescript-400.
Beide sind funktional React-Hooks (rufen `useEditor`/`useState`/`useEffect`/
`useAIOperation`/`useMutation`), werden aber nach ui-principles §15 als
Hook-Kategorie bewertet werden sollen. Kein aktueller RULE-04-Bruch, weil
das Gate nach Dateiname klassifiziert — aber die Gate-Logik unterläuft die
dokumentierte Hook-Grenze für eine Klasse zentraler Controller-Dateien.
**Akzeptanzkriterien:**
- [ ] Root-Cause-Entscheidung: Entweder (a) die `Controller.ts`-Dateien
      werden konsistent in `use*Controller.ts` umbenannt, sodass das Gate
      sie als Hook (150) klassifiziert, ODER (b) das Gate erkennt Hook-
      Exporte (`export function use*`) statt/zusätzlich zum Dateinamen.
- [ ] Im Fall (a): `check_frontend_file_size` meldet die umbenannten
      Dateien korrekt als Hook-Kategorie; ggf. entstehende Violations
      werden als baseline geführt und modularisiert (siehe AUFG-01-03).
- [ ] Im Fall (b): die Klassifikationslogik enthält einen Test, der eine
      `XxxController.ts` mit `export function useXxx` als Hook erkennt.
- [ ] `just check-frontend-size` bleibt grün oder zeigt nur die neu
      sichtbar werdenden, als baseline geführten Hook-Violations.
- [ ] ui-principles §15 (Hook-Limit 150) und `check_frontend_file_size.py`
      sind hinsichtlich der Hook-Klassifikation konsistent.
**Geschätzter Aufwand:** S–M

---

## Handoff an den Coordinator

**AI/Prompting-Gesamtbewertung:** ⭐⭐⭐⭐⭐ — Vorbehaltlos stark auf
Core-/Backend-/Prompting-Ebene **und** Frontend-/TipTap-/AI-UX-Ebene
(Abschnitte 7/8 finalisiert auf ⭐⭐⭐⭐⭐).

**Finale Sterne:**
- Abschnitt 7 (WebUI): ⭐⭐⭐⭐⭐
- Abschnitt 8 (TipTap & Editor-AI-Integration): ⭐⭐⭐⭐⭐
- Abschnitt 9 (AI-Verbesserungspotenzial): ⭐⭐⭐⭐ (Core-Specialist, unverändert)
- Gesamtbewertung AI-Features & Prompting: ⭐⭐⭐⭐⭐

**Wichtigste Befunde (Kurzfassung):**
1. Prompt-System (RULE-02/02a/02b) + Capability-Injection (ADR-026) +
   Routeable-Intent-Governance (ADR-037/046/049) sind maschinell
   abgesichert und in Code + CI durchgesetzt. `check-adoption` 0.97 PASS,
   ADR-046 voll compliant, 48/48 Prompts gültig.
2. 26 produktive Agenten erben konsequent von `NarrareAgent`;
   ModelRegistry-only wird durch `agent_checks.py` erzwungen.
3. Eine architektonische Inkonsistenz: `writing/pipeline_interview.py`
   nutzt `ModelRegistry.run()` direkt (AUFG-03-01) — kein Capability-Injection.
4. KB-Assist-Fallback umgeht ADR-048-Invocation-Validation/Evidence
   (AUFG-03-02).
5. A2A-Feature-Datei trägt falschen Status (`in progress`) und
   Phantom-Pfade (AUFG-03-03).
6. MCP/A2A bewusst post-MVP; Q-001/Q-002 offen — korrekt als Risiko
   dokumentiert, nicht als Implementierungsfehler.
7. **Frontend (finalisiert):** `useAIOperation`-Lifecycle-Hook +
   `connectSSE`-Transport + `mapSSEError`-i18n-Mapping + `AIAnnotation`-
   Mark-System + `GhostText`-Dekorationen + Slash-Command-Kapselung sind
   state-of-the-art und maschinell durch `check-ai-ux` (11 Gates) /
   `check-streaming` gesichert. 17 AI-Operationen dokumentiert (14 compliant,
   3 governed-exception). Accept/Reject-UX, Partial-Output-Erhaltung und
   Connection-Lost-Recovery (SSE + WebSocket/ADR-052) vollständig umgesetzt.
8. **Frontend-Nachhaltigkeitspunkte (keine Defekte):** `TipTapEditorController.ts`
   auf 400 Zeilen gewachsen (Frontend-Evidenz für AUFG-01-03 in Abschnitt 8
   ergänzt); File-Size-Gate klassifiziert ohne-`use`-Präfix benannte
   Hook-Dateien als 400-Zeilen-typescript statt 150-Zeilen-Hook (AUFG-03-04).

**Aufgaben-IDs:** AUFG-03-01 (Mittel, AI/Architektur),
AUFG-03-02 (Mittel, AI/Invocation-Integrity),
AUFG-03-03 (Niedrig, Governance/Docs),
**AUFG-03-04 (Mittel, Frontend/Governance/Tooling — neu, Frontend-Specialist)**.
AUFG-01-03 (Review 01, Frontend/Hook-Modularisierung) ist nicht im
Original (review-01) geändert; Abschnitt 8 dieses Reviews liefert jedoch
die aktualisierte Frontend-Evidenz (400 statt 335 Zeilen + Decomposition-
Empfehlung), auf die AUFG-01-03 zurückgreifen kann. Coordinator kann
beide Tasks zusammenführen.

**Geänderte Dateien:** Nur `_audit/results/technical-review/review-03-ai-features.md`
(diese Datei). Kein Code-Change, kein Commit, kein `--no-verify`.

**Blocker / Unsicherheiten:**
- Keine harten Blocker für nachfolgende Reviews.
- Frontend-Review auf Code-Lese-Ebene (keine Checker erneut ausgeführt);
  die Gates `check-ai-ux`, `check-streaming`, `check-frontend-size` wurden
  aus Review 01/02 (alle grün) übernommen und durch gezielte Reads
  verifiziert (Streaming-Quellcode, AI-Operation-Inventar,
  `.ai_interaction_exclude`, File-Size-Gate-Quellcode, Komponenten-Source).
- Embeddings im Code-Graph sind nicht gebaut (Graph meldet Embeddings: 0);
  semantische Suche fiel auf Hybrid/Keyword zurück. Für Folge-Reviews
  ggf. `embed_graph` laufen lassen.
- Eine kleine semantische Frage (kein Blocker): `editorStore.ts` hält
  neben UI-Toggles auch imperativ gesetzte Analyse-Ergebnisse
  (`betaReaderResult`/`sentimentResult`/`consistencyResult`). Das ist
  server-abgeleiteter State in einem UI-Store — within-limit und mit
  Panel-Toggles koordiniert; kein eigener AUFG, aber bei weiterem
  Zuwachs ein TanStack-Query-Cache-Refactoring-Kandidat.

**Finalisierungs-Status Abschnitte 7/8:** ✅ Erledigt.
- Abschnitt 7 (WebUI): Komponenten-Struktur, State-Management,
  AI-Feature-Präsentation final bewertet (⭐⭐⭐⭐⭐).
- Abschnitt 8 (TipTap): AI↔ProseMirror-Dokumentmodell, Ghost-Text-
  Injektion, Magic-Menü-Kapselung, Accept/Reject-UX,
  connectSSE/AbortController/Partial-Output/Retry final bewertet (⭐⭐⭐⭐⭐).
