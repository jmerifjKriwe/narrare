# Review 03 – AI-Features & Prompting

> **Voraussetzung:** Lies zuerst `_audit/results/technical-review/review-00-kontext.md` und stelle sicher,
> dass er vollständig ausgefüllt ist. Referenziere die dort dokumentierten Pfade und den Tech-Stack.
> Sollte `_audit/results/technical-review/review-00-kontext.md` nicht existieren, erstelle ihn
> zunächst auf Basis von `_audit/review-prompts/technical-review-prompts/review-00-kontext.md`
>
> **Routing:** Führe diesen Prompt mit `NarrareCoreSpecialist` aus (für Backend/Prompting) und beziehe `NarrareFrontendSpecialist` für die TipTap-Integration mit ein.
>
> **Ausgabe:** Schreibe das Ergebnis nach `_audit/results/technical-review/review-03-ai-features.md`.
> Sei kritisch. Dieser Review deckt alle AI-bezogenen Systeme ab – von den
> Nutzer-Prompts bis zu den Entwickler-Agenten.

---

## 1. Prompt-System für Nutzer

**Analysiere:**
- Wie kann ein Nutzer von Narrare die AI-Funktionen bedienen?
- Gibt es vorgefertigte Prompt-Templates? Wie sind sie strukturiert?
- Wie werden System-Prompts aufgebaut und befüllt (statisch / dynamisch / kontextabhängig)?
- Können Nutzer eigene Prompts speichern oder anpassen?
- Wie konsistent ist das Prompt-System über CLI, API, MCP und WebUI hinweg?
- Werden anpassbare Prompt-Inhalte ausschließlich über PromptComposer/Cascade geladen (RULE-02/02a)?
- Sind garantiert immer vorhandene Inhalte über Capabilities (`NarrareMeta`, `NarrareUniversalRules`) abgesichert statt manuell in Templates dupliziert?
- Bleiben dynamische Daten wie KB, Style Profiles und Voice Profiles als Runtime-Kontext/Variablen statt als hardcodierte Instruktionen im Code?

**Befunde:**

**AI-Bedienung (Nutzer-Sicht).** Der Nutzer erreicht die AI über klar getrennte Oberflächen, alle über die Service-Layer `/api/v1` konsolidiert:
- **Inline-Suggestions (Ghost-Text):** TipTap-`GhostText`-Extension (`packages/web/components/studio/editor/extensions/GhostText.ts`) mit SSE-Endpoint `POST /writing/chapters/{id}/suggest` — Copilot-artige graue Fortsetzungstexte, Tab/→/Esc-Steuerung (`packages/web/lib/api/suggest.ts`).
- **Slash-Command-Menü (Magic-Menü):** `/continue`, `/draft`, `/rewrite`, `/coauthor`, `/chat`, `/explain` (`packages/web/components/studio/editor/slash-commands/registry.ts`, `AI_SLASH_COMMANDS`). Sauber via `SlashCommandDispatchContext` vom Transport entkoppelt.
- **Bubble-Menü:** Auswahl → „AI Rewrite" (`TipTapBubbleMenu.tsx`).
- **Co-Author-Panel:** Modal mit Phasen `focus → streaming → review → done` (`CoAuthorPanel.tsx`).
- **Chat:** Freie Konversation (`ChatPanel.tsx`, `core/chat/chat_agent.py`).
- **Analyse-Panels:** Consistency, BetaReader, CharacterVoice, Readability, POV, Sentiment, Coreference (jeweils `use*`-Hooks + Streaming-API).
- **Interview:** Writing-Interview (WebSocket `interview_assisted`-Mode) + KB-Assist-Interview.

Es gibt **keine dedizierte CLI** und **keinen MCP/A2A-Client** (siehe §5/§6). Konsistenz über die implementierten Layer (API + WebUI) ist hoch — beide greifen auf dieselben `core/prompts/`-Templates und Services zurück.

**Vorgefertigte Prompt-Templates.** Sehr umfangreich: 64 gebundelte `.md`-Dateien unter `core/prompts/_bundled/` (Kategorien `meta/`, `universal/`, `writing/`, `analysis/`, `kb/`, `planning/`, `wiki/`, `generation/` + `writing/tones/`). Struktur: Frontmatter (`prompt_type`, `prompt_language`, `prompt_version`) + `## System Prompt`-Sektion + optionale `## First Message`. Versionsstempel vorhanden (z. B. `inline_suggest` v2.4.0, `meta` v3.0.0, `consistency` v2.0.0).

**System-Prompt-Aufbau.** Dreischichtig gemäß ADR-026, sauber getrennt:
1. **Garantiert (Capability):** `NarrareMeta` (`_bundled/meta/{lang}/system.md`), `NarrareUniversalRules` (`_bundled/universal/{lang}/system.md`), `NarrareObservability` — werden von `NarrareAgent.__init__` (`agents/base.py:127-132`) **immer** injiziert, nie manuell in Templates dupliziert. `meta.py:_load_meta_prompt()` lädt synchron mit EN-Fallback; `for_run()` resolved Sprache aus Deps.
2. **Anpassbar (Cascade):** `PromptComposer.build()` (`prompts/composer.py`) → `PromptRegistry.resolve()` (`prompts/registry.py`) mit 5-stufiger Cascade: DB → Project `.narrare/prompts/` → User `~/.config/narrare/prompts/` → Bundled → Bundled-EN-Fallback. Genre-Spezifität via `system_{genre}.md`.
3. **Dynamisch:** `{{variablen}}` (KB, Style/Voice-Profile, Recent Chapters, Preferences) als Runtime-Kontext — `variable_engine.py` substituiert `strict=True`. AI-Anweisungen werden **nicht** hardcodiert, sondern als `{{co_author_focus_instructions}}`, `{{character_voice_profiles}}`, `{{style_profile}}` etc. injiziert.

**Nutzer-Anpassbarkeit.** Vollwertiges Prompt-Management via API (`apps/api/narrare/prompts/router.py`): `list_prompts`, `get_prompt`, `save_override` (DB), `reset_override`, `cascade_info` (zeigt alle Cascade-Levels), `detect_updates` (erkennen von Bundled-Updates), `get_diff`. Plus Live-Test-Service (`live_test_service.py`, `_live_test_sse.py`) und Prompt-History. Nutzer können jeden Feature-Prompt in der DB überschreiben — sehr durchdacht.

**RULE-02/02a/02b-Compliance.**
- **PASS.** Anpassbare Feature-Prompts laufen ausschließlich über `PromptComposer`+`Cascade`. Keine Inline-System-/Task-Strings in Services gefunden. `writing_graph_prompts.py` hat den `composer is None`-Fallback entfernt (`_COMPOSER_MISSING_MSG`, fail-fast per RULE-11). ADR-054 hat Inline-Fallback-Baseline auf 0 gebracht (review-00).
- **PASS.** Garantierte Inhalte über `NarrareMeta`/`NarrareUniversalRules` Capabilities abgesichert, nicht in Templates dupliziert. Jeder produktive Agent erbt `NarrareAgent` → Auto-Injection (`base.py:127-132`).
- **PASS.** KB/Style/Voice als Runtime-Variablen. `composer.py:128-141` injiziert `culture_guidelines`/Name-Styles explizit; `co_author/system.md` bindet `{{kb_characters}}`, `{{character_voice_profiles}}`, `{{style_profile}}`. Keine hardcodierten Instruktionen.

**Qualität der Prompts.** Hochwertig und durchdacht. `prompt-content-standards.md` fordert 8 verbindliche Elemente, erzwungen via `check_prompt_structure.py --strict`. Gesehen:
- **Rolle/Kontext/Format:** Konsistent (z. B. `consistency/system.md`: klare Rolle, Check-Types, Output-Format als JSON-Schema, Severity-Definitionen).
- **Do-NOT-Listen:** Jeder Prompt hat eine `### Do NOT`-Sektion mit ≥4 Einträgen (erfüllt ≥4-Regel).
- **Injection-Defense:** User-Content konsequent in XML-Tags gewrappt: `<user_provided_text role="before_cursor">`, `<user_provided_data>`, `<user_instructions>` — und `universal/system.md` instruiert explizit, diese als Daten zu behandeln. Meta-Prompt nennt dieselben Tags.
- **False-Positive-Gates / Evidence-Gates:** `consistency/system.md:63` verlangt „only emit an issue when both conflicting facts are explicitly present"; `inline_suggest` unterscheidet Text-vor/nach-Cursor mit klarer Rollen-Trennung.
- **Reasoning/Scratchpad:** `interview/system.md:83` fordert `<scratchpad>`-Block vor der Frage-Ausgabe.
- **Generated-Candidate-Boilerplate:** KB-Suggestions werden überall als „unaccepted candidates / lower-priority / must not override" markiert (z. B. `co_author/system.md:36-44`, `inline_suggest/system.md:58-65`).
- **Formality-Register:** `{{avoidance_patterns}}` überall vorhanden.

**Mängel:**
- **Feature-Prompts sind EN-only.** Nur `meta/` und `universal/` haben `de/`+`fr/`-Übersetzungen. Alle `writing/`, `analysis/`, `kb/`, `planning/`-Prompts existieren nur in `en/`. Bei `language=de` liefert die Cascade zwar lokalisierte Meta-/Universal-Regeln, fällt aber für die Feature-Instruktionen auf EN zurück. Funktionierender Fallback, aber kein vollständiges i18n-Versprechen für Prompts.
- **Meta-Lite-Parallele Pipeline.** `_bundled/meta/{lang}/system.lite.md` existiert (8 Zeilen), aber es ist im Code nicht erkennbar, wann Lite vs. Full selektiert wird (kein Aufrufer in `meta.py` gefunden, der `variant: lite` auswählt). Möglicherweise tote Konfiguration — prüfen.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** _Außerordentlich gereiftes Prompt-System: ADR-026-Dreiteilung (Capability/Cascade/Dynamic) sauber umgesetzt, RULE-02/02a/02b alle PASS, 5-stufige Cascade mit Nutzer-Overrides + Live-Test + Diff-Tooling, Prompt-Quality-Governance (`check_prompt_structure.py --strict`, 8 Pflicht-Elemente), hochwertige Best-Practice-Prompts (Rolle/Format/Do-NOT/Injection-Defense/Evidence-Gates/Scratchpad). Abzug 1 Stern: Feature-Prompts ausschließlich EN (de/fr-Fallback nur für Meta/Universal) — i18n-Versprechen für Prompts nicht vollständig eingelöst; Meta-Lite-Variante ohne erkennbaren Selektor (potenzielle tote Konfiguration)._

---

## 2. Agent-System während der Entwicklung

**Befunde:**

**Versorgung der Dev-Agenten.** Narrare nutzt eine dreischichtige Dev-Agent-Architektur unter OpenCode:
- **Root `AGENTS.md`** (Orchestrator-Instruktionen): Definiert Trigger-Phrasen → Subagent-Routing, 6 Narrare-Subagents, 5 `/skill`-Wrapper, Thinking-Partner- vs. Delegation-Pattern, SSOT-Hinweise.
- **`.opencode/agents/narrare-dev-coordinator.md`** (Primary Coordinator, mode: primary): Layer-specialist-Orchestrator mit detailliertem Permission-Modell (bash deny-by-default + Allowliste, edit deny + gezielte Ask/Allow, tool `code-review-graph_*` allow).
- **`.opencode/agents/subagents/narrare-dev/`** (6 Subagents): `architecture.md`, `backend.md`, `core.md`, `docs.md`, `frontend.md`, `platform.md` — jeweils Layer-spezifisch mit Permission-Modell, Tier-1-Regeln, Self-Review-Checkliste.
- **`.opencode/context/narrare-dev/`** (extrahierter Kontext): `navigation.md` + 31 extrahierte Dateien (<200 Zeilen) aus 135 Docs. Unterteilt in `standards/` (8 Dateien), `concepts/`, `constraints/`, `domain/`, `examples/`, `guides/`, `lookup/`, `processes/`, `templates/`.
- **`.opencode/skills/`**: `context7/` (Library-Docs), `task-management/` (Task-CLI).
- **`.agents/skills/`** (Projekt-Skills): `building-pydantic-ai-agents/`, `mem0/`, `commit-context/`, `recall/`, `remember/`, `shadcn/`, `logfire-*`, `remediate-review/`, `find-skills/`, `handoff/`, `recap/`, `session-history/`, `forget/`, `frontend-design/`, `tailwind-design-system/`, `vercel-*`.

**Kontext-Window-Effizienz.** Gut gelöst: Extraktion reduziert 135 Docs (z. B. CONSTRAINTS.md 766 Zeilen → `rules.md`; testing-standards.md 1224 Zeilen → `quality-gates.md`) auf <200-Zeilen-Dateien. `navigation.md` dient als kompakter Index. `tier1-compact-rules.md` (~95 Zeilen) als „Minimum jeder Agent muss wissen". Coordinator lädt kontextbezogen.

**Konsistenz.** Hoch. `tier1-compact-rules.md` spiegelt CONSTRAINTS.md (23 Regeln), `packages/core/AGENTS.md` und `apps/api/AGENTS.md` sind layer-spezifisch und referenzieren CONSTRAINTS.md als SSOT (expliziter „SSOT Notice"-Hinweis). Keine offensichtlichen Widersprüche gefunden. Subagent-Definitionen sind konsistent mit Root-`AGENTS.md`-Trigger-Phrasen.

**Konkrete Bewertung der `.opencode`-Inhalte:**

| Datei/Verzeichnis | Inhalt | Qualität | Anmerkung |
|---|---|---|---|
| `agents/narrare-dev-coordinator.md` | Primary-Coordinator: Routing, Permission-Modell (deny-by-default bash, Ask/Allow-Edit), MCP-Graph-Anweisungen, 6 Subagents | ⭐⭐⭐⭐⭐ | Vorbildlich granular; Permission-Modell durchdacht (sicherer als Allow-all). |
| `agents/subagents/narrare-dev/core.md` | Core-Specialist: LLM/Prompts/Embeddings/Memory-Ownership, RULE-01b/02, Skills-Hinweise, Self-Review-Checkliste | ⭐⭐⭐⭐⭐ | Tier-1-Regeln, Architectural-Discipline, pydantic-ai/mem0-Skill-Trigger dokumentiert. |
| `agents/subagents/narrare-dev/architecture.md` | Architecture-Gate: ADRs, Contracts, Module-Grenzen | ⭐⭐⭐⭐ | Stark; könnte ADR-039-Lücke erwähnen. |
| `agents/subagents/narrare-dev/backend.md` | Service-Layer-Pattern, Repository, DI | ⭐⭐⭐⭐ | Solide; Agent-First-Pattern korrekt. |
| `agents/subagents/narrare-dev/frontend.md` | Next.js 16, TipTap, RULE-15/16/17 | ⭐⭐⭐⭐ | Aktuell; erwähnt `proxy.ts`. |
| `agents/subagents/narrare-dev/docs.md` | Feature-Docs, i18n, Help-Texts | ⭐⭐⭐⭐ | Angemessen. |
| `agents/subagents/narrare-dev/platform.md` | Testing/CI/Docker/Deployment | ⭐⭐⭐⭐ | Angemessen. |
| `context/narrare-dev/navigation.md` | Index über 31 extrahierte Dateien (Priorität/Quelle/Beschreibung) | ⭐⭐⭐⭐⭐ | Kompakt, wartbar, gute Priorisierung (critical/high/medium). |
| `context/narrare-dev/standards/architectural-discipline.md` | §7 „documented ≠ implemented", Root-Cause-First | ⭐⭐⭐⭐⭐ | Zentrale Disziplin-Regel, hochrelevant. |
| `context/narrare-dev/standards/tier1-compact-rules.md` | 23 Regeln + Testing einzeilig + Common-Violations-Spalte | ⭐⭐⭐⭐⭐ | Höchst nützlich als Quick-Reference; Common-Violations-Spalte praxisnah. |
| `context/narrare-dev/standards/graph-exploration.md` | Graph-First-Standard, Decision-Matrix code-review-graph vs. codebase-memory-mcp | ⭐⭐⭐⭐ | Wichtig; beachten dass Embeddings=0 für semantic search. |
| `context/narrare-dev/standards/prompt-standards.md` | Extrakt aus prompt-standards.md | ⭐⭐⭐⭐ | Konsistent mit §1. |
| `context/narrare-dev/domain/architecture-concepts.md` | Layer-Architektur, 4-Client-Modell, Streaming | ⭐⭐⭐⭐ | Gut. |
| `skills/context7/` | Library-Doc-Retrieval-Skill | ⭐⭐⭐⭐ | Praktisch für Versions-Checks. |
| `skills/task-management/` | Task-CLI (Subtask-Tracking) | ⭐⭐⭐ | Angemessen; überschneidet sich mit Superpowers-task-Skill. |
| `.agents/skills/building-pydantic-ai-agents/` | pydantic-ai-Patterns, Gotchas (`@agent.tool` vs `@agent.tool_plain`, Model-String-Prefix) | ⭐⭐⭐⭐⭐ | Direkt relevant für RULE-01b-Compliance; Referenzen AGENTS-CORE/TOOLS-CORE. |
| `.agents/skills/mem0/` | AsyncMemory-OSS-Patterns (ADR-033) | ⭐⭐⭐⭐⭐ | Direkt relevant; Graceful-Degradation-Pattern. |

**Mängel:**
- **Skill-Duplikation.** `.agents/skills/` und `.opencode/skills/` + Superpowers-Skills (`.cache/opencode/.../superpowers`) überlappen teilweise (`task-management` vs. Superpowers-`task-management`; `commit-context` vs. Superpowers-`handoff`). Potenzial für Verwirrung, welcher Skill greift.
- **Kein Hook-Mechanismus erkennbar.** Die Analyse-Frage nennt „Hooks" — in `.opencode/` sind keine Pre-/Post-Hooks (z. B. automatischer `check_architecture.py`-Lauf nach Edit) definiert; Enforcement läuft über Git-Hooks (pre-commit) + CI, nicht über Agent-Hooks. Akzeptabel, aber erwähnenswert.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** _Sehr gut organisiertes, mehrschichtiges Dev-Agent-System mit deny-by-default-Permission-Modell, kompakt extrahiertem Kontext (31 Dateien <200 Zeilen aus 135 Docs), klarer SSOT-Kaskade und konsistenten Layer-Specialists. Tier1-Compact-Rules und Architectural-Discipline sind vorbildlich. Abzug: Skill-Duplikation zwischen `.agents/skills/`, `.opencode/skills/` und Superpowers kann zu Mehrdeutigkeit führen; kein Agent-Hook-Mechanismus (Enforcement nur via Git/CI)._

---

## 3. Agent-System während der Tool-Nutzung

**Befunde:**

**Spezialisierte Agenten.** Narrare hat eine beachtliche Palette von **30+ produktiven `NarrareAgent`-Subklassen** (SSOT: `core/narrare_core/agents/__init__.py`), kategorisiert:
- **Schreiben/Review:** `DraftAgent`, `OutlineAgent`, `ChapterSummaryAgent`, `ReviewAgent`, `BetaReaderAgent` (+ DeepDive).
- **Inline/Assistenz:** `InlineSuggestAgent`, `StorySuggestAgent`, Chat (`core/chat/chat_agent.py`).
- **Knowledge Base:** `KBAgent`, `KBAssistAgent`, `KBImproveAgent`, `MergeAgent`, `FactExtractorAgent`.
- **Analyse:** `ConsistencyAgent`, `ReadabilityAgent`, `POVDetectionAgent`, `CharacterArcAgent`, `CharacterVoiceAgent` (+ `CharacterVoiceCheckerAgent`), `CoreferenceAgent`, `TemporalExtractionAgent`, `TimelineAgent`, `ExtractionAgent`, `PreferenceAnalysisAgent`, `WorldbuildingAgent`.
- **Planung:** Outline/Timeline (in `core/planning`).
- **Test-Only:** `PromptLiveTestAgent`.

Jeder Agent hat eigene `*_types.py` (Pydantic Output-Modell) und eigene Feature-Prompts unter `_bundled/{category}/`.

**Capability-Vererbung (RULE-01b/ADR-026).**
- **PASS.** Alle produktiven Agenten erben `NarrareAgent[DepsT, OutputT]` (`agents/base.py:69`). `NarrareAgent.__init__` (`base.py:127-132`) injiziert **immer** `[NarrareObservability, NarrareUniversalRules, NarrareMeta, *(capabilities)]`. Kein manueller Meta-Prompt-Load nötig (ADR-026 Phase 3, `with_meta()` entfernt).
- **PASS (Modell-Auflösung).** `NarrareAgent.__init__` nimmt `model: Model` als Pflichtparameter, der vom Aufrufer via `registry.get_model(config)` (`writing_graph_prompts.py:53-59`) geholt wird. Keine direkte Provider-Instanzierung in Agenten. `AgentRegistry` (`agents/registry.py`) cachet Agent-Instanzen per `(agent_type, id(model), system_prompt)` für Prompt-Caching (ADR-016).

**Kontext-Weitergabe.** Zwei Muster:
- **Mode 1 (Service → Agent):** Service baut `PromptContext`, ruft `PromptComposer.build()` → `ComposedPrompt`, übergibt `composed.user` als `prompt` an `agent.run()`, `composed.system` als `system_prompt` an den Konstruktor. Interview-Pfad: `InterviewQuestionAgent(model, system_prompt=composed.system)` + `agent.run(prompt=composed.user)`.
- **Mode 2 (Graph-intern):** `WritingGraph` (`agents/writing_graph.py`) nutzt `compose_invocation()` + `_run_invocation_pipeline()` für prepare/finalize (Validation + Enrichment + Budget + Evidence). PromptContext wird pro Step frisch gebaut (`_base_context`), mit KB-Anreicherung (`_enrich_prompt_context_with_kb`).

**Multi-Agent-Orchestrierung.** `WritingGraph` (`agents/writing_graph.py`) als pydantic-graph-State-Machine:
```
plan_outline → write_draft → review_draft → finalize
                                ↑       ↓
                                └─ revise_draft
```
Nutzt `GraphBuilder` (ADR-015 Phase 4). `AgentRegistry` (`agents/registry.py`) zentralisiert Instanz-Caching mit TTL (300s, Anthropic-Cache-TTL) + LRU-Eviction (max 50). Zustandspersistenz via `store.save(run_id, state)`.

**Versionsverwaltung.** Agent-Anweisungen sind versioniert via Prompt-Frontmatter (`prompt_version`) + Git. Prompt-History-API (`router_prompt_history.py`, `history_service.py`) trackt Prompt-Änderungen. Es gibt jedoch **keine separate Versionierung der Agent-Klassen selbst** (z. B. `DraftAgent` v1/v2) — Breaking Changes am Agent-Output-Typ würden alle Consumer gleichzeitig brechen.

**Kontext zwischen Aufrufen.** Conversational Agents (`HistoryPolicy.CONVERSATIONAL`, ADR-034) nutzen `ProcessHistory.messages` → `message_history` in `run_stream()` (`base.py:176-236`). Task-Agents default `HistoryPolicy.NONE`.

**Mängel:**
- **Kein Cross-Agent-Kontext-Persistenz-Layer.** Jeweils nur innerhalb eines Graph-Runs oder einer Chat-Session. Wenn ein Autor z. B. Consistency-Check-Ergebnisse in den nächsten Co-Author-Lauf einspeisen will, muss er manuell vermitteln. Kein „Shared-Agent-Memory" jenseits von mem0-Preferences.
- **Agent-Versions-Lücke.** Keine Versionierung der Agent-Klassen — nur der Prompts.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** _Umfangreiche, architektonisch saubere Agent-Palette (30+ spezialisierte Agents), alle korrekt von `NarrareAgent` erbend mit Auto-Capability-Injection (RULE-01b/ADR-026 PASS), Model ausschließlich via ModelRegistry aufgelöst (keine direkte Provider-Instanzierung), zentrales AgentRegistry-Caching, WritingGraph als Multi-Step-Orchestrierung, ProcessHistory für konversationellen Kontext. Abzug: keine persistente Cross-Agent-Kontext-Teilung zwischen separaten Werkzeug-Aufrufen; keine Agent-Klassen-Versionierung (nur Prompt-Versionierung)._

---

## 4. Interview-System

**Befunde:**

**Implementierung.** Zwei eigenständige Interview-Subsysteme, beide über `InterviewQuestionAgent` (`agents/interview_question_agent.py`) bzw. `KBAssistAgent` realisiert:

1. **Writing-Interview** (`writing/en/interview/system.md`, `InterviewQuestionAgent`):
   - Eingebettet in den WebSocket-Session-Workflow (`apps/api/narrare/writing/`): Mode `interactive_session` (freie Chat-Session) und `interview_assisted` (strukturiertes Interview → Draft-Generierung).
   - `ws_handler.py` erkennt `interview_assisted`-Mode; `ws_turn_service.py` mapt auf `"interview"`.
   - `_interview_draft.py` (`InterviewDraftGenerator`) generiert aus gesammelten Interview-Antworten einen Kapitelentwurf über WebSocket-Streaming — mit Token-Budget-Cap für lange Transkripte (>20 Q&A-Paare).
   - Fragen-Generierung: **AI-generiert** (dynamisch, kontextabhängig) — der Prompt instruiert „3-5 targeted questions (not all at once — one or two at a time)", KB-gesteuerte Lücken-Analyse, Scratchpad-Reasoning vor der Frage-Ausgabe.

2. **KB-Assist-Interview** (`kb/en/interview/system.md`, `KBAssistAgent`):
   - Fragt gezielt zu Template-Feldern (`kb/assist_service.py:get_interview_question`, `kb/assist_contracts.py`).
   - Endpoint: `POST /novels/{novel_id}/kb/sessions/{session_id}/interview` (`kb/router_sessions.py:95`).

**Arten.** (a) Schreib-Interview (Kapitel-Vision, Charakter-Motivation, Plot-Wendepunkte, emotionale Beats), (b) KB-Feld-Interview (Worldbuilding-/Entitäts-Details). Konsistenz-Interviews laufen separat über `ConsistencyAgent`.

**Fragen-Generierung.** Dynamisch/AI-generiert, kontextadaptiv: Der Interview-Prompt (`writing/en/interview/system.md`) passt Fragen an KB-Dichte an („If the KB already has rich character/location data, focus on plot and pacing instead"). Scratchpad zwingt zur Voranalyse der Lücken.

**Antwort-Speicherung & Wiederverwendung.** Interview-Antworten fließen als `author_instructions` / `chapter_outline` in `PromptContext` ein und werden beim Draft (`_interview_draft.py`) als formatiertes Transkript injiziert (mit Token-Cap). KB-Interview-Antworten persistieren in der KB-Session. Antworten werden somit für nachfolgende AI-Aufrufe (Draft, Co-Author) nutzbar.

**Integration.** Voll in die WebSocket-Session-Pipeline integriert (Session-Mode `interview_assisted`). KB-Interview über dedizierten REST-Endpoint. Kein CLI/MCP (entfällt).

**UX.** WebSocket-basiertes Streaming (progressives Draft-Frontend). Trennung Frage-Phase → Draft-Phase klar. Token-Cap verhindert Context-Overflow-Crashes. `InterviewDeps` bewusst minimal gehalten (Kompositions-Pattern Mode 1).

**Mängel:**
- **Keine Vorab-Auswahl der Interview-Tiefe.** Nutzer kann nicht wählen „kurzes 3-Fragen-Interview vs. tiefes 10-Fragen-Interview" — Tiefe wird vom AI dynamisch bestimmt.
- **KB-Interview-Prompt (`kb/en/interview`) nicht im Detail geprüft** auf gleiche Quality-Gates wie Writing-Prompts (Do-NOT-Liste etc.) — Konsistenz-Vermutung, aber nicht verifiziert.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** _Zwei gut durchdachte, AI-gestützte Interview-Subsysteme (Writing + KB), beide kontextadaptiv mit Scratchpad-Reasoning und KB-Lücken-Analyse, sauber in WebSocket-/REST-Pipeline integriert, Antworten fließen in Draft-Generierung ein, Token-Cap schützt vor Overflow. Abzug: keine nutzerseitige Steuerung der Interview-Tiefe; KB-Interview-Prompt-Quality nicht vollständig verifiziert._

---

## 5. MCP-Server

**Befunde:**

**Status: NICHT IMPLEMENTIERT.** Bestätigt durch review-00: `apps/mcp/` existiert nicht. ADAPTER-001 spec = „Planned, Not Implemented". Blockiert durch **Q-001** (MCP-Auth-Strategie, 🟡 Open). README vermerkt „planned; calls Service Layer when built".

**Plan.** Laut RULE-12 (4-Client-Modell: API, CLI, MCP, A2A) ist MCP ein geplanter Roadmap-Adapter, der bei Implementierung die Service-Layer (`/api/v1`-Services) als Tools exponieren würde. Keine Tool-Inventarisierung vorhanden (da nicht gebaut).

**Gap/Impact.** Ohne MCP können externe AI-Clients (z. B. Claude Desktop, Cursor) Narrare-Funktionen nicht direkt als MCP-Tools nutzen. Für den aktuellen MVP-Betrieb (WebUI-first) nicht kritisch, schränkt aber die „vollständig anpassbare/local-first"-Vision für Power-User ein, die Narrare in ihre bestehende MCP-Toolchain einbinden wollen.

**Tool-Inventar:**

| Tool-Name | Beschreibung | Qualität der Beschreibung | Fehlt in anderen Layern? |
|---|---|---|---|
| _n/a — MCP nicht implementiert (ADAPTER-001, blockiert durch Q-001)_ | — | — | — |

**Bewertung:** ⭐⭐
**Befunde:** _MCP-Server ist nicht implementiert (ADAPTER-001 „Planned, Not Implemented", blockiert durch offene Q-001 MCP-Auth-Strategie). Kein Code, kein Tool-Inventar, keine Doku jenseits der Roadmap-Notiz. Bewertung bezieht sich auf den Plan-Stand: die Roadmap-Intention ist dokumentiert, aber bis Q-001 geklärt ist, gibt es nichts Funktionierendes. Für MVP akzeptabel; für die Local-First-/Power-User-Vision ein spürbarer Funktionsverlust._

---

## 6. A2A

**Befunde:**

**Status: NICHT IMPLEMENTIERT.** Bestätigt durch review-00: `apps/a2a/` existiert nicht. ADAPTER-002 spec = „Planned, Not Implemented". Blockiert durch **Q-002** (A2A-Streaming-Anforderung, 🟡 Open).

**Plan.** Laut RULE-12 geplanter Roadmap-Adapter für Agent-to-Agent-Kommunikation. Bei Implementierung würden Narrare-Agenten via A2A-Protokoll für externe Agenten-Orchestrierungen erreichbar. Keine Tool-Inventarisierung vorhanden.

**Gap/Impact.** Ohne A2A können externe Multi-Agent-Frameworks Narrare-Agenten nicht direkt ansprechen. Relevanz hängt stark davon ab, ob Nutzer Narrare in Cross-Agent-Workflows einbetten wollen — aktuell Nischen-Fall.

**Tool-Inventar:**

| Tool-Name | Beschreibung | Qualität der Beschreibung | Fehlt in anderen Layern? |
|---|---|---|---|
| _n/a — A2A nicht implementiert (ADAPTER-002, blockiert durch Q-002)_ | — | — | — |

**Bewertung:** ⭐⭐
**Befunde:** _A2A-Server ist nicht implementiert (ADAPTER-002 „Planned, Not Implemented", blockiert durch offene Q-002 A2A-Streaming-Anforderung). Kein Code, kein Tool-Inventar. Roadmap-Dokumentation vorhanden, aber bis Q-002 geklärt ist, nichts Funktionierendes. Niedrigere praktische Relevanz als MCP (Nischen-Anwendungsfall)._

---

## 7. WebUI

**Befunde:**

**Aktueller Stand.** Next.js 16 App Router, weit fortgeschritten. Route-Groups `app/(auth)/`, `app/(studio)/` (mit `AuthGate`), 3 Shells (Dashboard `/`, Wizard `/wizard`, Studio-Workspace `/novel/[id]/**`). Route-Middleware ausschließlich über `proxy.ts` (RULE-15). Editor mit TipTap v3 + SSE-Streaming. Dev-Server Port 3000.

**AI-Feature-Präsentation.** Ausgeprägt:
- **Streaming:** `connectSSE()` (`lib/api/streaming.ts`) als zentrale SSE-Transport-Schicht (native fetch + ReadableStream, AbortController + connectTimeout 30s + AbortSignal.any-Kombinierung). `useAIOperation()` (`lib/hooks/use-ai-operation.ts`) als zwingender Lifecycle-Hook für alle AI-Operationen (ADR-043, §16) — mit Zustandsmaschine, AbortController, Connection-Loss-Detection, Partial-Output-Preservation, Retry-Logik, Error→i18n-Mapping.
- **Loading/Errors:** Konsistent — `StatusMessage`-Komponenten, `mapSSEError`, lokalisierte Error-Texte, Retry-Buttons.
- **Co-Author-Panel:** Phasenbasiertes Modal (`CoAuthorPanel.tsx`) mit Streaming/Review/Done/Error-Phasen, Style-Variant-Regeneration, Escape-Handler.

**Komponenten-Struktur.** Sauber getrennt: `components/studio/editor/` (~60 Komponenten + `__tests__/`), `components/studio/analysis/` (Consistency, BetaReader etc.), `components/studio/kb/`, `components/studio/planning/`. Editor-Controller ist in fokussierte Sub-Hooks zerlegt (`useRewriteFlow`, `useGhostTextConfig`, `useEditorInstance`, `useEditorAutosave`) — RULE-04/06 vorbildlich.

**State-Management.** Zustand (Client) + TanStack Query v5 (Server) — angemessen für die Komplexität. `editorStore` (Zustand) für Editor-Zustand.

**Backend-Konsistenz.** Hoch — Frontend-API-Module (`lib/api/`) spiegeln Backend-Router; `analysis.ts`, `consistency-stream.ts`, `character-voice-stream.ts` etc. folgen exakt den Backend-Schemas (RULE-17). `test_prompt_contract.py` sichert API↔Frontend-Feldnamen-Parität.

**Was fehlt / problematisch:**
- **`AnalysisPanel.tsx` ist ein PLACEHOLDER** (`components/studio/AnalysisPanel.tsx:53-57`): `setTimeout(() => setIsAnalyzing(false), 1500)` — Fake-Loading ohne realen API-Call. Explizites TODO: „replace with a real analysis API call; this placeholder drives the loading StatusMessage until async analysis is wired (no mock stat numbers)". Dies ist ein klarer Fall von „documented ≠ implemented" (architectural-discipline §7). **Aber:** die eigentlichen Analyse-Features sind woanders voll verdrahtet (`components/studio/analysis/ConsistencyPanel.tsx` nutzt `useConsistencyStream`, BetaReader/CharacterVoice/Readability/POV über eigene Hooks). Das Placeholder-Panel ist ein verwaistes/legacy Dashboard-Element, kein Hinweis auf fehlende Analyse-Funktionalität. Dennoch sollte es entfernt oder verdrahtet werden, da es Nutzer verwirrt.
- **State-Stats-Empty-Placeholder** im selben Panel („no mock numbers" — korrekt ohne Fake-Daten, aber leer).

**Bewertung (WIP-bereinigt):** ⭐⭐⭐⭐
**Befunde:** _WebUI ist weit fortgeschritten mit exzellenter AI-Feature-Präsentation: zentrale `connectSSE()`+`useAIOperation()`-Lifecycle-Compliance (§16, ADR-043), sauber getrennte Editor-Komponenten (~60) mit fokussierten Sub-Hooks (RULE-04/06), Backend-Konsistenz via Schema-Parität (RULE-17), phasenbasierte Co-Author-UX. Abzug 1 Stern: `AnalysisPanel.tsx` ist ein unverbundener Placeholder (setTimeout statt echtem API-Call) — ein verwaistes Dashboard-Element, das die sonst voll verdrahteten Analyse-Features (Consistency/BetaReader/CharacterVoice in `components/studio/analysis/`) fälschlich als unvollständig erscheinen lässt._

---

## 8. TipTap & Editor-AI-Integration (Das Herzstück)

**Befunde:**

**Architektur Streaming-Response ↔ ProseMirror.** Durchdacht und korrekt getrennt:
- **GhostText-Extension** (`extensions/GhostText.ts`, 299 Zeilen): Nutzt `ProseMirror Plugin` + `Decoration.widget(suggestionPos, ghostSpan, { side: 1, key: "ghost" })` — platziert grauen Ghost-Text **nach** dem Cursor, **ohne** das Dokument zu mutieren (rein dekorativ). Vier Phasen dokumentiert: (1) statische Decoration-Validierung, (2) Accept/Reject + simulierte Streams, (3) echtes SSE, (4) Production-Polish (LRU-Cache, Hint-Decoration, Analytics).
- **Suggest-Fetcher** (`lib/api/suggest.ts`): `createSseSuggestionFetcher()` kapselt `connectSSE()` über dem SSE-Endpoint, akkumuliert Chunks → Promise<string>. Expliziter AbortSignal-Listener (sonst würde Promise bei Abort nie settlen). SSE→Promise-Bridge-Muster sauber.
- **AIAnnotation-Mark** (`extensions/AIAnnotation.ts`, 345 Zeilen): ProseMirror `Mark` mit Attributen (`request_id`, `source`, `original_text`, `status`, `created_at`) — überlebt Transaktionen, dient als zuverlässige Vergleichsbasis für Modify-Detection. Tracker-Plugin erzwingt „single-pending-mark"-Constraint, nutzt ProseMirror-Transaction-Mapping (kein manuelles Positions-Bookkeeping). Mutationen via Standalone-Funktionen in `aiAnnotationApi.ts` (Proxy-`this`-Problem umgangen).

**Flüssige Injektion vs. Blockierung.** Ghost-Text ist **nicht-blockierend** — der Nutzer kann weiter tippen, während ein Vorschlag ansteht. Typing-Mismatch-Detection (`handleTypingDuringSuggestion`): passende Taste → Auto-Advance, Mismatch → Clear. Charakter-weises Streaming via `setInterval(30ms/char)` für flüssige Ausrollung. Auto-Trigger nach Pause (>800ms, ≥5 Zeichen am Absatzende). AbortController für pendente Requests. Prefix-LRU-Cache (50 Einträge, 30s TTL) vermeidet redundante API-Calls.

**Komponententrennung.** Vorbildlich:
- `TipTapEditorController.ts` (115 Zeilen) ist ein **dünner Composer**, delegiert an fokussierte Sub-Hooks (`useEditorAutosave`, `useGhostTextConfig`, `useEditorInstance`, `useGhostTextOnboardingAnchor`, `useRewriteFlow`).
- **Magic-Menü** (Slash-Commands) komplett entkoppelt: `slash-commands/` mit `registry.ts` (Definitionen), `parser.ts` (Filterung), `slash-state.ts`, `useSlashCommandState.ts`, `SlashCommandMenu.tsx`, `menu-items.ts`. Dispatch über `SlashCommandDispatchContext` — ruft nie Transport direkt. Wired-Ops-Set signalisiert unavailable Commands mit „actionable guidance".
- **Bubble-Menü** (`TipTapBubbleMenu.tsx`): eigenständig, nur Bold/Italic/AI-Rewrite.
- **Co-Author-Panel** (`CoAuthorPanel.tsx`): eigenständiges Modal, phasenbasiert (`focus/streaming/review/done/error`), nutzt `useCoAuthorPanel` + `useCoAuthorStyleVariant`.
- **Rewrite-Flow** (`useRewriteFlow.ts`): eigene State-Machine (`idle/selecting-mode/streaming/showing-alternatives`), nutzt `useRewriteOperation` (wraps `useAIOperation`).

**Accept/Reject-UX.** Intuitiv und performant:
- Ghost-Text: `Tab` = Accept All, `Escape` = Reject, `ArrowRight` = Accept First Word. Onboarding-Callout (`GhostTextOnboarding`) für Erstnutzer.
- Rewrite: `RewriteSuggestionModal` mit mehreren Alternativen, Style-Variant-Regeneration, Reject-with-Reason-Input, Insert-as-New-Option.
- Co-Author: `CoAuthorReviewPhase` mit Toggle-Changes, Accept-All/Reject-All, Apply-Button, Reasoning-Anzeige.
- InlineDiff (`InlineDiff.tsx`) für Change-Visualisierung.

**SSE/AbortController/Retry (RULE-20/UI-§16).**
- **PASS.** `connectSSE()` (streaming.ts) nutzt nativen `fetch` + `AbortController` mit `AbortSignal.any()`-Kombinierung (Caller-Signal + interner Timeout-Controller). Connect-Timeout 30s.
- **PASS.** `useAIOperation()` (use-ai-operation.ts) erzwingt §16: AbortController-Management, Connection-Loss-Detection (`DEFAULT_CONNECTION_LOSS_TIMEOUT`), `DEFAULT_MAX_RETRIES` für Auto-Retry, Partial-Output-Preservation, Error→i18n-Mapping (`mapSSEError`). Alle AI-Operationen **müssen** diesen Hook nutzen (ADR-043).
- **PASS.** Ghost-Text: eigener AbortController (`storage._abortController`), Fehler-Status-Decoration (low-noise, auto-clear nach 4s), Fetching-Status-Decoration. Partial-Output wird im Cache gehalten.

**Mängel:**
- **Ghost-Text-i18n-Limitation** (`suggest.ts:16-19`): TipTap-Extensions laufen außerhalb des React-Lifecycle, daher kann `useAIOperation` nicht vollständig migriert werden. Error-Mapping passiert auf Transport-Ebene, aber die Extension selbst hat keinen i18n-Zugang — Errors werden „silent dismissal" gehandhabt. Dokumentiert (§20), aber suboptimale UX bei Ghost-Text-Fehlern (nur generische Decoration, keine lokalisierte Recovery-Action).
- **Kein Retry bei Ghost-Text.** Im Gegensatz zu `useAIOperation` hat Ghost-Text keine Auto-Retry-Logik bei Connection-Loss — nur Abort + Error-Decoration. Bei instabiler Verbindung kein automatischer Wiederholungsversuch.

**Bewertung:** ⭐⭐⭐⭐⭐
**Befunde:** _Herausragende TipTap/AI-Integration: GhostText mit ProseMirror-`Decoration.widget(side:1)` korrekt nicht-mutierend, 4-Phasen-Architektur (LRU-Cache, Analytics, Auto-Trigger, Typing-Mismatch-Detection), AIAnnotation-Mark mit Transaction-Survival + Modify-Detection, sauberste Komponententrennung (dünnere Controller, fokussierte Sub-Hooks, entkoppeltes Slash-Command-Modul), intuitive Accept/Reject-UX (Tab/Esc/→ + Modals + Diff), volle §16-Compliance via `connectSSE()`+`useAIOperation()` (AbortController, Connect-Timeout, Connection-Loss-Retry, Partial-Output). Kleinste Abzugsgründe: Ghost-Text-i18n-Limitation (Extension ohne React-Lifecycle → silent error dismissal) und fehlendes Ghost-Text-Auto-Retry — beide dokumentiert, aber UX-suboptimal._

---

## 9. AI-Verbesserungspotenzial für den Nutzer

**Befunde:**

Aktuelle AI-Unterstützung ist bereits breit (Inline-Suggest, Co-Author, Rewrite, Consistency, BetaReader, CharacterVoice, Readability, POV, Coreference, Timeline, FactExtraction, Worldbuilding, KB-Interview, Preference-Learning, Sentiment). Bewertung des einzelnen Verbesserungspotenzials:

| Idee | Fit für Narrare | Wert für Romanautoren | Aufwand | Voraussetzungen | Aktuelles Niveau |
|---|---|---|---|---|---|
| **Inline-Suggestions** | Hoch | Hoch — reduziert Schreibblockade, erhält Flow | **Bereits implementiert** (GhostText, v2.4.0) | KB-Kontext, Style-Profile, Voice-Profile | ⭐⭐⭐⭐⭐ Vorhanden |
| **Writing-Style-Analyse & Konsistenz** | Hoch | Hoch — einheitliche Stimme über 100k+ Wörter | **Teilweise implementiert** (Style-Profile via `{{style_profile}}`, `PreferenceAnalysisAgent`) | Manuskript-Korpus, Embeddings | ⭐⭐⭐⭐ Vorhanden (Profilierung); ⭐⭐⭐ Konsistenz-Check über Gesamt-Werk noch schwach |
| **Charakter-Konsistenz-Tracking** | Hoch | Hoch — Figurenstimme ist Kern des Romans | **Implementiert** (`CharacterVoiceAgent` + `CharacterVoiceCheckerAgent`, ANAL-008; `character_voice/system.md`) | Voice-Profile pro Figur, Dialog-Corpus | ⭐⭐⭐⭐ Vorhanden |
| **Plot-Hole-Detection** | Hoch | Hoch — strukturelle Integrität | **Implementiert** (`ConsistencyAgent` mit check_types `character/timeline/world/plot`, `consistency/system.md` v2.0.0, Fact-Extraction-Pipeline) | Fact-Extraction, KB-Entities, Timeline | ⭐⭐⭐⭐ Vorhanden (Evidence-Gates gegen False-Positives) |
| **Kontextsensitive Vorschläge (Genre/Ton)** | Hoch | Mittel —Genre-Konventionen einhalten | **Implementiert** (Genre/Ton in Meta + Feature-Prompts, `writing/tones/*.md` 9 Ton-Profile, `{{story_structure}}`) | Genre-Setup, Ton-Auswahl | ⭐⭐⭐⭐ Vorhanden |
| **Multi-Draft-Vergleich mit AI-Feedback** | Mittel | Hoch — Alternativen vergleichen, Iteration fördern | **Teilweise** (Style-Variant-Regeneration im Rewrite/Co-Author; `StyleVariantPicker`) | Style-Variant-Engine, Speicherung | ⭐⭐⭐ Partiell (Varianten vorhanden, kein direkter A/B-Vergleich mit AI-Bewertung) |
| **Leser-Perspektiven-Simulation** | Hoch | Sehr hoch — „Wirkt diese Szene, wenn Leser X nicht weiß?" | **Teilweise** (`BetaReaderAgent` + DeepDive, „reader's perspective") | — | ⭐⭐⭐⭐ Vorhanden (BetaReader); gezielter „wissender/unwissender Leser"-Kontrast nicht parametrisierbar |
| **Autonome Research-Agenten (Weltenbau)** | Mittel | Mittel-Hoch — Worldbuilding-Details recherchieren | **Nicht implementiert** (Worldbuilding-Agent generiert, aber kein autonomen Web-Research-Loop) | Web-Search-Tool, A2A/MCP, Safety-Guardrails | ⭐ Niedrig (generativ, nicht recherchierend) |
| **Emotionale Intensitätskurve visualisieren** | Hoch | Hoch — Pacing/Spannungsbogen über Kapitel | **Teilweise** (`useSentiment`, ANAL — pro-Kapitel); **Visualisierung fehlt** (keine Kapitel-übergreifende Kurve, recharts vorhanden aber nicht dafür genutzt) | Sentiment pro Szene, Zeitachsen-Mapping | ⭐⭐ Niedrig (Datenpunktion vorhanden, keine Kurven-Visualisierung über den Roman) |

**Zusätzliche Ideen (nicht in der Liste, aber wertvoll):**
- **Outline-vs-Draft-Abgleich:** Prüfen, ob der geschriebene Draft dem Outline folgt (`OutlineAgent` + `ReviewAgent` vorhanden, aber kein automatischer Drift-Report). Aufwand M.
- **Wiederholungs-/Redundanz-Detektor:** Häufige Phrasen, wiederholte Beschreibungen über Kapitel (nicht vorhanden). Aufwand M. Voraussetzung: Manuskript-Index.

**Bewertung:** ⭐⭐⭐⭐ (aktuelles Unterstützungsniveau)
**Befunde:** _Breite, reife AI-Unterstützung: 7 der 9 gelisteten Ideen sind bereits (teil-)implementiert (Inline-Suggest, Style/Konsistenz, Character-Voice, Plot-Hole, kontextsensitive Vorschläge, Leser-Perspektive via BetaReader, Multi-Draft partiell). Größte Hebel für nächsten Mehrwert: (1) Emotionale Intensitätskurve — Sentiment-Daten vorhanden, aber keine Roman-Spannungsbogen-Visualisierung (recharts läge bereit); (2) Autonome Research-Agenten für Weltenbau (aktuell nur generativ, kein Web-Research); (3) direkter Multi-Draft-A/B-Vergleich mit AI-Bewertung (Variant-Engine existiert, aber kein Vergleichs-Workflow). Alles in allem schon weit über Durchschnitt für AI-Schreibtools._

---

## Gesamtbewertung AI-Features & Prompting

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** _keine (erstes Audit)_ | **Trend:** ➡️ (Basis-Audit)
**Zusammenfassung:** Narrare besitzt ein architektonisch herausragend gereiftes AI/Prompting-Fundament: ADR-026-Dreiteilung (Capability/Cascade/Dynamic) wird konsistent durchgesetzt (RULE-02/02a/02b alle PASS), 30+ spezialisierte Agents erben korrekt von `NarrareAgent` mit Auto-Capability-Injection (RULE-01b PASS), Modelle ausschließlich via ModelRegistry aufgelöst, die TipTap/GhostText-Integration ist ein herausragendes Herzstück mit ProseMirror-konformer nicht-mutierender Decoration-Architektur und voller §16-SSE-Lifecycle-Compliance. Schwächen: Feature-Prompts sind EN-only (de/fr-Fallback nur für Meta/Universal), `AnalysisPanel.tsx` ist ein verwaiseter Placeholder, MCP/A2A sind nicht implementiert (blockiert durch Q-001/Q-002), und konkrete Hebel wie emotionale Intensitätskurve sowie autonome Research-Agenten sind noch ungenutzt. In Summe deutlich über dem Durchschnitt AI-gestützter Schreibtools, mit klarem, dokumentiertem Pfad für die verbleibenden Lücken.

---

## Aufgaben

### [AUFG-03-01] Feature-Prompts auf de/fr übersetzen (i18n-Vollständigkeit)
**Priorität:** Mittel
**Bereich:** AI
**Kontext:** Nur `meta/` und `universal/` haben `de/`+`fr/`-Übersetzungen. Alle `writing/`, `analysis/`, `kb/`, `planning/`-Prompts existieren ausschließlich in `en/`. Bei `language=de/fr` liefert die Cascade zwar lokalisierte Meta-/Universal-Regeln, fällt aber für die Feature-Instruktionen auf EN zurück. Das i18n-Versprechen für Prompts ist damit nicht vollständig eingelöst (das UI ist lokalisiert, die AI-Instruktionen größtenteils nicht).
**Akzeptanzkriterien:**
- [ ] Priorisierte Feature-Prompts (`inline_suggest`, `co_author`, `rewrite_selection`, `new_chapter`, `chat`, `interview`) in `de/` und `fr/` übersetzt
- [ ] Cascade-Fallback-Test (`de` → bundled-de → bundled-en) greift korrekt
- [ ] `check_prompt_structure.py` prüft Parität der übersetzten Prompt-Versionen
- [ ] Bestehende EN-Prompts bleiben Source-of-Truth; Übersetzungen folgen `prompt_version`
**Geschätzter Aufwand:** L

### [AUFG-03-02] Verwaisten `AnalysisPanel.tsx`-Placeholder entfernen oder verdrahten
**Priorität:** Mittel
**Bereich:** AI / DX
**Kontext:** `packages/web/components/studio/AnalysisPanel.tsx:53-57` ist ein unverbundener Placeholder: `setTimeout(() => setIsAnalyzing(false), 1500)` ohne realen API-Call (explizites TODO). Die eigentlichen Analyse-Features (Consistency, BetaReader, CharacterVoice, Readability, POV) sind woanders voll verdrahtet (`components/studio/analysis/`). Das Placeholder-Panel verwirrt Nutzer („analyzing" ohne Ergebnis) und suggeriert fälschlich Unvollständigkeit. Fall von „documented ≠ implemented" (architectural-discipline §7).
**Akzeptanzkriterien:**
- [ ] Entweder: `AnalysisPanel.tsx` an echte Analyse-APIs verdrahtet (ConsistencyStream/BetaReader/etc. nutzen) ODER entfernt/gelöscht, falls redundant mit `components/studio/analysis/`
- [ ] Kein `setTimeout`-Fake-Loading mehr in produktivem Code
- [ ] Falls entfernt: keine dangling Imports / toten Routen
- [ ] i18n-Keys bereinigt, falls Panel entfernt
**Geschätzter Aufwand:** S

### [AUFG-03-03] Ghost-Text-Auto-Retry bei Connection-Loss ergänzen
**Priorität:** Niedrig
**Bereich:** AI
**Kontext:** Die `GhostText`-Extension (`extensions/GhostText.ts`) hat im Gegensatz zu `useAIOperation()` (§16-konform mit `DEFAULT_MAX_RETRIES`) keine Auto-Retry-Logik bei Connection-Loss — nur Abort + transiente Error-Decoration (auto-clear nach 4s). Bei instabiler Netzwerkverbindung erhält der Nutzer keinen automatischen Wiederholungsversuch für Inline-Suggestions, was den Schreib-Flow stört. Die Limitation ist in `suggest.ts:16-19` dokumentiert (TipTap-Extensions laufen außerhalb React-Lifecycle → keine `useAIOperation`-Migration möglich).
**Akzeptanzkriterien:**
- [ ] Ghost-Text-Fetcher hat begrenzte Retry-Logik (z. B. 1 Retry nach kurzem Backoff bei Network-Error, nicht bei Abort)
- [ ] Retry-Logik lebt im Extension-Scope (keine React-Hook-Abhängigkeit)
- [ ] Unit-Test für Retry-Verhalten (Fake-Fetcher)
- [ ] Keine Regression bei Abort-Handling
**Geschätzter Aufwand:** S

### [AUFG-03-04] Emotionale Intensitätskurve über Kapitel visualisieren
**Priorität:** Mittel
**Bereich:** AI
**Kontext:** Sentiment-Daten sind pro Kapitel vorhanden (`useSentiment`, ANAL), und `recharts` (`^3.9.1`) liegt im Stack — aber es gibt keine Roman-weite Visualisierung der emotionalen Intensität / des Spannungsbogens über alle Kapitel hinweg. Für Romanautoren ist dies ein hochgradig wertvolles Pacing-Werkzeug („hängt Kapitel 12 emotional durch?"). Größter ungenutzter Hebel aus §9.
**Akzeptanzkriterien:**
- [ ] Endpoint/Aggregation, der Sentiment pro Kapitel (oder pro Szene) über den gesamten Roman liefert
- [ ] Visualisierung als Kurve/Chart (recharts) in der Studio-Workspace
- [ ] Zeitachsen-Mapping (Kapitel-Reihenfolge oder Timeline-Position)
- [ ] Interaktiv: Klick auf Datenpunkt → Sprung zum Kapitel
- [ ] i18n der Achsen/Labels (RULE-16)
**Geschätzter Aufwand:** M

### [AUFG-03-05] Meta-Lite-Variante: Selektor verifizieren oder entfernen
**Priorität:** Niedrig
**Bereich:** AI
**Kontext:** `_bundled/meta/{lang}/system.lite.md` existiert (8 Zeilen, `variant: lite`), aber im Code ist kein Aufrufer erkennbar, der `variant: lite` gegenüber der Full-Version (`system.md`) selektiert. `meta.py:_load_meta_prompt()` lädt fix `system.md`. Möglicherweise tote Konfiguration, die Token-Einsparung verspricht (Lite ≈ 8 vs. Full ≈ 33 Zeilen), aber nie greift.
**Akzeptanzkriterien:**
- [ ] Entweder: Selektor implementiert (z. B. `NarrareMeta(variant="lite")` für Kontext-budget-kritische Agents, z. B. Inline-Suggest) mit dokumentierter Auswahl-Regel
- [ ] Oder: Lite-Variante entfernt, wenn kein Use-Case existiert
- [ ] Falls implementiert: Test, der Lite vs. Full korrekt schaltet
- [ ] Update der Capability-Doku
**Geschätzter Aufwand:** S

### [AUFG-03-06] Cross-Agent-Kontext-Teilung für aufeinanderfolgende Werkzeug-Aufrufe
**Priorität:** Niedrig
**Bereich:** AI / Architektur
**Kontext:** Kontext-Weitergabe zwischen Agenten funktioniert nur innerhalb eines Graph-Runs (`WritingGraph`) oder einer Chat-Session (`ProcessHistory`). Möchte ein Autor Ergebnisse aus einem Consistency-Check in den nächsten Co-Author-Lauf einspeisen, muss er manuell vermitteln. Es gibt kein „Shared-Agent-Memory" jenseits von mem0-Preferences. Dies begrenzt Workflow-Komposition (z. B. Consistency-Finding → Co-Author-Fix → Re-Check).
**Akzeptanzkriterien:**
- [ ] ADR/Dokumentation, ob und wie Cross-Agent-Kontext geteilt werden soll (z. B. Session-gebundener Kontext-Speicher, der Agent-Outputs annotiert)
- [ ] Falls umgesetzt: definierter Integration-Contract (RULE-22) zwischen Konsumenten- und Produzenten-Agent
- [ ] Graceful Degradation, falls Kontext-Speicher unavailable
**Geschätzter Aufwand:** L

### [AUFG-03-07] Skill-Duplikation zwischen `.agents/skills/`, `.opencode/skills/` und Superpowers auflösen
**Priorität:** Niedrig
**Bereich:** DX
**Kontext:** Skills existieren parallel in `.agents/skills/` (z. B. `task-management`), `.opencode/skills/` (`task-management`, `context7`) und dem Superpowers-Cache (`task-management`, `handoff` vs. `commit-context`). Die Überlappung kann zu Mehrdeutigkeit führen, welcher Skill bei einem Trigger greift, und erschwert die Wartung (Drift zwischen Duplikaten).
**Akzeptanzkriterien:**
- [ ] Inventarisierung aller Skills über die drei Quellen
- [ ] Klare Ownership-Zuweisung (welcher Skill ist kanonisch, welcher ist Wrapper/Verweis)
- [ ] Duplikate entweder konsolidiert oder als dokumentierte Aliasse markiert
- [ ] Navigation/Doku für Agent-Autoren, welcher Skill wo zu finden ist
**Geschätzter Aufwand:** S
