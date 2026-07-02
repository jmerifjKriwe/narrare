# Review 01 – Architektur & Code-Qualität

> Aktualisiert am 2026-06-29 durch NarrarePlatformSpecialist. Grundlage:
> `_audit/results/technical-review/review-00-kontext.md`,
> `docs/_shared/CONSTRAINTS.md` als SSOT, aktuelle Code-/Checker-Evidenz und
> Code-Graph. Alte erledigte Befunde aus früheren Reviews (`useExtractionPhase`
> RULE-04/AI-UX, `NameGenerator` AbortController-Test, `auth/router_me.py`
> Router-DB-Query, direkter mem0-Import in `_app/dependencies.py`) werden nicht
> erneut als offen geführt.

> **Re-Check am 2026-07-01 durch NarrareCoordinator** (verifiziert via Code-Graph
> `callers_of` + Grep + Live-Checks im sauberen Worktree `review-01-remediation`).
> Dieser Re-Check hält den verifizierten Ist-Stand fest; keine der drei Aufgaben
> wurde dabei implementiert (Akzeptanzkriterien bleiben `[ ]`).

## Methodik & ausgeführte Prüfungen

- Graph-first ausgeführt: `get_minimal_context`, `list_graph_stats`,
  `get_architecture_overview`, `list_communities`, `get_knowledge_gaps`,
  `find_large_functions` (File + Function), `get_hub_nodes`,
  `get_bridge_nodes`, `semantic_search_nodes`, `query_graph` für Beziehungen.
- Graph-Snapshot: 26.084 Nodes, 185.730 Edges, 2.777 Files, Sprachen Python,
  Bash, TypeScript, TSX, JavaScript; Graph-Update 2026-06-29T18:23:23;
  Embeddings: 0.
- Top-Communities (size ≥100): `tests-it:renders` (591), mehrere `tests-when`,
  `planning-service` (452), `scripts-check` (345), `prompts-prompt` (321),
  `fakes-called` (317), `analysis-when` (266), `chapters-service` (174).
- Graph-Hotspots: `fetchApi` (degree 161), `useTipTapEditorController`
  (degree 117), `KBSessionFieldList` (111), `MetadataSidebar` (94),
  `useKnowledgeGraphController` (92). Bridge-Knoten liegen überwiegend in Tests;
  produktive Bridge-/Hub-Knoten sind `fetchApi` und `setAccessToken`.
- Knowledge-Gaps-Ausgabe war groß/truncated; maschinell zusammengefasst:
  50 isolated nodes, 2.169 thin communities, 20 untested hotspots. Viele Treffer
  sind Tests/Tooling/Alembic; produktiv relevant bleiben vor allem Frontend-Hubs.

### Checks

| Check | Ergebnis |
|---|---|
| `just check-architecture` | ✅ 1.913 Dateien, 16 genehmigte Exceptions; Exception-Baseline 11 current / 11 baseline / 0 new; Prompt Surface Contract OK |
| `just check-python-size` | ✅ alle Python-Dateien innerhalb RULE-04; Ratchet 0 current, 2 baseline resolved |
| `just check-frontend-size` | ✅ alle TS/TSX-Dateien innerhalb RULE-04; Ratchet 0 current / 0 baseline |
| `just check-locale-sync` | ✅ 42 Prompt-Gruppen synced, 0 drifted |
| `pnpm exec tsx scripts/validate-i18n.ts` | ✅ 2 Locales gegen EN, 2.487 Keys, ICU konsistent, Backend-Textcheck OK |
| `just check-configuration-matrix` | ✅ 25 expected setting_ids, 25 Matrix-Einträge, 0 Violations |
| `just check-streaming` | ✅ 3 SSE-Endpunkte, alle Frontend-Consumer über `connectSSE()` |
| `just check-prompts-strict` | ✅ 48/48 System-Prompts gültig, Prompt-Warning-Ratchet 0 |
| `just check-adoption` | ✅ Score 0.97 PASS; `analysis/character_voice` runtime ✅ adopted ✅; Adoption debt ratchet 1 current / 121 baseline / 120 resolved |
| `just check-ai-ux` | ✅ 0 Violations, 3 governed exclusions |
| RULE-17 Stichprobe | ✅ 23 passed, 17 skipped für ausgewählte Cross-Layer-Contract-Tests |
| `just check-health` | ✅ 0.88 HEALTHY, aber `feature_adoption` bleibt 0.50 wegen 121 baseline items *(Stand 2026-07-01: 0.87 / 1 baseline — durch WRITE-010-Arbeit behoben)* |
| `just check-frontend` | ⚠️ lokal nach 180s mit Exit 143 abgebrochen; viele Tests waren bereits grün, aber kein vollständiger PASS-Nachweis in dieser Session |

### Re-Check 2026-07-01 (verifizierte Ist-Werte)

Verifiziert durch NarrareCoordinator via Code-Graph (`callers_of`) + Grep +
Live-Checks im sauberen Worktree `review-01-remediation` (Branch, Stand
2026-07-01). Keine Aufgabe wurde in diesem Durchgang implementiert; die Tabelle
hält den verifizierten Ist-Stand fest (vgl. AUFG-01-01/02/03 unten).

| Aufgabe | Verifizierter Ist-Stand (2026-07-01) | Status |
|---|---|---|
| **AUFG-01-01** Retry-Settings | `packages/core/narrare_core/llm/retry.py::with_retry` hat laut Graph **nur 14 Test-Caller** (`tests/unit/core/llm/test_retry.py`) und **0 Produktions-Caller** (Grep bestätigt). `RetryConfig` wird exportiert (`narrare_core/llm/__init__.py`: `DEFAULT_RETRY`/`FAST_RETRY`/`PATIENT_RETRY`/`NO_RETRY`), ist aber in Produktion ungenutzt. `retry.py` zuletzt geändert 2026-05-24 (CR-08, `f463e17d`). Matrix-Eintrag `websocket_idle_retry_cascade` (`docs/architecture/governance/configuration-adoption-matrix.yaml:656-674`) aggregiert weiterhin 3 Settings unter einem `lifecycle: adopted`; dessen `runtime_consumer`/Evidence decken **nur** `ws_timeout` → `WritingSessionHandler` ab — die beiden `retry_*`-Felder bleiben false controls. | **OFFEN** |
| **AUFG-01-02** `character_voice` | `just check-health` feature_adoption: war **0.50 (121 baseline)** zum Audit → **jetzt 0.87 (1 baseline)**. Die 121→1-Bereinigung erfolgte via WRITE-010 (2026-06-30, adoption_debt 5→1) — dieser Teil des Widerspruchs ist **gelöst**. `just check-adoption`: **PASS 0.97, 1 current / 1 baseline / 0 new** (die 0.97-Zahl des Audits bleibt korrekt). check-health und check-adoption sind nun konsistent (jeweils ~1 debt); der zum Audit schwere Widerspruch ist aufgelöst. `CURRENT_STATE.md` (2026-06-30) und `ANAL-008` (Zeile 327, `df10b814`) nennen `character_voice` jetzt "runtime-verified". **Verbleibende Drift:** `docs/features/INDEX.md:126-127` ist veraltet — sagt weiterhin "runtime adoption = governed debt (static-verified; runtime evidence pending CI/integration)". (INDEX.md-Korrektur ist separate Stage-3b-Aufgabe; hier nur als stale dokumentiert.) | **WEITGEHEND GELÖST** (nur INDEX.md stale) |
| **AUFG-01-03** Editor-/Writing-Hotspots | Verifiziert via Graph: `useTipTapEditorController` (`packages/web/components/studio/editor/TipTapEditorController.ts`) ist **334 Zeilen (66–400)**, degree **117**; `WritingPipeline.generate` (`packages/core/narrare_core/writing/pipeline.py`) ist **205 Zeilen (75–280)**. Keine Modularisierung erfolgt. | **OFFEN** |

> **Update 2026-07-01 (Remediation):** Alle drei Aufgaben (AUFG-01-01, AUFG-01-02, AUFG-01-03↔AUFG-01-08) sind nachfolgend **ERLEDIGT** worden — siehe §Aufgaben (pro Aufgabe: ERLEDIGT-Statuszeile + Akzeptanzkriterien `[x]`) sowie §Abschluss-Status unten. Diese Tabelle hält unverändert den historischen Ist-Stand des Re-Checks fest.

**Querschnitt — Registry-Hygiene (cross-cutting).**
`docs/architecture/governance/aufg-registry.md` fehlt AUFG-01-02 vollständig;
der dortige Eintrag "AUFG-01-03" ist ein *unrelated* Eintrag (MCP/A2A), nicht
die Editor-/Writing-Hotspot-Aufgabe. AUFG-01-01s Registry-Eintrag nennt als
Quelle "review-05-release.md" (sollte review-01 sein) und als
Abhängigkeitspfad `_retry.py` (tatsächlich `retry.py`). (Nur dokumentiert;
Registry-Fix obliegt einem anderen Specialist.)

---

## 1. Gesamt-Architektur & Regel-Prüfung

**Bewertung:** ⭐⭐⭐⭐ `Gut, mit zwei Governance-/Effect-Integrity-Risiken`

**Befunde:**
- Architektur-Muster: Layered/Clean-ish. Zielrichtung bleibt klar:
  `FastAPI Router/Adapter → Service → Repository → DB`, Core ohne HTTP/DB,
  Agents/Prompt/LLM unter `packages/core/narrare_core/*`, WebUI als separater
  Next.js Adapter. CLI ist Dev-/Ops-Fläche, kein Produktadapter; MCP/A2A sind
  weiterhin nicht implementiert.
- Regel-Gates sind überwiegend stark: Architekturcheck, Prompt-Struktur,
  File-Size-Ratchets, Streaming-Compliance, Locale-Sync, i18n-Validation,
  Configuration-Matrix und AI-UX sind grün.
- RULE-01b: grün mit genehmigten, baseline-stabilen Exceptions in
  `setup/provider_service.py`, `planning/remap.py`, Wiki-Agenten und
  `llm/gateway.py`. Keine neue Exception.
- RULE-02/02a/02b: `check-prompts-strict` und Prompt Surface Contract grün;
  48/48 System-Prompts gültig. `check-adoption` meldet ADR-046 Prompt-Path
  Compliance vollständig compliant.
- RULE-03: Domainmodule zeigen breite Contract-Struktur (`contracts.py`,
  Service-/Repository-Protokolle); Stichproben Memory/Analysis/Writing nutzen
  explizite Contracts. Kein neues Modul ohne Contract als Befund gefunden.
- RULE-04/06: Harte Python- und Frontend-File-Size-Gates sind grün. Der Graph
  zeigt trotzdem große produktive Funktionen, u. a.
  `useTipTapEditorController` 335 Zeilen,
  `useGenerationPanelController` 231 Zeilen,
  `WritingPipeline.generate` 206 Zeilen,
  `useKBAssistedCreationController` 194 Zeilen,
  `WritingContextAssembler.assemble` 185 Zeilen. Das ist kein aktueller
  Gate-Bruch, aber ein nachhaltiges Refactoring-Risiko.
- RULE-14: In diesem Review keine geänderten Model-/Migration-Diffs; keine
  aktuelle Modeländerung als Befund. Alembic-Hubs im Graph sind erwartbar.
- RULE-15: Architekturcheck grün; keine `middleware.ts`-Regression.
- RULE-16/17: Frontend-i18n-Registry-Test existiert
  (`packages/web/__tests__/i18n-namespace-registry.test.ts`) und i18n-Validation
  ist grün. Ausgewählte API↔Frontend-Contract-Tests liefen 23 passed / 17 skipped.
- RULE-18/19: Architekturcheck grün. Gezielt gesucht nach `session.execute` in
  `router*.py`: nur `apps/api/narrare/metrics/router.py:43`, genehmigte Health-
  Check-Exception.
- RULE-18b: `check-configuration-matrix` ist formal grün, aber ein semantischer
  Befund bleibt: `websocket_idle_retry_cascade` bündelt `ws_timeout`,
  `retry_max_attempts` und `retry_base_delay`; Code-Evidenz zeigt nur
  `ws_timeout` bis `WritingSessionHandler` (`router_sessions.py:148`).
  `RetryConfig`/`with_retry` in `core/llm/retry.py` haben laut Graph nur
  Test-Caller. Das ist eine mögliche false-control-Lücke für die beiden
  Retry-Felder (Details in Abschnitt 5).
- RULE-20: `just check-streaming` grün; 3 SSE-Endpunkte sind an `connectSSE()`
  angebunden.
- RULE-22/Adoption: Current docs sind widersprüchlich. `CURRENT_STATE.md` und
  `docs/features/INDEX.md` nennen `character_voice` runtime adoption weiterhin
  governed debt/pending; `just check-adoption` meldet aktuell runtime ✅ adopted ✅.
  Zusätzlich bewertet `just check-health` Feature Adoption mit 0.50 wegen 121
  baseline items, obwohl `check-adoption` nur noch 1 current item meldet.
  *(Re-Check 2026-07-01: `check-health` und `check-adoption` sind inzwischen
  konsistent — beide melden ~1 debt (`check-health` feature_adoption 0.87 / 1
  baseline; `check-adoption` 0.97 PASS, 1 current / 1 baseline). Der zum
  Audit-Zeitpunkt schwere Widerspruch ist aufgelöst. Einzig
  `docs/features/INDEX.md:126` bleibt stale und nennt weiterhin governed debt —
  siehe AUFG-01-02.)*

**Root Cause:** Die Kernarchitektur ist stabil, aber Governance-Metadaten
klassifizieren teilweise aggregierte Einstellungen/Statuszustände, ohne dass der
Checker die Wirkung jedes einzelnen Feldes bzw. jeden Status-Snapshot semantisch
gegen Runtime-Evidenz validiert.

**Alternativen betrachtet:**
1. Nur Checker-Grün übernehmen — verworfen, weil Architectural Discipline
   „Check grün“ nicht mit End-to-End-Korrektheit gleichsetzt.
2. Alle Settings als offen markieren — verworfen, weil `ws_timeout` und viele
   CR-08-Werte real konsumiert und getestet sind.
3. Gewählt: nur konkrete, belegte Drift (`retry_*`-Effect und Adoption-Status)
   als Aufgaben führen.

---

## 2. Service Layer

**Bewertung:** ⭐⭐⭐⭐ `Konsequent dünne Router; einzelne DI-Factories bleiben komplex`

**Befunde:**
- Expliziter Service Layer existiert in `apps/api/narrare/<domain>/service*.py`;
  Repositories kapseln SQLAlchemy, Core bleibt HTTP-/DB-frei. Das Muster ist in
  Memory, KB, Analysis, Writing, Settings, Wiki, Chapters und Planning sichtbar.
- Router delegieren überwiegend sofort an Services. `grep` nach direkten
  `session.execute`/`.execute(` in `router*.py` fand nur die genehmigte
  Health-Check-Exception `metrics/router.py:43`.
- Memory ist sauberer als im alten Review: Router (`memory/router.py`) nutzt
  `SessionDep`, Factory baut Repository/Core-Service, Route delegiert an
  `MemoryFeedbackService` / `MemoryPreferenceService`. Raw `source_id` wird vor
  mem0/DB in einen Hash transformiert (`service.py:102-106`).
- Der alte direkte DB-Zugriff in `auth/router_me.py` ist nicht mehr reproduzierbar.
- Komplexität sitzt zunehmend in Dependency-Factories/Wiring statt in Routern:
  Memory baut im Router eine `_persist_adapter`-Callback-Brücke; Writing-Session
  löst mehrere Runtime-Abhängigkeiten vor Handler-Aufbau. Das ist noch kein
  Verstoß, aber zukünftige Adapter (MCP/A2A) sollten diese Factories nicht
  kopieren, sondern über dedizierte DI-/adapterunabhängige Factorymodule nutzen.
- Services sind überwiegend zustandslos/DI-getrieben. Ausnahmen sind bewusst als
  Singletons/Caches dokumentiert (`dependencies_prompts.py` Prompt/Preference
  Singletons, `MemoryClientCache`).

---

## 3. Code-Duplikate zwischen API, CLI, MCP und WebUI

**Feature-Gap-Matrix:**

| Funktion | CLI | API | MCP | WebUI |
|---|---:|---:|---:|---:|
| Auth/Login/Setup | ✗ Produkt-CLI | ✓ | ✗ | ✓ |
| Novel/Volume/Chapter CRUD | ✗ | ✓ | ✗ | ✓ |
| Writing: generate/extend/rewrite/co-author/chat/inline/story suggest | ✗ | ✓ | ✗ | ✓ |
| KB Entries/Sessions/Extraction/Improve/Merge/Worldbuilding | ✗ | ✓ | ✗ | ✓ |
| Planning/Timeline/Character Arc | ✗ | ✓ | ✗ | ✓ |
| Analysis: readability, POV, beta reader, sentiment, consistency, coreference, character voice | ✗ | ✓ | ✗ | ✓ |
| Prompt management/customization/history/live test | ✗ | ✓ | ✗ | ✓ |
| Memory/preferences/feedback | ✗ | ✓ | ✗ | ✓ |
| MCP/A2A exposure | ✗ | ✗ | ✗ | ✗ |

**Bewertung:** ⭐⭐⭐⭐ `API/Web kohärent; Multi-Adapter bleibt Roadmap`

**Befunde:**
- Real implementierte Produkt-Einstiegspunkte sind API und WebUI. CLI bleibt
  Dev-/Ops (`just`, Setup-Skripte, Evals); MCP/A2A sind laut Review-00,
  Feature-Index und offenen Fragen geplant/nicht implementiert.
- Kein aktueller Copy-Paste-Befund zwischen CLI/API/MCP/WebUI, weil nur API/Web
  produktiv existieren.
- Strukturelle Prävention ist vorhanden: Services/Contracts vor Implementation,
  RULE-13 gemeinsame Streaming-/Non-Streaming-Signaturen, RULE-17 Contract-Tests.
- Risiko: Einige API-DI-Factories enthalten adapterrelevantes Wiring. Wenn MCP/A2A
  später kommen, sollten sie auf Core/API-Service-Contracts aufsetzen und keine
  Router-Factories kopieren.

---

## 4. i18n-Implementierung

**Bewertung:** ⭐⭐⭐⭐⭐ `Maschinell gut abgesichert`

**Befunde:**
- Frontend nutzt `next-intl`; unterstützte UI-Sprachen: EN/DE/FR. Message-Dateien
  liegen in `packages/i18n/messages/{en,de,fr}`.
- `packages/web/lib/i18n/request.ts` registriert die Namespaces `common`, `auth`,
  `wizard`, `dashboard`, `editor`, `errors`, `generation`, `settings`,
  `settings-ai`, `settings-appearance`, `studio`, `analysis`, `timeline`.
- RULE-16 ist durch `packages/web/__tests__/i18n-namespace-registry.test.ts`
  geschützt: alle `useTranslations("X")`-Namespaces müssen in `request.ts`
  registriert sein.
- `pnpm exec tsx scripts/validate-i18n.ts` ist grün: 2 Locales gegen EN,
  2.487 Keys, ICU-Placeholder konsistent, Backend-Textcheck ohne Befund.
- Prompt-Locale-Sync ist grün: 42 Gruppen synced, 0 drifted. EN-only
  Feature-Prompts bleiben nach aktueller Prompt-Policy zulässig; Meta/Universal
  sind mehrsprachig.

---

## 5. API-Timeout- und Fehlerbehandlung

**Bewertung:** ⭐⭐⭐ `Gute zentrale Muster, aber Retry-Einstellungen wirken nicht nachweisbar bis zur Runtime`

**Befunde:**
- SSE-Transport ist zentral: `packages/web/lib/api/streaming.ts` definiert
  `DEFAULT_CONNECT_TIMEOUT_MS = 30_000`, kombiniert Caller-Signal und internes
  Timeout-Signal via `AbortSignal.any()`, normalisiert Fehler über
  `SSEStreamError`, und `check-streaming` bestätigt alle SSE-Endpoints.
- WebSocket idle timeout ist real verdrahtet: `Settings.ws_idle_timeout_seconds`
  (`settings_model.py:121-125`) → `TokenLimitsService._apply_env_layer()`
  (`token_limits/service.py:199-206`) → `router_sessions.py:148` als
  `ws_idle_timeout=limits.ws_timeout`.
- Fehlerbehandlung Backend: RULE-11-Gate grün. mem0-Fallbacks loggen und
  degradieren zu `NullMemoryClient`; Router/Services re-raise/konvertieren
  relevante Domainfehler.
- **Konkreter Befund (RULE-18b):** `retry_max_attempts` und `retry_base_delay`
  sind als API/UI-Felder vorhanden (`schemas.py:157-159`, `SystemTimeouts.tsx`),
  werden vom TokenLimitsService resolved (`service.py:205-206`, `278-283`) und
  in der Matrix unter `websocket_idle_retry_cascade` als adopted geführt
  (`configuration-adoption-matrix.yaml:656-674`). Die tatsächliche Retry-Engine
  `packages/core/narrare_core/llm/retry.py::with_retry` hat laut Graph jedoch nur
  Test-Caller; eine Produktionseinbindung dieser beiden resolved Werte an einer
  LLM-/WebSocket-/SSE-Retry-Boundary wurde nicht gefunden. Damit kann `just
  check-configuration-matrix` formal grün sein, obwohl die beiden Retry-Felder
  möglicherweise false controls sind.
- `just check-frontend` konnte lokal nicht vollständig bewiesen werden (Timeout
  180s, Exit 143). Das ist kein Code-Finding, aber der Review markiert Frontend-
  Full-Gate hier als nicht vollständig verifiziert.

---

## 6. mem0 / memU – Implementierung

**Bewertung:** ⭐⭐⭐⭐ `Adapter-Boundary deutlich verbessert; Provider-Cascade bewusst operatorlastig`

**Befunde:**
- mem0 ist im Core-Adapter gekapselt: `narrare_core/memory/mem0_client.py`
  importiert `mem0` nur innerhalb der Factory (`lines 294-297`, `361-364`) und
  fällt bei Import-/Creation-Fehlern auf `NullMemoryClient` zurück.
- Die frühere Boundary-Leak-Stelle ist behoben: `apps/api/narrare/_app/dependencies_prompts.py`
  nutzt `is_mem0_available()` und `detect_provider_from_env()` aus
  `narrare_core.memory.availability`; kein direkter mem0-Import in `_app`.
- Persistenz/Invalidierung: `MemoryFeedbackService.record_feedback()` persistiert
  Feedback über Repository/Core-Service; `MemoryPreferenceService.reset_preferences()`
  löscht DB-Events und ruft `PreferenceService.reset()` auf. `FeedbackService`
  persistiert zuerst und forwardet mem0 best-effort.
- Datenschutz: Raw `source_id` wird nicht an mem0 weitergegeben; stattdessen
  `source_id_hash` + Version (`apps/api/narrare/memory/service.py:102-106`).
  `FeedbackService._translate_to_memory_text()` speichert nicht den Rohvorschlag
  oder Nutzer-Rewrite, sondern action/intent/rating/kontextuelle Metadaten.
- Provider-Erkennung bleibt env-basiert und bewusst schmal
  (`availability.py:21-24`: OpenAI/Anthropic). Das widerspricht nicht aktuell der
  Matrix (`mem0_defaults` als operator_default), sollte aber nicht als
  user-/project-configurable Memory-Provider beworben werden, solange keine
  echte Settings-/ModelRouting-Cascade bis mem0 nachgewiesen ist.

---

## 7. Refactoring-Kandidaten

| Priorität | Datei/Modul | Problem | Architektonisch saubere Lösung |
|---:|---|---|---|
| 1 | `docs/architecture/governance/configuration-adoption-matrix.yaml` + `apps/api/narrare/settings/token_limits/*` + `packages/core/narrare_core/llm/retry.py` | `retry_max_attempts`/`retry_base_delay` sind exposed/resolved, aber kein Produktions-Caller von `with_retry`; Matrix aggregiert sie mit real adoptiertem `ws_timeout`. | Setting-IDs für `ws_timeout` und `retry_*` trennen; entweder Retry-Werte an die richtige Runtime-Boundary anbinden und mit Effect-Tests belegen oder als `formal_finding` führen. |
| 2 | `docs/_shared/CURRENT_STATE.md`, `docs/features/INDEX.md`, Adoption-/Health-Ratchets | `character_voice` wird in Docs als governed debt geführt, `check-adoption` meldet runtime adopted; `check-health` zählt 121 baseline items. | Eine SSOT-Statussemantik herstellen: Evidence akzeptieren und Docs/Health aktualisieren oder Checker-Evidence als ungültig markieren und Finding offen halten. |
| 3 | `packages/web/components/studio/editor/TipTapEditorController.ts` | Graph: 335-Zeilen Hook, degree 117; zentraler Editor-Hotspot. | Controller nach synchronen Zustands-, Persistence-, Command- und AI-Orchestration-Hooks splitten; öffentliche Hook-API stabil halten. |
| 4 | `packages/core/narrare_core/writing/pipeline.py::WritingPipeline.generate` | 206-Zeilen Core-Orchestrierung an einer kritischen Writing-Boundary. | Pipeline-Stages mit expliziten Stage-Contracts extrahieren (context, budget, invocation, validation), ohne Prompt-/Agent-Abstraktionen zu umgehen. |
| 5 | `apps/api/narrare/memory/router.py` Factory-Wiring | Router-Fabrik enthält `_persist_adapter` DB-Modell-Mapping für Core-Callback; aktuell kein Verstoß, aber Adapter-Wiederverwendung wird erschwert. | Memory-Service-Factory/adapter module extrahieren; Router delegiert nur Dependency-Auflösung und Route-Aufruf. |

---

## Gesamtbewertung Architektur & Code-Qualität

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐⭐ | **Trend:** ➡️ Gleich / leicht besser
**Zusammenfassung:** Die harte Architektur- und Qualitätslage ist gut: zentrale
Gates für Constraints, Prompt Governance, i18n, Streaming, File Size,
Configuration Matrix und AI-UX sind grün. Frühere konkrete Regressionen sind
behoben. Die wichtigsten aktuellen Risiken liegen nicht in Routern oder
Prompt-Assembly, sondern in Governance-Wahrheit: aggregierte Retry-Settings
scheinen nicht vollständig bis zur Runtime zu wirken, und Adoption-Dokumentation,
Adoption-Checker und Health-Scoring widersprechen sich bei `character_voice` bzw.
Baseline-Debt. Review 02 kann starten, sollte diese Statusdrift aber als Kontext
mitnehmen.

---

## Erledigte Altbefunde aus vorherigem Review

- `useExtractionPhase.ts` RULE-04/AI-UX: erledigt. `check-frontend-size` und
  `check-ai-ux` sind grün.
- `NameGenerator` roher AbortController-Test: erledigt; AI-UX-Checker meldet 0
  Violations.
- `auth/router_me.py` direkte SQLAlchemy-Query: erledigt/nicht reproduzierbar;
  Router-DB-Grep findet nur die genehmigte Metrics-Exception.
- mem0 direkter Import in `_app/dependencies.py`: erledigt; Verfügbarkeit liegt
  in `narrare_core.memory.availability`.

---

## Ursachenanalyse & Prävention (Re-Check 2026-07-01)

> Warum traten diese Probleme trotz umfangreicher Dokumentation auf? Sechs verifizierte Ursachen (RC1–RC6) und ein Präventionsplan (P1–P6). Die ADRs zu P1/P2 (ADR-061) und P3/P5 (ADR-062) sind umgesetzt (✅ Implemented); P4 ist bewusst zurückgestellt, P6 in ADR-061s P1 integriert.

### Ursachen (RC1–RC6)

- **RC1 — Checker-Blindheit (geslichte Validierung):** `check-configuration-matrix`
  verifiziert, dass jeder Eintrag die Felder *hat*, nicht dass der genannte
  `runtime_consumer` den Wert an einer echten Call-Site auch konsumiert.
  Wiederholt die CR-04-Lektion (FIND-010/011) auf der Settings-Schicht.
- **RC2 — Aggregation verschleiert per-Field-Wahrheit:** `websocket_idle_retry_cascade`
  bündelt 3 Settings unter einem `adopted` + einem Consumer + einem
  Evidence-Set, sodass ein realer Consumer zwei false controls legitimiert.
  Verletzt RULE-18b (per-Setting-Intent auf Entry-Granularität).
- **RC3 — Mehrere Status-Snapshots ohne Reconcile-Invariante:** Der
  `character_voice`-Status lebt an 6 Stellen (CURRENT_STATE, INDEX, ANAL-Spec,
  `check-adoption` live, `check-health`-Ratchet, Adoption-Registry). Kein
  Checker erzwingt doc↔doc-Konsistenz → INDEX veraltete, als CURRENT_STATE
  aktualisiert wurde.
- **RC4 — Health-Ratchet vs. Adoption-Live (semantisches Gap):** `check-health`
  nutzt den geratchetten Baseline-Nenner; `check-adoption` berechnet current
  debt live. (Hier durch echte Arbeit weitgehend selbst korrigiert, aber das
  strukturelle Missverhältnis bleibt bestehen.)
- **RC5 — Review→Registry-Lifecycle-Gap:** Zwei der drei Review-01-Aufgaben
  gelangten nie in `aufg-registry.md`; AUFG-01-03 kollidiert mit einem
  unrelated Eintrag. Review-Aufgaben können im Markdown verschwinden.
- **RC6 — Review-Artefakt nicht mechanisch an Quelle verlinkt:** Es gibt keinen
  Gate, der Review-Findings an den zugehörigen Code/Checker bindet, sodass
  Drift unbemerkt überleben kann.

### Präventionsplan (P1–P6)

- **P1 — Per-Setting-Effect-Integrity-Checker:** `check-configuration-matrix`
  verifiziert gegen den Code-Graphen, dass der genannte `runtime_consumer` den
  aufgelösten Wert an einer echten Call-Site referenziert (Einträge ablehnen,
  deren cited Consumer das Setting nicht nutzt).
- **P2 — Aggregations-Verbot in der Matrix:** Jedes material setting erhält
  eigenen Eintrag mit eigenem Consumer + Evidence. `websocket_idle_retry_cascade`
  aufsplitten.
- **P3 — Status-SSOT + doc↔doc-Konsistenz-Checker:** Adoption-Registry als
  einzige Status-Quelle; ein Checker schlägt fehl, wenn INDEX/CURRENT_STATE/Spec
  der Registry widersprechen (z. B. INDEX "governed debt" vs. Registry
  "runtime-verified"). Erweitert ADR-047 auf Status-Konsistenz.
- **P4 — Health↔Adoption-Reconcile:** `check-health` `feature_adoption` liest
  denselben current-Wert wie `check-adoption`, ODER die Semantik wird explizit
  dokumentiert.
- **P5 — Review→Registry-Mandatory-Linking:** Gate, das verlangt, dass jedes
  `### [AUFG-XX-YY]` in `_audit/review-*.md` einen konsistenten Registry-Eintrag
  hat (passende ID, source=diese Review-Datei, korrekte Pfade).
- **P6 — Graph-gegründeter "adopted"-Nachweis:** `lifecycle: adopted` erfordert
  einen graph-verifizierten setting→resolver→consumer-Pfad, nicht nur eine
  YAML-Assertion.

> **Hinweis:** Die Präventions-ADRs sind umgesetzt — ADR-061 ✅ *Implemented* (P1+P2; P2 blockierend, P1 warning-only mit Clean-Baseline, ratchets später zu blockierend) und ADR-062 ✅ *Implemented* (P3+P5; beide warning-only, ratchets später zu blockierend). P4 (Health↔Adoption-Reconcile) ist als `accepted_enhancement` zurückgestellt; P6 ist als graph-groundeter Pfad in ADR-061s P1 integriert.

## Aufgaben

### [AUFG-01-01] Retry-Settings auf echte Runtime-Wirkung prüfen und governance-sicher klassifizieren
**Re-Check 2026-07-01:** **ERLEDIGT 2026-07-01** — ADR-060 ✅ *Implemented*: Provider-Layer-Transport-Retry (`core/llm/_transport_retry.py`, env `NARRARE_LLM_TRANSPORT_MAX_RETRIES`, default 2) in alle 7 Provider-Factories verdrahtet mit Effect-Test `tests/unit/core/llm/test_transport_retry.py`; falsche User-Oberfläche end-to-end entfernt (UI/API/validators/resolver/operator-env); `with_retry`/`RetryConfig` retired (verifiziert: 0 Produktions-Caller via Grep + Code-Graph); Matrix-Eintrag `websocket_idle_retry_cascade` aufgespalten in `ws_idle_timeout` + `llm_transport_retry`; `just check-configuration-matrix` green (26 Einträge, 0 Violations). `retry.py`/`test_retry.py` gelöscht (staged `D`).
**Priorität:** Hoch
**Bereich:** Architektur / DX
**Kontext:** `retry_max_attempts` und `retry_base_delay` sind UI/API-/Settings-Felder und werden resolved, aber `core/llm/retry.py::with_retry` hat laut Graph nur Test-Caller. RULE-18b verlangt Runtime-Consumer + Effect-Evidence pro material setting.
**Akzeptanzkriterien:**
- [x] `ws_timeout`, `retry_max_attempts` und `retry_base_delay` sind in der Configuration Adoption Matrix getrennt oder eindeutig pro Feld belegt.
- [x] Für jedes adopted Retry-Feld existiert ein Runtime-Consumer an der LLM-/SSE-/WebSocket-Retry-Boundary.
- [x] Regressionstest beweist, dass eine geänderte Retry-Einstellung das Runtime-Verhalten ändert oder eine dokumentierte Warnung/Fehler auslöst.
- [x] Falls Retry bewusst nicht runtime-configurable ist: UI/API/Matrix klassifizieren es als governed/operator default oder formal finding, nicht als adopted false control.
**Geschätzter Aufwand:** M

### [AUFG-01-02] `character_voice` Adoption-Status und Health-Baseline synchronisieren
**Re-Check 2026-07-01:** **ERLEDIGT 2026-07-01** — `docs/features/INDEX.md:126` + `docs/_shared/GLOSSARY.md:232` auf *runtime-verified* korrigiert; `just check-adoption` PASS 0.97; `just check-health` feature_adoption 0.87/1 baseline; check-health und check-adoption sind nun konsistent (keine widersprüchliche Handlungsanweisung).
**Priorität:** Mittel
**Bereich:** Governance / Release
**Kontext:** Docs (`CURRENT_STATE.md`, Feature-Index, ANAL-008) führen `character_voice` runtime adoption als governed debt; `just check-adoption` meldet runtime ✅ adopted ✅. Gleichzeitig bewertet `just check-health` Feature Adoption mit 0.50 wegen 121 baseline items, obwohl `check-adoption` nur 1 current item meldet.
**Akzeptanzkriterien:**
- [x] Geklärt ist, ob die aktuelle `character_voice` runtime evidence gültig ist.
- [x] `CURRENT_STATE.md`, Feature-Index/ANAL-008 und Adoption-Registry verwenden dieselbe Statussemantik.
- [x] Health-Scoring unterscheidet current debt von historischer baseline/resolved debt oder dokumentiert bewusst, warum baseline debt weiter score-relevant ist.
- [x] `just check-adoption` und `just check-health` liefern für Adoption keine widersprüchliche Handlungsanweisung.
**Geschätzter Aufwand:** S–M

### [AUFG-01-03] Editor-/Writing-Hotspots vor weiterer Feature-Anlagerung modularisieren
**Re-Check 2026-07-01:** **ERLEDIGT 2026-07-01** — `useTipTapEditorController` 400→115-Zeilen dünner Composer + 8 fokussierte Module (`useEditorInstance`, `useEditorAutosave`, `useGhostTextConfig`, `useGhostTextOnboardingAnchor`, `useRewriteActions`, `useRewriteFlow`, `useRewriteOperation`, `rewriteStream`; öffentliche API stabil); `WritingPipeline.generate` 206→118 + neues `_mode_dispatch.py` (Stage-Contracts dokumentiert); Modularisierung, keine Minifikation; Editor-/Writing-Tests + Architekturchecks grün (`check-frontend-size` 0 new, Frontend-Tests 602 passed).
**Priorität:** Mittel
**Bereich:** Architektur / Frontend / Core
**Kontext:** Graph-Hotspots `useTipTapEditorController` (335 Zeilen, degree 117) und `WritingPipeline.generate` (206 Zeilen) sind keine aktuellen RULE-04-Verstöße, aber zentrale Blast-Radius-Knoten.
**Akzeptanzkriterien:**
- [x] Für `TipTapEditorController` existiert ein Refactoring-Plan mit stabiler öffentlicher Hook-API und extrahierten Verantwortlichkeiten.
- [x] Für `WritingPipeline.generate` sind Stage-Verantwortlichkeiten/Contracts dokumentiert, bevor neue Writing-Features daran andocken.
- [x] Refactoring erfolgt durch Modularisierung, nicht durch Kommentar-/Whitespace-Reduktion.
- [x] Bestehende Editor-/Writing-Tests und Architekturchecks bleiben grün.
**Geschätzter Aufwand:** L

---

## Abschluss-Status (2026-07-01)

Die Review-01-Remediation ist abgeschlossen. Alle drei Aufgaben sind **resolved**
(Implementation + Enforcement verifiziert durch die vollständige Platform-Validierung
am 2026-07-01 — siehe pro Aufgabe):

- **AUFG-01-01 (Retry-Settings):** ERLEDIGT — ADR-060 ✅ *Implemented* (Provider-Layer-Transport-Retry; false user surface entfernt; `with_retry`/`RetryConfig` retired, 0 Caller; Matrix-Split). `check-configuration-matrix` PASS (26 Einträge).
- **AUFG-01-02 (`character_voice`):** ERLEDIGT — INDEX.md + GLOSSARY.md auf runtime-verified korrigiert; `check-adoption` PASS 0.97; `check-health` feature_adoption 0.87/1; beide konsistent.
- **AUFG-01-03 / AUFG-01-08 (Editor-/Writing-Hotspots):** ERLEDIGT — `useTipTapEditorController` 400→115 + 8 Module; `WritingPipeline.generate` 206→118 + `_mode_dispatch.py` (Stage-4-Contract dokumentiert); öffentliche API stabil; Modularisierung, keine Minifikation.

**Governing decisions:** ADR-060 ✅ *Implemented* (Retry-Reklassifizierung). ADR-061 ✅ *Implemented* (Matrix-Effect-Integrity-Hardening, Prävention P1+P2; Commit `817a3643`). ADR-062 ✅ *Implemented* (Governance-Drift Phase-2 Status-SSOT + Review→Registry-Linking, Prävention P3+P5; Commit `6b2ef523`). P4 (Health↔Adoption-Reconcile) bewusst als `accepted_enhancement` zurückgestellt (weitgehend selbst-korrigiert, Teilmenge von P3); P6 in ADR-061s P1 (graph-groundeter Pfad) integriert.

**Validierung 2026-07-01 (alle Gates grün):** `check-architecture` (0 new), `check-python-size`
/`check-frontend-size` (0 new), `check-streaming`, `check-ai-ux`, `check-prompts-strict`,
`check-locale-sync`, `validate-i18n.ts`, `check-configuration-matrix` (26/26),
`check-adoption` (0.97), `check-health` (0.93), `pyright` (0 errors), `ruff` (clean),
`pytest tests/unit` (8616 passed), RULE-17 Contract-Tests (35 passed), Frontend-Tests
editor/settings/i18n (602 passed).
