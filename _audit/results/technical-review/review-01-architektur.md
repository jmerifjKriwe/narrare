# Review 01 – Architektur & Code-Qualität

> **Voraussetzung:** Lies zuerst `_audit/results/technical-review/review-00-kontext.md` und stelle sicher,
> dass er vollständig ausgefüllt ist. Referenziere die dort dokumentierten Pfade und den Tech-Stack.
> Sollte `_audit/results/technical-review/review-00-kontext.md` nicht existieren, erstelle ihn
> zunächst auf Basis von `_audit/review-prompts/technical-review-prompts/review-00-kontext.md`
>
> **Routing:** Führe diesen Prompt mit `NarrarePlatformSpecialist` aus.
>
> **Ausgabe:** Schreibe das Ergebnis nach `_audit/results/technical-review/review-01-architektur.md`.
> Sei kritisch. Bewerte jeden Abschnitt mit der Skala aus dem Kontext-Dokument.

---

> **Methodik-Hinweis:** Evidenz wurde graph-first erhoben (`code-review-graph` MCP,
> gebaut/frisch: 26.940 Knoten, 193.137 Kanten, Risiko low). Da der Graph 0 Embeddings
> hat, wurde `semantic_search` nicht genutzt; stattdessen `query_graph`, `find_large_functions`,
> `get_hub_nodes`, `get_bridge_nodes` sowie gezielte Read/Grep-Checks. Alle Qualitäts-Tore
> wurden live nachvollzogen: `just check` (9/9 grün), `just check-architecture`,
> `just check-streaming`, `just check-locale-sync`, `just check-adoption`, `just check-ai-ux`,
> `just check-python-size`, `just check-frontend-size` sowie das Frontend-Test
> `i18n-namespace-registry.test.ts`. `codebase-memory-mcp` war laut Vorgabe nicht indiziert.

---

## 1. Gesamt-Architektur & Regel-Prüfung

**Regel-Prüfung:**

`/check-constraints` bzw. `just check-architecture` wurde ausgeführt:
`✅ Architecture constraints OK (1984 files checked, 16 approved exception(s))` plus
`check_exception_baseline.py`: 11 current / 11 baseline / 0 new / 0 resolved (kein Wachstum).
`check_prompt_surface_contract.py`: OK. Alle Ausnahmen sind in `pyproject.toml
[tool.narrare.architecture.exceptions]` registriert und in `CONSTRAINTS.md` §7 gespiegelt
(10 eindeutige Ausnahmen + Inline-`# narrare: allow`-Kommentare an jeder Verletzungsstelle).

Explizite Prüfung der jüngeren Narrare-Regeln (jeweils PASS/VIOLATION + Referenz):

| Regel | Status | Evidenz |
|---|---|---|
| **RULE-01b** (Agents/ModelRegistry, kein direktes Provider-Import/HTTP) | ✅ PASS | `check_architecture.py` AST-Import + Instantiierungs- + URL-Scan grün. 6 aktive genehmigte Ausnahmen (`core/llm/embedding_providers.py`, `core/memory/mem0_client.py`, `core/planning/remap.py`, `core/wiki/agent.py`, `core/wiki/agent_chapter.py`, `apps/api/setup/provider_service.py`) — alle mit Inline-`# narrare: allow-agent reason=...`. Kein `import openai`/`anthropic` außerhalb `core/llm/`, keine direkten Provider-HTTP-Calls. |
| **RULE-02a** (Prompt-Content-Kategorien: Capability/Cascade/Dynamic) | ✅ PASS | `check_architecture.py` Capability-f-string-Scan grün; `check_prompt_surface_contract.py` OK; Adoption-Score 0.97 (alle Intents adopted/static/runtime ✅, `just check-adoption`). Inline-Fallback-Baseline bei 0 ratcheted. **Graubereich-Beobachtung** siehe §6: mem0-Extraktionsprompts in `core/memory/mem0_client.py` (mem0-Config, nicht Narrare-Agent-Prompt) — grenzwertig, nicht als Verletzung gezählt. |
| **RULE-14** (Model-Änderung braucht Alembic-Migration) | ✅ PASS | 30 Migrationen (`apps/api/alembic/versions/0001`–`0030`) vorhanden; Integration-Tests laufen gegen echte Alembic-Migrationen (nicht `create_all()`). Cross-Table-Check als Regeltext dokumentiert. |
| **RULE-15** (proxy.ts statt middleware.ts) | ✅ PASS | `packages/web/proxy.ts` existiert; kein `middleware.ts` unter `packages/web/**` (file-existence-Scan). `just check-architecture` file-scan grün. |
| **RULE-16** (i18n namespace registration) | ✅ PASS (mit Doku-Drift, s. §4) | `i18n-namespace-registry.test.ts` ✅ (1 Test, 77 ms). 13 Namespaces in `request.ts` registriert, je 13 Dateien in en/de/fr. |
| **RULE-17** (API-Frontend-Contract-Konsistenz) | ✅ PASS | `tests/unit/api/test_prompt_contract.py` + `tests/unit/api/test_generation_router_contract.py` vorhanden und grün; `just check` Frontend Types: 0 errors. |
| **RULE-18 / 18b** (keine hardcodierte Router-Konfig / Configuration-Effect) | ✅ PASS | 1 genehmigte RULE-18-Ausnahme (`apps/api/narrare/memory/suggestion_identity.py` — gepinnte Krypto-Konstante, CR-AUFG-07-24). RULE-18b Adoption-Matrix CI-validiert; `check-adoption` Overall PASS (0.97). |
| **RULE-19** (SessionDep statt bare AsyncSession) | ✅ PASS | 1 genehmigte Ausnahme (`apps/api/narrare/metrics/router.py` Health-Check, platform-review-01). Alle `dependencies.py`-Factories nutzen `SessionDep`. |
| **RULE-20** (keine Half-Implementations / Streaming-Compliance) | ✅ PASS | `just check-streaming`: 14 SSE-Endpoints, 14/14 nutzen `connectSSE` im Frontend; Ratchet 0/0. Keine REST-only-AI-Features. |
| **RULE-22** (Cross-Feature Coherence Gate) | ✅ PASS | `packages/core/narrare_core/context/integration_contracts.py` (400 Zeilen) definiert KB-Consumer-Contracts (ADR-050 P1-B); ADR-049/050-Checker sind CI-blockierend. |

**Architektur-Analyse:**

- **Muster:** Geschichtete Clean-/Hexagonal-Hybride-Architektur mit strikter Schichtentrennung.
  Router (Präsentation) → Service (Business-Logik) → Repository (Persistenz) → DB, mit
  `packages/core/` als domänenlogischer Kern ohne HTTP/DB-Abhängigkeiten. Adapter
  (LLM-Gateway, mem0, Redis, pgvector, SMTP, Event-Bus) sind hinter dedizierten Modulen
  gekapselt (RULE-08).
- **Schichtentrennung:** Konsequent eingehalten. Verifiziert an `writing/router.py`
  (thin, delegiert sofort an `WritingService`, 123 Zeilen), `chat/chat_service.py`
  (implementiert `ChatServiceProtocol` aus `core/contracts`). Kein SQL in Services, kein
  Business-Logik in Routern.
- **Domänen- vs. Infrastruktur- vs. Präsentationstrennung:** Klar. `core/` = reine Domäne
  (kein `fastapi`/`sqlalchemy`-Import), `apps/api/` = Service + HTTP, `packages/web/` =
  Frontend. Dependency-Richtung eine-way (RULE-07): `core/` importiert nie aus `apps/`.
- **Abhängigkeitsrichtung / Zirkuläre Abhängigkeiten:** Eine-way, keine Zirkel (graph:
  Risiko low; `get_bridge_nodes` zeigt nur Test-Knoten als Chokepoints, kein
  Produktions-Zirkel). Hub-Knoten sind erwartungsgemäß `fetchApi` (Frontend-API-Core),
  `upgrade` (Alembic 0001, 132 ausgehende Kanten = Schema-Setup), `useAIOperation`,
  `KBSessionFieldList` — alles legitime Zentren.
- **Größte/komplexeste Module:** `apps/api/narrare/settings/` ist der komplexeste
  Domain-Ordner (Subpaket `token_limits/` + 6+ Services: `user_providers_service`,
  `project_ai_settings_service`, `user_ai_settings_service`, `custom_tone_service`,
  `model_routing_resolver`, `token_profiles`). Wohl modularisiert, aber hohe kognitive Last.
- **God-Classes/Modules:** Keine klassische God-Class. Die größten *nicht-Test*-Dateien
  sind Daten/Contract-Dateien an der harten Grenze: `core/llm/intents.py` (400) und
  `core/context/integration_contracts.py` (400) — beide exakt am Hard-Limit (vgl. §7).
- **Neue Module ohne Contract:** Nicht festgestellt. Jeder Service hat einen Protocol
  (`contracts.py`/`_types.py`), z.B. `auth/contracts.py`, `chapters/contracts.py`,
  `chat` über `narrare_core.chat.contracts.ChatServiceProtocol`. Cross-Feature-Contracts
  in `integration_contracts.py`.

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐⭐`
**Befunde:** Die Architektur-Verfassung (23 RULE-XX, maschinell erzwungen via `check_architecture.py`
in pre-commit + CI) ist vorbildlich umgesetzt und durchgesetzt: 1.984 Dateien geprüft, 0 echte
Verletzungen, 16 genehmigte Ausnahmen (alle mit ADR/Reason + Inline-Kommentar + Ratchet-Gate
gegen Wachstum). Alle 9 Qualitäts-Tore (`just check`) grün — Architecture, Lint, Typecheck
(0 Fehler), Security, Model Registry, Prompts, Frontend Lint, i18n Validation, Frontend Types
(0 Fehler). Dependency-Richtung strikt eine-way, keine Zirkel, kein Business-Logik in Routern.
Der einzige Abzug verbleibt bei dokumentierten Detail-Drifts (CONSTRAINTS-Pfad vs. Realität,
§4) und zwei Dateien exakt am Hard-Limit (§7) — beides kein Architektur-Defekt, verhindert
aber "kein Handlungsbedarf" in absoluter Lesart. Dennoch: für ein Projekt dieser Größe mit
vollständiger maschineller Durchsetzung ist dies eine ⭐⭐⭐⭐⭐-Bewertung.

---

## 2. Service Layer

**Analysiere:**

- **Existiert ein expliziter Service Layer?** Ja. Jeder Domain-Ordner unter
  `apps/api/narrare/*/` enthält Service-Datei(en): `auth/service.py`, `chapters/service.py`,
  `kb/service.py` (+ `graph_service.py`), `novels/service.py`, `volumes/service.py`,
  `templates/service.py`, `setup/service.py`, `memory/service.py`, `prompts/service.py`,
  `wiki/service.py`, `planning/service.py`, `embeddings/service.py`, `writing/service.py`
  (+ `suggest_service.py`), `chat/chat_service.py`, `settings/` (mehrere `*_service.py` +
  `token_limits/service.py`). Konsistente `service.py`-/`<name>_service.py`-Namenskonvention
  (beide RULE-06-konform).
- **Konsistente Nutzung durch alle Einstiegspunkte?**
  - **API:** ✅ Ja — verifiziert an `writing/router.py` (jede Route delegiert sofort an
    `service = await get_writing_service(...); return await service.<method>(...)`, 123
    Zeilen, 0 Business-Logik). `metrics/router.py` ist die einzige genehmigte Ausnahme
    (Health-Check mit direktem DB-Ping, RULE-19 #15).
  - **WebUI:** ✅ Ja (indirekt) — Frontend ruft ausschließlich die REST/SSE-API auf
    (`lib/api/core.ts::fetchApi` ist der zentrale Hub, 140 eingehende Kanten). WebUI ruft
    nie `core/` direkt auf (korrekt per RULE-12: WebUI ist Client der Service-Layer-via-API).
  - **MCP / A2A / CLI:** Nicht implementiert (review-00: ADAPTER-001/002 „Planned, Not
    Implemented", blockiert durch Q-001/Q-002). Kein Service-Layer-Mißbrauch möglich.
    Architektonisch vorbereitet: Services haben Protocol-Contracts (RULE-03), sodass
    zukünftige Adapter dieselben Services ohne Anpassung aufrufen können.
- **Business-Logik in Routern/CLI/MCP?** Nein. `writing/router.py` dokumentiert explizit
  „Thin delegation layer (RULE-06): every route immediately delegates to WritingService.
  No business logic lives here." Validierung erfolgt via Pydantic-Schemas (`schemas.py`)
  + Service; keine SQL-Queries in Routern (außer genehmigter Health-Check).
- **Stateless vs. stateful?** Stateless. Services erhalten Dependencies via DI
  (`Depends(...)`, Factories in `dependencies*.py`/`deps.py`). Kein Instanz-Zustand über
  injizierte Repos/Registries hinaus. DB-Sessions via `SessionDep` (RULE-19).

**Konkrete Prüfung:** Keine direkten DB-Zugriffe in Routern (außer genehmigte Ausnahme).
Keine duplizierte Validierungslogik — Pydantic-Schemas zentral in `schemas.py`. Service-Layer
ist Single Source of Business-Logik. Hub-Analyse bestätigt: Produktions-Call-Zentrum ist
`fetchApi` (Frontend→API-Grenze), nicht ein verteiltes Logik-Konglomerat.

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐⭐`
**Befunde:** Exemplarischer, konsistenter Service Layer. Dünne Router, die sofort delegieren;
Services mit Protocol-Contracts (RULE-03); stateless via DI; Repository-Pattern für DB-Zugriff.
Die beiden implementierten Einstiegspunkte (API, WebUI) nutzen den Service Layer korrekt.
Da MCP/A2A/CLI nicht existieren, ist die „alle Einstiegspunkte"-Prüfung auf 2/4 faktisch
limitiert — aber die Contract-Vorbereitung (RULE-03 Protocols) stellt sicher, dass zukünftige
Adapter denselben Service Layer nutzen werden, ohne Duplikation.

---

## 3. Code-Duplikate zwischen API, CLI, MCP und WebUI

**Analysiere:**

- **Duplizierte Funktionen über Einstiegspunkte:** Praktisch keine. Da nur **2 von 4**
  Einstiegspunkten implementiert sind (API + WebUI; CLI/MCP/A2A fehlen), gibt es keine
  Multi-Entry-Point-Duplikation. WebUI delegiert an API, API delegiert an Service Layer —
  keine parallele Geschäftslogik.
- **Copy-Paste, der in den Service Layer gehört:** Keiner festgestellt. Geteilte Kernlogik
  ist korrekt in `packages/core/` gekapselt (z.B. `narrare_core.chat.chat_service_core` wird
  von `chat/chat_service.py` importiert, nicht dupliziert). Frontend-API-Calls sind thin
  (`fetchApi`-Wrapper), keine Logik-Duplikation.
- **Feature-Gap-Matrix:** Die „Lücken" sind *geplante Roadmap-Adapter* (blockiert durch
  Q-001/Q-002), keine versehentlich fehlenden Funktionen:

| Funktion | CLI | API | MCP | WebUI |
|---|---|---|---|---|
| Writing-Generierung (Draft/Outline/Continue/Suggest/Co-Author/Rewrite/Extend/Style-Variants/Story-Suggest) | ✗ (nicht impl.) | ✓ (`writing/router*.py`, 9 Router) | ✗ (nicht impl., ADAPTER-001) | ✓ (SSE via `generation-streams.ts`/`suggest.ts`/`coauthor.ts`) |
| KB-CRUD + Graph + Worldbuilding + Enhance/Improve/Merge | ✗ | ✓ (`kb/router*.py`) | ✗ | ✓ (`lib/api/kb.ts`) |
| Analyse (Beta-Reader, POV, Coreference, Consistency, Character-Voice, Voice-Check, Readability, Sentiment) | ✗ | ✓ (`analysis/router*.py`) | ✗ | ✓ (`analysis/*-stream.ts`) |
| Chat (Agent-basiert, SSE) | ✗ | ✓ (`chat/router.py`) | ✗ | ✓ (`api/chat.ts`) |
| Planning (Timeline/Storyboard/Character-Arc) | ✗ | ✓ (`planning/router*.py`) | ✗ | ✓ (`api/timeline.ts`) |
| Memory/Preferences (mem0) | ✗ | ✓ (`memory/router.py`) | ✗ | ✓ (via Settings) |
| Settings (AI-Providers/Models/Token-Limits/Tones/Prompts) | ✗ | ✓ (`settings/router*.py`) | ✗ | ✓ (Settings-Views) |
| Auth (Login/Register/Refresh) | ✗ | ✓ (`auth/router*.py`) | ✗ | ✓ (`(auth)/`) |

**Empfehlung:** Der aktuelle Zustand ist architektonisch gesund (keine Duplikation, weil
Single-Sourcing über Service Layer). Da CLI/MCP/A2A noch nicht existieren, ist das
strukturelle Verhinderungsmittel bereits vorhanden: RULE-12 (Service Layer = einzige
öffentliche API) + RULE-03 (Protocol-Contracts pro Service) bedeuten, dass zukünftige
Adapter *dieselben* Services aufrufen. Wenn ADAPTER-001/002 gebaut werden (nach Q-001/Q-002-
Klärung), müssen sie `apps/mcp/`/`apps/a2a/` als reine Adapter anlegen, die existierende
Services injiziert bekommen — keine Logik-Duplikation. Ein Contract-Test-Suite zwischen
Service-Protocol und Adapter-Aufruf (wie `test_prompt_contract.py` für RULE-17) würde dies
zusätzlich absichern, sobald ein zweiter Client existiert.

**Bewertung:** ⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** Keine Code-Duplikation vorhanden (nur 2/4 Einstiegspunkte implementiert). Die
Architektur (RULE-12 + RULE-03 Contracts) ist vorbereitet, um Duplikation beim Hinzufügen
von MCP/A2A/CLI strukturell zu verhindern. Die Bewertung berücksichtigt, dass die
Feature-Gap-Matrix zu 50% aus „nicht implementiert"-Einträgen besteht — dies ist eine
governed Roadmap-Lücke (Q-001/Q-002), kein Qualitätsdefizit, verhindert aber die Höchstnote,
da die Multi-Entry-Point-Disziplin noch nicht im Feld bewiesen ist.

---

## 4. i18n-Implementierung

**Analysiere:**

- **Framework/Muster:** `next-intl` v4 (`^4.13.1`). Server-side Config in
  `packages/web/lib/i18n/request.ts` (`getRequestConfig`), Locale-Auflösung via Cookie
  (`NEXT_LOCALE`) → `requestLocale` → Default `en`. Routing in `lib/i18n/routing.ts`.
  3 Locales: `en`, `de`, `fr`.
- **Strings externalisiert?** Ja, nahezu vollständig. Über 100 `useTranslations("X")`-Aufrufe
  gefunden (Namespaces: `studio`, `common`, `analysis`, `editor`, `generation`, `dashboard`,
  `auth`, `wizard`, `settings`, `settings-ai`, `settings-appearance`, `errors`, `timeline`).
  Hartcodierte UI-Strings im Frontend-Produktionscode sind die Ausnahme (Grep fand nur
  Test-Dateien mit Literalen und `toaster.tsx`/`search-input.tsx` — Marginale). Backend
  liefert strukturierte `{detail, code}`-Errors (Codes, nicht übersetzt — korrekt: Frontend
  übersetzt Fehlercodes, Backend ist locale-agnostisch).
- **i18n-Struktur konsistent über Einstiegspunkte?** Backend = locale-agnostisch (Fehlercodes).
  API-Responses = strukturierte JSON mit stabilen Feldnamen (RULE-17). Frontend = next-intl
  mit registrierten Namespaces. Konsistent.
- **Sprachen & Abdeckung:** en/de/fr, jeweils 13 Namespace-Dateien (paritätisch in
  `packages/i18n/messages/{locale}/`). `just check-locale-sync`: 43/43 Prompt-Gruppen
  SYNCED, 0 drifted. UI-Namespace-Vollständigkeit via `i18n-namespace-registry.test.ts`
  durchgesetzt.
- **RULE-16 (Namespace-Registrierung):** ✅ PASS — Test grün. Alle 13 `useTranslations`-Namespaces
  sind in `request.ts` registriert UND haben JSON-Dateien in allen 3 Locales.
- **RULE-17 (Backend-Schema == Frontend-Typ):** ✅ PASS — `test_prompt_contract.py` +
  `test_generation_router_contract.py` grün; Frontend-Types: 0 Fehler (`just check`).

**Dokumentations-Drift (realer Befund):** `CONSTRAINTS.md` RULE-16 dokumentiert die
Locale-Dateipfade als `packages/web/messages/{locale}/{ns}.json` — dieser Pfad **existiert
nicht** (`packages/web/messages/` ist nicht vorhanden). Die tatsächlichen Dateien liegen in
`packages/i18n/messages/{locale}/{ns}.json` (importiert via
`../../../i18n/messages/${locale}/${ns}.json` in `request.ts`). Die `i18n-namespace-registry.test.ts`
prüft den korrekten Pfad (daher grün), aber die Regel-Dokumentation ist inaccurate. Dies ist
ein Doc-Drift, kein Code-Defekt — verstößt aber gegen das „documented = implemented"-Prinzip
(architectural-discipline §7): die verfassunggebende Datei nennt einen falschen Pfad.

**Bewertung:** ⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** Solide next-intl-Implementierung mit maschinell durchgesetzter Namespace-Parität
(RULE-16 ✅, RULE-17 ✅, Locale-Sync 43/43). Backend korrekt locale-agnostisch. Abzug für den
Dokumentations-Drift in `CONSTRAINTS.md` RULE-16 (Pfad `packages/web/messages/` ≠ Realität
`packages/i18n/messages/`) — die SSOT-Regeldatei ist an dieser Stelle inaccurate, was künftige
Mitwirkende verwirren und automatisierte Pfad-Checker (die sich auf den dokumentierten Pfad
verlassen) fehlschlagen lassen könnte.

---

## 5. API-Timeout- und Fehlerbehandlung

**Analysiere:**

- **Timeout-Mechanismen (Retries/Backoff/Circuit-Breaker):**
  - **Transport-Retry (governed, ADR-060):** Provider-SDK-Level Retry via
    `core/llm/_transport_retry.py` — `TRANSPORT_MAX_RETRIES_DEFAULT=2` (parity mit
    OpenAI/Anthropic/Groq-SDK-Defaults), Operator-Override via Env
    `NARRARE_LLM_TRANSPORT_MAX_RETRIES`. Bewusst *kein* User/Project-Surface (verhindert
    False-Control; ehem. `retry_max_attempts`/`retry_base_delay` entfernt). Gilt einheitlich
    für `ModelRegistry.run()` UND `.stream()` (inkl. Connection/First-Token-Phase). Test:
    `tests/unit/core/llm/test_transport_retry.py`.
  - **Circuit-Breaker:** Nicht vorhanden. Provider-SDK-Backoff ist einziger Retry-Mechanismus.
    Für ein local-first Single-User-Produkt vertretbar, aber bei Provider-Ausfällen gibt es
    keine globale Schutzschaltung.
  - **Rate-Limiting:** `pyrate-limiter` (`>=4.0,<5`) pro Endpoint-Gruppe (z.B.
    `AI_WRITE_LIMITER` in `rate_limits.py`).
- **Timeouts konfigurierbar vs. hardcodiert?** Transport-Retry = operator-governed (Env).
  Explizite HTTP-Timeouts liegen beim Provider-SDK (pydantic-ai/httpx-Defaults). Keine
  hardcodierten Service-Timeouts gefunden.
- **Partielle Fehler / langsame AI-API:** Streaming via `agent.run_stream()`; Final-Chunk
  trägt Usage-Daten (`gateway.py:263-279`). Usage-Limits via `usage_limits` an Agent durchgereicht.
- **Streaming-Abbruch-Handling:** ADR-052/053 (WebSocket Session Stop/Recovery + Lifecycle)
  implementiert. SSE-Streams nutzen `connectSSE` (`lib/api/streaming.ts`) mit AbortController
  (Frontend). `useAIOperation`-Hook (ADR-043) kapselt Cancel/Error/Loading.
- **Zentrale Fehlerbehandlung:** ✅ Vorhanden in `apps/api/narrare/_app/main.py`:
  `@app.exception_handler(NarrareError)` mapt Domain-Errors (NotFoundError→404,
  ForbiddenError→403, ConflictError→409, AuthenticationError→401, ValidationError→422,
  Default→400) auf strukturierte `{detail, code}`-JSON mit structlog-Logging.
  `@app.exception_handler(Exception)` als Catch-All → 500 + `exc_info=True`-Logging. Kein
  Silent-Pass auf Top-Level.
- **Einheitliches Logging:** `RequestLoggingMiddleware` loggt jeden Request (Dauer, Status,
  `request_id`, `trace_id`, `span_id` via structlog-Contextvars). OTel-Integration
  (`telemetry.py`).
- **Stille Fehler (RULE-11):** `check_architecture.py` bare-except-Scan = grün. 2 spezifische
  `except ...: pass` gefunden (beide *nicht* bare `except`, daher regelkonform):
  - `_app/lifespan.py:297` — `except ImportError: pass` (optionaler TaskIQ-Broker-Shutdown;
    akzeptabel, könnte `logger.debug` fügen).
  - `core/wiki/prompt_loader.py:71` — `except (ModuleNotFoundError, FileNotFoundError, OSError): pass`
    mit anschließendem EN-Fallback (Cascade-Pattern; `OSError`-Schlucken könnte reale
    IO-Fehler verdecken — verbesserungswürdig).
- **RULE-13 (Streaming & Nicht-Streaming gleiche Signatur):** ⚠️ **Graubereich.** Die Regel
  fordert eine einzelne Methode `async def run(self, ..., stream: bool = False) ->
  LLMResult | AsyncIterator[str]`. `ModelRegistry` bietet stattdessen *zwei separate Methoden*:
  `run()` (nicht-streaming, Zeile 142) und `stream()` (streaming, Zeile 217). Das entspricht
  nicht dem wörtlichen RULE-13-Signatur-Vorbild, ist aber funktional äquivalent (beide nutzen
  denselben `get_model`/`build_runtime_model_settings`-Pfad). Entweder RULE-13-Text an die
  realisierte Zwei-Methoden-Architektur anpassen (ADR) oder Signaturen vereinheitlichen.

**Bewertung:** ⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** Solide, zentralisierte Fehlerbehandlung (Domain-Error-Mapping + Catch-All +
structlog + OTel). Governed Transport-Retry (ADR-060) beseitigt eine frühere False-Control und
gilt einheitlich für run/stream. Streaming-Lifecycle (ADR-052/053) und `connectSSE`-Compliance
(RULE-20: 14/14) sind vorbildlich. Abzüge: (1) RULE-13-Signatur-Vorbild wird nicht wörtlich
erfüllt (zwei Methoden statt einer `stream: bool`-Signatur) — needs reconciliation; (2) kein
Circuit-Breaker (nur SDK-Backoff); (3) `prompt_loader.py` schluckt `OSError` ohne Debug-Log.

---

## 6. mem0 / memU – Implementierung

**Analysiere:**

- **Integration:** mem0 (`mem0ai` 2.0.11, ADR-033) ist *ausschließlich* in
  `packages/core/narrare_core/memory/mem0_client.py` importiert (RULE-08 ✓ — „This module
  is the ONLY place mem0 is imported"). Dies ist die genehmigte RULE-01b-Ausnahme #2
  (mem0's `AsyncMemory` braucht eigenen LLM-Client für interne Extraktion).
- **Speichern/Abrufen/Invalidieren:**
  - **Speichern:** pgvector-Vector-Store (via `db_url` in `_build_mem0_config` →
    `vector_store: {provider: pgvector}`) — local-first in der eigenen Postgres-DB des Nutzers.
  - **Abrufen:** über `core/memory/preference_service.py` + `feedback_service.py`
    (PreferenceAnalysis / Feedback-Pipeline).
  - **Invalidierung:** Nicht explizit dokumentiert. mem0 verwaltet eigenen Lifecycle;
    `NullMemoryClient` als Degradation.
- **Memory-Logik gekapselt?** Ja — Service-Layer-Wrapper in `apps/api/narrare/memory/service.py`,
  Kernlogik in `core/memory/`. Konsistent über Einstiegspunkte (nur API+WebUI vorhanden).
- **Konsistenzprobleme?** Keine festgestellt (Single-Source `mem0_client.py`).
- **Datenschutz:** Local-first — Memories in eigener pgvector-DB des Nutzers; keine
  Cloud-Abhängigkeit außer dem LLM-Provider selbst. `NullMemoryClient`-Fallback, wenn mem0
  nicht installiert / Embeddings deaktiviert / Erzeugung fehlschlägt (graceful degradation ✓).
- **Provider/Modell aus Settings vs. Hardcoding:**
  - ✅ Provider/API-Key/Base-URL kommen via DI (`create_memory_client(provider=..., api_key=...)`).
  - ⚠️ **Default-Modelle hardcodiert:** `_PROVIDER_DEFAULT_MODELS` (Zeile 28-33) mapt Provider
    → Modellname hartkodiert (`anthropic→claude-haiku-4-20250414`, `openai→gpt-4.1-nano`,
    `ollama→llama3.2:3b`, `zai→glm-4-flash`), Fallback `_FALLBACK_MODEL="gpt-4.1-nano"`.
    Diese sind bewusst kleine/günstige mem0-interne Extraktionsmodelle (nicht nutzerseitig),
    aber nicht aus der Settings-Cascade bezogen. Vertretbar als Defaults, aber ein
    potenzielles Drift-Risiko, wenn sich Modell-IDs ändern.
  - ✅ `memory_model`-Override möglich (von Caller aus Settings).
- **⚠️ RULE-02-Graubereich (Extraktionsprompts in `core/memory/`):** `_WRITING_PREFERENCE_PROMPTS`
  (Zeile 43-68) enthält sprachspezifische Extraktions-Anweisungs-Strings (en/de/fr) als
  Modulkonstanten in `core/memory/mem0_client.py`. Diese werden als `custom_instructions` an
  mem0's Config übergeben, nicht an einen Narrare-Agenten. Dennoch sind es *Prompt-Strings*,
  die außerhalb `core/prompts/` leben. RULE-02b grenzt dies nicht explizit ein (mem0-Config ist
  keine Narrare-Prompt-Auflösung), aber für Konsistenz sollten diese entweder nach
  `core/prompts/_bundled/memory/` wandern oder als genehmigte Ausnahme dokumentiert werden.

**Bewertung:** ⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** mem0 ist korrekt gekapselt (einzige Import-Stelle, RULE-08), mit eleganter
4-Tier-Embedding-Cascade (OpenAI → provider-native → local sentence-transformers →
NullMemoryClient) und local-first pgvector-Speicherung (Datenschutz ✓). Abzüge: (1) Default-
Memory-Modelle hartkodiert in `_PROVIDER_DEFAULT_MODELS` (nicht Settings-Cascade; gerechtfertigt
für mem0-interne Modelle, aber Drift-Risiko); (2) Extraktions-Prompt-Strings als Modulkonstanten
in `core/memory/` — RULE-02/RULE-02b-Graubereich, der entweder nach `core/prompts/` migriert
oder als genehmigte Ausnahme dokumentiert werden sollte; (3) keine explizite Memory-Invalidierungs-
Strategie dokumentiert.

---

## 7. Refactoring-Kandidaten

**Analysiere:** Top-5 Refactoring-Stellen, begründet durch objektive Evidenz
(`find_large_functions`, File-Size-Gate, Regel-Graubereiche):

| Priorität | Datei/Modul | Problem | Empfohlene Lösung |
|---|---|---|---|
| 1 | `packages/core/narrare_core/memory/mem0_client.py` (375 Zeilen) | **RULE-02/RULE-02b-Graubereich:** `_WRITING_PREFERENCE_PROMPTS` (en/de/fr, Zeile 43-68) sind Prompt-Strings in `core/memory/`, nicht `core/prompts/`. `_PROVIDER_DEFAULT_MODELS` (Zeile 28-33) hardcodiert Modell-IDs. Beides ist für mem0-intern vertretbar, aber inkonsistent mit der Prompt-Pfad-Verfassung (RULE-02b). | Extraktionsprompts nach `core/prompts/_bundled/memory/{locale}/system.md` migrieren (über `PromptComposer`/Cascade) ODER als genehmigte `# narrare: allow-prompt-path reason="mem0-internal config"`-Ausnahme in `pyproject.toml` registrieren. Default-Modelle in Settings-Cascade oder `core/llm/`-Default-Tabelle verschieben. |
| 2 | `packages/core/narrare_core/context/integration_contracts.py` (400 Zeilen) | **Exakt am RULE-04 Hard-Limit** (400). Definiert sämtliche KB-Cross-Feature-Contracts (ADR-050 P1-B: KB↔Planning/Timeline/Storyboard/Chapters/Consistency). Die nächste Contract-Ergänzung (ADR-050 P1-C/D, CONS-003) drückt die Datei über das Limit → Build-Fehler. | Präventiv nach Consumer-Domain aufteilen: z.B. `integration_contracts/__init__.py` + `_kb_lifecycle.py` + `_planning_consumer.py` + `_chapters_consumer.py`. Vor dem nächsten Cross-Feature-Contract-PR. |
| 3 | `packages/core/narrare_core/llm/intents.py` (400 Zeilen) | **Exakt am RULE-04 Hard-Limit** (400). Vermischt `LLMIntent`-Enum, `MODEL_ROUTING`-Tabelle und Intent-Metadaten. Hub-Charakter (viele Services importieren Intents). | Präventiv aufteilen: `_enums.py` (`LLMIntent`), `_routing.py` (`MODEL_ROUTING`), `_metadata.py`. Reduziert auch Blast-Radius bei Intent-Änderungen. |
| 4 | `docs/_shared/CONSTRAINTS.md` RULE-16 (Dokumentation) | **Doc-Drift:** Dokumentiert Locale-Pfade als `packages/web/messages/{locale}/`, tatsächlicher Pfad ist `packages/i18n/messages/{locale}/`. Verfassungsdokument inaccurate — verletzt „documented = implemented" (architectural-discipline §7). | CONSTRAINTS.md RULE-16 Pfad-Beispiele auf `packages/i18n/messages/{locale}/{ns}.json` korrigieren. `just check-ssot` prüft CURRENT_STATE-Claims — auf Doc-vs-Code-Pfad-Parität erweitern. |
| 5 | `packages/core/narrare_core/llm/gateway.py` (281 Zeilen) + RULE-13 | **RULE-13-Signatur-Reconciliation:** Regel fordert `run(self, ..., stream: bool=False) -> LLMResult | AsyncIterator[str]`; Realität sind zwei Methoden `run()` + `stream()`. Entweder ist die Zwei-Methoden-Architektur korrekt (dann RULE-13-Text via ADR anpassen) oder Signaturen vereinheitlichen. | Klärung: ADR schreiben, das die Zwei-Methoden-Signatur (`run` für synchron, `stream` für AsyncIterator) als Standard deklariert, und RULE-13-Text in CONSTRAINTS.md entsprechend aktualisieren. Verhindert zukünftige Verwirrung bei Reviewern. |

---

## Gesamtbewertung Architektur & Code-Qualität

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Vorherige Bewertung:** _keine (Erst-Audit)_ | **Trend:** _➡️ Erst-Audit (kein Vergleich)_
**Zusammenfassung:** Narrare besitzt eine vorbildlich durchgesetzte, maschinell erzwungene
Clean-/Hexagonal-Architektur: alle 23 RULE-XX-Verfassungsregeln werden via `check_architecture.py`
(pre-commit + CI) geprüft, alle 9 Qualitäts-Tore sind grün (Architecture/Lint/Typecheck/Security/
Model-Registry/Prompts/Frontend-Lint/i18n/Frontend-Types je 0 Fehler), 0 echte Verletzungen bei
16/10 sauber registrierten + ratcheted Ausnahmen, Coverage-Badge 92%. Schichtentrennung ist
strikt (dünne Router → Service → Repository), Dependency-Richtung eine-way, keine Zirkel,
kein Business-Logik in Routern, Service-Layer mit Protocol-Contracts (RULE-03) konsistent
durch alle implementierten Einstiegspunkte genutzt. Die Abwertung von ⭐⭐⭐⭐⭐ auf ⭐⭐⭐⭐
erfolgt ausschließlich aufgrund nachgewiesener Detail-Defizite, die das
„documented = implemented"-Prinzip tangieren: ein CONSTRAINTS.md-Pfad-Drift (RULE-16), eine
RULE-13-Signatur-Diskrepanz, zwei Dateien exakt am Hard-Limit (pr forthcoming build-breaks)
sowie ein mem0-Prompt-Graubereich (§6). Keiner dieser Punkte ist ein Architektur-Defekt — sie
sind aufräumbare Konsistenz-Lücken in einem ansonsten herausragend disziplinierten System.

---

## Aufgaben

### [AUFG-01-01] CONSTRAINTS.md RULE-16 Locale-Pfad-Korrektur (Doc-Drift)
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — Pfad in CONSTRAINTS/guides korrigiert + neuer CI-blockierender `ssot_locale_path_checks`-Checker ratchet-locked.
**Priorität:** Niedrig
**Bereich:** Architektur
**Kontext:** `docs/_shared/CONSTRAINTS.md` RULE-16 dokumentiert die i18n-Locale-Dateipfade als `packages/web/messages/{locale}/{ns}.json`. Dieser Pfad existiert nicht — die tatsächlichen Dateien liegen in `packages/i18n/messages/{locale}/{ns}.json` (importiert via `packages/web/lib/i18n/request.ts`: `../../../i18n/messages/${locale}/${ns}.json`). Die verfassunggebende SSOT-Datei ist an dieser Stelle inaccurate, was Mitwirkende verwirrt und das „documented = implemented"-Prinzip (architectural-discipline §7) verletzt. Der Code funktioniert korrekt (`i18n-namespace-registry.test.ts` ist grün); nur die Dokumentation driftet.
**Akzeptanzkriterien:**
- [x] CONSTRAINTS.md RULE-16: alle Pfad-Beispiele von `packages/web/messages/{locale}/` auf `packages/i18n/messages/{locale}/` korrigiert
- [x] Prüfung, ob weitere Stellen in CONSTRAINTS.md / coding-standards.md denselben falschen Pfad nennen, und ggf. korrigiert (gefunden + korrigiert in `docs/development/how-to-add-an-agent.md` L608/L698, `docs/mvp/mvp-plan.md` L665)
- [x] `just check-architecture` bleibt grün
- [x] Optional: `check-ssot` um Locale-Pfad-Parität (dokumentiert vs. `request.ts`-Import) erweitern, um künftigen Drift zu verhindern — umgesetzt als `ssot_locale_path_checks.py`

**Exit evidence (Implementation + Enforcement):**
- **Implementation:** Staler Pfad `packages/web/messages/` → `packages/i18n/messages/` korrigiert in `docs/_shared/CONSTRAINTS.md` (RULE-16 L740–742, L936), `docs/development/how-to-add-an-agent.md` (L608, L698), `docs/mvp/mvp-plan.md` (L665; zusätzlich monolithic→namespaced korrigiert). Commit `a927e706`.
- **ADR:** ADR-013 geprüft — korrekt und selbstkonsistent (es ist das Relocation-ADR; seine `packages/web/messages/`-Referenzen sind historischer Context + abgelehnte Option A). Keine ADR-Aktion nötig.
- **Enforcement:** Neuer Checker `scripts/doc_drift/ssot_locale_path_checks.py` (3 kritische Assertions: CONSTRAINTS darf den stalen Pfad nicht enthalten / muss den kanonischen Pfad enthalten / `request.ts`-Import-Parität), eingebunden in `scripts/check_doc_drift.py` (CI-blockierend, ci.yml `architecture`-Job). Unit-Tests: `tests/unit/scripts/test_ssot_locale_path_checks.py` (8 Tests). Fails-on-revert nachgewiesen. Commit `ad328f65`.
- **Außerhalb des Scopes (nicht als resolved behauptet, nur dokumentiert):** ADR-043 L834 trägt einen defekten historischen `rg`-Befehl (immutable ADR, braucht Supersession-Notiz — Architektur-Entscheidung, außerhalb Scope); `scripts/checks/ai_operation_inventory.yaml` L526 führt weiterhin den stalen Pfad (separater Code/Inventory-Drift, außerhalb Scope).
**Geschätzter Aufwand:** S

### [AUFG-01-02] mem0-Extraktionsprompts: RULE-02b-Klärung
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — ADR-064 klärt RULE-02b-Scope; governed Exception registriert (pyproject + CONSTRAINTS §7 #17) + baseline-ratcheted + Regressionstest.
**Priorität:** Mittel
**Bereich:** Architektur / AI
**Kontext:** `packages/core/narrare_core/memory/mem0_client.py` enthält `_WRITING_PREFERENCE_PROMPTS` (en/de/fr, Zeile 43-68) als Modulkonstanten — Prompt-Strings, die als `custom_instructions` an mem0's Config übergeben werden. Diese leben in `core/memory/`, nicht in `core/prompts/`, was ein RULE-02b-Graubereich ist (Prompt-Pfad-Compliance gilt für Narrare-Prompt-Auflösung; mem0-Config ist formal keine solche). Um Konsistenz mit der Prompt-Pfad-Verfassung herzustellen und künftige Ausweitung zu verhindern, muss eine explizite Entscheidung getroffen werden. Zusätzlich enthält `_PROVIDER_DEFAULT_MODELS` (Zeile 28-33) hardcodierte mem0-interne Modell-IDs.
**Akzeptanzkriterien:**
- [x] Architektur-Entscheidung dokumentiert: Option (b) gewählt — governed `# narrare: allow-prompt-path`-Ausnahme registriert in `pyproject.toml [tool.narrare.architecture.exceptions]` + `docs/_shared/CONSTRAINTS.md` §7 (Row #17) (ADR-064 begründet, dass RULE-02b genuin nicht greift: `custom_instructions` ist ein opaque Config-String für eine 3rd-Party-LLM-Intern-Aufruf, erreicht nie `PromptComposer`/Agenten)
- [ ] `_PROVIDER_DEFAULT_MODELS`: prüfen, ob diese in Settings-Cascade oder `core/llm/`-Default-Tabelle gehören; ggf. verschieben oder als governed default mit Owner/Begründung klassifizieren (RULE-18b) → deferred: Klassifizierung als governed RULE-18b-Default (owner=core/memory, nicht nutzerseitiges Extraktionsmodell) in ADR-064 dokumentiert; die formale RULE-18b-adoption-matrix-Zeile konnte nicht geschrieben werden, da repo-weit keine `configuration-adoption-matrix.yaml` existiert
- [x] `just check-architecture` + `check_exception_baseline` bleiben grün (12/12 baseline, kein Wachstum)
- [x] Bei Option (b): Inline-`# narrare: allow-prompt-path reason="mem0 config string, not Narrare prompt path (ADR-064)"`-Kommentar an jeder `_WRITING_PREFERENCE_PROMPTS`-Verwendung (`mem0_client.py` L43/L145/L199)

**Exit evidence (Implementation + Enforcement):**
- **Decision/ADR:** ADR-064 `docs/architecture/decisions/ADR-064-mem0-prompt-path-scope-and-memory-defaults.md` — RULE-02b greift genuin nicht (mem0 `custom_instructions` ist ein opaque Config-String für den internen LLM-Aufruf einer 3rd-Party-Library, erreicht nie `PromptComposer`/Agenten); defensiv als **governed Exception** registriert, um die Scope-Grenze maschinenlesbar zu verankern und Wachstum einzurasten. `_PROVIDER_DEFAULT_MODELS` als **governed RULE-18b-Default** klassifiziert (owner=core/memory, keine nutzerseitigen Extraktionsmodelle).
- **Implementation:** Exception registriert in `pyproject.toml [tool.narrare.architecture.exceptions]` + `docs/_shared/CONSTRAINTS.md` §7 (Row #17) + `scripts/architecture/ai-gate-baseline.json` Fingerprint (Commit `ea35942c`); Inline-Marker an `packages/core/narrare_core/memory/mem0_client.py` L43/L145/L199 (Commit `71603a79`).
- **Enforcement:** `check_exception_baseline.py` No-Growth-Ratchet — 12/12, CI-blockierend + pre-commit (auf allen Commits grün gehalten). Regressionstest `tests/unit/core/memory/test_mem0_prompt_path_scope.py` (2 Tests: realer `check_prompt_registry_access` flaggt nichts auf `mem0_client.py` + pyproject-Eintrag existiert). Commit `71603a79`.
- **Deferred:** RULE-18b-adoption-matrix-Zeile für `_PROVIDER_DEFAULT_MODELS` hat keine Zieldatei — keine `configuration-adoption-matrix.yaml` existiert repo-weit; Klassifizierung stattdessen in ADR-064 festgehalten.
**Geschätzter Aufwand:** M

### [AUFG-01-03] Präventive Aufteilung: integration_contracts.py (am Hard-Limit)
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — in Consumer-Domain-Paket `integration_contracts/` aufgeteilt; alle Dateien < 250; `just check-python-size` (RULE-04 Hard-Limit) beweist es CI-blockierend.
**Priorität:** Mittel
**Bereich:** Architektur
**Kontext:** `packages/core/narrare_core/context/integration_contracts.py` liegt bei exakt 400 Zeilen — dem RULE-04 Hard-Limit für Python-Module. Die Datei definiert sämtliche KB-Cross-Feature-Contracts (ADR-050 P1-B) für KB↔Planning/Timeline/Storyboard/Chapters/Consistency. Die nächste Contract-Ergänzung (ADR-050 P1-C/D oder CONS-003 Multi-Step-Workflows) wird die Datei über das Limit drücken → Build-Fehler (RULE-04 Hard-Limit = Build-Failure). Präventive Modularisierung ist jetzt günstig, später (mit Backward-Compat-Zwang) teuer.
**Akzeptanzkriterien:**
- [x] `integration_contracts.py` aufgeteilt in ein `integration_contracts/`-Paket: `__init__.py` (69, Re-Exports aller 10 öffentlichen Namen) + `_vocab.py` (58) + `_kb_lifecycle.py` (250) + `_planning_consumer.py` (85) + `_chapters_consumer.py` (50)
- [x] Alle Importe (`from narrare_core.context.integration_contracts import ...`) bleiben funktional (öffentliche API über `__init__.py` — alle 10 öffentlichen Namen re-exportiert, Git detektierte den Split als Rename)
- [x] Keine Datei > 250 Zeilen (Soft-Target) nach Aufteilung (alle Dateien nun < 250)
- [x] `just check-architecture` + `check-python-size` bleiben grün; bestehende Tests grün (alle integration_contracts-Consumer-Tests über apps/api + tests)

**Exit evidence (Implementation + Enforcement):**
- **Implementation:** `packages/core/narrare_core/context/integration_contracts.py` (400) → Paket `integration_contracts/`: `__init__.py` (69, re-exportiert alle 10 öffentlichen Namen), `_vocab.py` (58), `_kb_lifecycle.py` (250), `_planning_consumer.py` (85), `_chapters_consumer.py` (50). Öffentliche API unverändert. Commit `d7ee7420`.
- **Enforcement:** `just check-python-size` (RULE-04 Hard-Limit, CI-blockierend + pre-commit) beweist jede Datei ≤ 400 (alle nun < 250 Soft-Target). Alle abhängigen Tests grün (integration_contracts-Consumer über apps/api + tests). Git detektierte den Split als Rename.
**Geschätzter Aufwand:** M

### [AUFG-01-04] RULE-13-Signatur-Reconciliation (run/stream)
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — ADR-065 deklariert die Zwei-Methoden-Signatur zum Standard; RULE-13-Text reconciled; Contract-Regressionstest verifiziert die Form via `inspect`.
**Priorität:** Niedrig
**Bereich:** Architektur
**Kontext:** RULE-13 (CONSTRAINTS.md) fordert für Streaming-LLM-Operationen eine einzelne Methode `async def run(self, ..., stream: bool = False) -> LLMResult | AsyncIterator[str]`. Die reale Implementierung in `packages/core/narrare_core/llm/gateway.py` bietet zwei separate Methoden: `run()` (nicht-streaming) und `stream()` (AsyncIterator). Beide nutzen denselben `get_model`/`build_runtime_model_settings`-Pfad, sind also funktional äquivalent zum Regelziel, aber die Signatur passt nicht zum dokumentierten Vorbild. Diese Diskrepanz kann Reviewer verwirren und ist eine Latent-Inconsistency zwischen Verfassung und Code.
**Akzeptanzkriterien:**
- [x] Architektur-Entscheidung: Option (a) gewählt — ADR-065 deklariert die Zwei-Methoden-Signatur (`run()` Coroutine → `LLMResult` + `stream()` AsyncGen → `AsyncIterator[StreamChunk]`) zum Standard; Vereinheitlichung abgelehnt (würde einen Union-Return erzwingen → RULE-23-Gefahr über 5 Call-Sites)
- [x] Bei (a): RULE-13-Text in CONSTRAINTS.md aktualisiert (§5 Text + Zwei-Methoden-Code-Beispiel + Begründung + §6 Enforcement-Tabelle RULE-13-Zeile)
- [x] Bei (b): alle Caller (`gateway.py` 142/217, Services) angepasst; Tests grün → entfällt: Option (a) gewählt (ADR-065), keine Signatur-Vereinheitlichung nötig; `gateway.py`-Signaturen passen bereits zum neuen Standard (keine Code-Änderung)
- [x] `just check-architecture` + Typecheck grün

**Exit evidence (Implementation + Enforcement):**
- **Decision/ADR:** ADR-065 `docs/architecture/decisions/ADR-065-rule-13-two-method-run-stream-contract.md` — Zwei-Methoden-`run()` (Coroutine → `LLMResult`) + `stream()` (AsyncGen → `AsyncIterator[StreamChunk]`) als Standard deklariert; RULE-13-Text an die Realität reconciled. Vereinheitigung abgelehnt (würde Union-Return erzwingen → RULE-23-Gefahr über 5 Call-Sites).
- **Implementation:** `docs/_shared/CONSTRAINTS.md` §5 RULE-13 neu geschrieben (Text + Zwei-Methoden-Code-Beispiel + Begründung) + §6 Enforcement-Tabelle RULE-13-Zeile ergänzt. Commit `c8f6c704`. Keine `gateway.py`-Änderung (Signaturen passen bereits zum neuen Standard).
- **Enforcement:** Regressionstest `tests/unit/core/llm/test_model_registry.py` → `TestModelRegistryContractShape` (3 Tests via `inspect`: beide Methoden vorhanden; `run` `iscoroutinefunction` & keine AsyncGen; `stream` `isasyncgenfunction` mit `AsyncIterator[StreamChunk]`-Annotation). CI-blockierend unter `test-unit`. Commit `072df3cd`.
**Geschätzter Aufwand:** S (bei ADR/Doku) / M (bei Signatur-Vereinheitlichung)

### [AUFG-01-05] Präventive Aufteilung: llm/intents.py (am Hard-Limit)
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — `intents.py` (400) → `intents/`-Paket (11 Dateien, alle < 250); `INTENT_DOCS` AST-verifiziert identisch gehalten. Hinweis: die Review-Prämisse (Mix aus Enum + `MODEL_ROUTING` + Metadaten) war veraltet — siehe Exit evidence.
**Priorität:** Niedrig
**Bereich:** Architektur
**Kontext:** `packages/core/narrare_core/llm/intents.py` liegt bei exakt 400 Zeilen (RULE-04 Hard-Limit). Die Datei vereint das `LLMIntent`-Enum, die `MODEL_ROUTING`-Tabelle und Intent-Metadaten und ist ein Hub (viele Services importieren Intents). Der nächste Intent oder Routing-Eintrag (z.B. für CONS-003/WRITE-013 Multi-Step-Workflows) drückt die Datei über das Limit → Build-Fehler.
**Akzeptanzkriterien:**
- [x] `intents.py` aufgeteilt — in ein `intents/`-Paket (11 Dateien): `__init__.py` (30, re-exportiert `LLMIntent` + `INTENT_DOCS`) + `_enums.py` (149, `LLMIntent` StrEnum mit knappen Einzeiler-Scope-Docstrings, ~250 Zeilen Headroom) + `_docs.py` (44, Aggregator) + 7 kategoriale `_docs_*.py`-Dateien. → Prämissen-Korrektur: das vorgeschlagene `_routing.py`/`_metadata.py`-Layout entfiel, weil `MODEL_ROUTING`/`ModelConfig`/`get_model_config()` bereits entfernt waren (siehe Exit evidence)
- [x] Öffentliche API (`from narrare_core.llm.intents import LLMIntent`) bleibt erhalten (Architektur-Test bestätigt den Re-Export)
- [x] Keine Datei > 250 Zeilen (Soft-Target) nach Aufteilung (`just check-python-size` beweist alle < 250)
- [x] `just check-architecture` + `check-python-size` + Typecheck grün; bestehende Tests grün

**Exit evidence (Implementation + Enforcement):**
- **Prämissen-Korrektur (wichtig):** Die Review (§7 + Aufgaben-Kontext) behauptete, `intents.py` mische `LLMIntent`-Enum + `MODEL_ROUTING`-Tabelle + Intent-Metadaten. Das war **veraltet** — das Modul-eigene Docstring dokumentiert, dass `MODEL_ROUTING`/`get_model_config()`/`ModelConfig` entfernt und durch Runtime-Auflösung ersetzt wurden. Die Datei war ein einzelner docstring-lastiger `LLMIntent`-StrEnum (400 Zeilen = ~30 Member + ~370 Zeilen pro-Intent-Prosa). Die Review-Prämisse traf also nicht zu; der Split wurde dennoch zur Einhaltung des RULE-04-Limits durchgeführt.
- **Implementation:** `packages/core/narrare_core/llm/intents.py` (400) → Paket `intents/` (11 Dateien): `__init__.py` (30), `_enums.py` (149), `_docs.py` (44) + 7 kategoriale `_docs_*.py`-Dateien. `INTENT_DOCS` hält alle 28 Einträge **wortwörtlich** (AST-verifiziert identisch zu den Original-Docstrings — nichts entfernt, RULE-04 gewahrt). Verifiziert: kein Code liest Member-`__doc__`. Öffentliche API unverändert. Commit `1729f2ba`.
- **Enforcement:** `just check-python-size` (RULE-04 Hard-Limit, CI-blockierend + pre-commit) beweist alle Dateien < 250; Architektur-Test, der `from narrare_core.llm.intents import LLMIntent` assertiert, besteht weiterhin via Re-Export. Alle Tests grün.
**Geschätzter Aufwand:** S

### [AUFG-01-06] prompt_loader.py: OSError loggen statt silent pass + except-Tuple normalisieren
**Re-Check 2026-07-08:** **ERLEDIGT 2026-07-08** — OSError wird via `structlog` `logger.debug(exc_info=True, …)` geloggt + Regressionstest (`capture_logs`) verifiziert Log + EN-Fallback.
**Priorität:** Niedrig
**Bereich:** Core / Qualität
**Kontext:** `packages/core/narrare_core/wiki/prompt_loader.py:71–72` fängt `(ModuleNotFoundError, FileNotFoundError, OSError)` mit `pass` ab. Das stumme Schlucken von `OSError` (Permission/Disk/Corruption) verdeckt reale IO-Fehler ohne jegliche Trace — ein RULE-11-Geist-Verstoß, den der bare-except-Scanner (`check_architecture.py`) nicht abfängt, weil er nur bare `except:` bzw. `except Exception: pass` prüft, nicht das Schlucken spezifischer Exception-Typen ohne Logging. L71 nutzt zudem `except A, B, C:` ohne Parenthesen (gültiges Python-3-Tuple-Expr, aber inkonsistent mit L87, das `except (…):` schreibt).
**Akzeptanzkriterien:**
- [x] `OSError`-Zweig logged die Exception via `logger.debug(...)` (inkl. category/language/mode), statt stumm `pass` — `structlog` `logger.debug("bundled_prompt_load_failed_fallback_en", exc_info=True, category=…, language=…, mode=…)`; Verhalten identisch (fällt weiterhin zum EN-Fallback durch)
- [x] Except-Tuple mit Parenthesen normalisiert (`except (…):`) für Konsistenz mit L87 → ruff kanonische Form (Parens optional für non-binding except); Konsistenz wird vom Formatter erzwungen (L87 behält Parens nur, weil `as exc:` sie verlangt)
- [x] Regressionstest: ein provoziertes `OSError` wird geloggt (assert log record) UND der English-Fallback greift weiterhin — `tests/unit/core/wiki/test_prompt_loader.py` → `test_oserror_during_read_text_emits_debug_log_and_falls_back_to_en` (via `structlog.testing.capture_logs`)
- [x] `just check` + `just lint` + `just typecheck` + `just test-unit` grün

**Exit evidence (Implementation + Enforcement):**
- **Implementation:** `packages/core/narrare_core/wiki/prompt_loader.py` — stilles `except …: pass` ersetzt durch `structlog` `logger.debug("bundled_prompt_load_failed_fallback_en", exc_info=True, category=…, language=…, mode=…)`; Verhalten identisch (fällt weiterhin zum EN-Fallback durch). Commit `cbc4ac10`.
- **Enforcement:** Regressionstest `tests/unit/core/wiki/test_prompt_loader.py` → `test_oserror_during_read_text_emits_debug_log_and_falls_back_to_en` (via `structlog.testing.capture_logs`: assertet DEBUG-Record mit `exc_info`+Context emitted UND EN-Fallback returned UND keine Exception propagiert). CI-blockierend unter `test-unit`. Commit `cbc4ac10`.
- **Anmerkung zum Except-Tuple-Paren-Sub-Kriterium:** in ruffs kanonischer Komma-Form belassen — `ruff format` normalisiert non-binding `except (A,B,C):` → `except A,B,C:`; L87 behält Parens nur, weil `as exc:` sie erfordert. Die Codebase steht bereits in der kanonischen konsistenten Form des Formatters; Parens via `# fmt: skip` zu erzwingen wäre ein einmaliger Ausreißer, der gegen den Formatter arbeitet (ein Workaround) — abgelehnt. Sub-Kriterium `[x]` mit Inline-Hinweis `→ ruff kanonische Form (Parens optional für non-binding except); Konsistenz vom Formatter erzwungen`.
**Geschätzter Aufwand:** S

---

## Abschluss-Status

**Review-Ergebnis:** Alle 6 AUFG-Aufgaben (01-01 … 01-06) sind remediiert — jede mit
**Implementation + Enforcement** (finding-lifecycle §2 `✅ Resolved`), nicht bloß implementiert.

| AUFG | Status | Ein-Zeilen-Evidenz | Commits |
|---|---|---|---|
| 01-01 | ✅ Resolved (2026-07-08) | RULE-16-Pfad in CONSTRAINTS/guides korrigiert + neuer CI-blockierender `ssot_locale_path_checks.py`-Checker (ratchet-locked, 8 Unit-Tests) | `a927e706`, `ad328f65` |
| 01-02 | ✅ Resolved (2026-07-08) | ADR-064 klärt RULE-02b-Scope; governed Exception registriert (pyproject + CONSTRAINTS §7 #17) + `check_exception_baseline` 12/12 + Regressionstest | `ea35942c`, `71603a79` |
| 01-03 | ✅ Resolved (2026-07-08) | `integration_contracts.py` (400) → Consumer-Domain-Paket (alle < 250); `just check-python-size` (RULE-04) beweist es | `d7ee7420` |
| 01-04 | ✅ Resolved (2026-07-08) | ADR-065 deklariert Zwei-Methoden-`run`/`stream` zum Standard; RULE-13-Text reconciled; Contract-Regressionstest via `inspect` | `c8f6c704`, `072df3cd` |
| 01-05 | ✅ Resolved (2026-07-08) | `intents.py` (400) → `intents/`-Paket (11 Dateien, alle < 250); `INTENT_DOCS` AST-verifiziert identisch (Review-Prämisse korrigiert) | `1729f2ba` |
| 01-06 | ✅ Resolved (2026-07-08) | OSError via `structlog` `logger.debug(exc_info=True)` geloggt; Regressionstest (`capture_logs`) verifiziert Log + EN-Fallback | `cbc4ac10` |

**Hinzugefügte Präventionsmaßnahmen (gegen die Fehlerklasse, nicht nur den Einzelfall):**
- **Doc-Drift-Checker** `scripts/doc_drift/ssot_locale_path_checks.py` (CI-blockierend via `check_doc_drift.py`) — verhindert künftigen CONSTRAINTS↔`request.ts`-Pfad-Drift (AUFG-01-01).
- **Exception-Ratchet** `check_exception_baseline.py` no-growth (12/12, CI-blockierend + pre-commit) — rastet prompt-path-Ausnahmen ein und verhindert Graubereich-Wachstum (AUFG-01-02).
- **3 Regressionstests:** `test_mem0_prompt_path_scope.py` (AUFG-01-02), `TestModelRegistryContractShape` (AUFG-01-04), `test_oserror_during_read_text_emits_debug_log_and_falls_back_to_en` (AUFG-01-06) — alle CI-blockierend unter `test-unit`.
- **2 Size-Gate-bewiesene Splits:** `integration_contracts/` + `intents/` je via `just check-python-size` (RULE-04 Hard-Limit, CI-blockierend + pre-commit) bewiesen (AUFG-01-03, AUFG-01-05).
- **RULE-13-Contract-Test** verifiziert die Zwei-Methoden-Signatur-Form via `inspect` (AUFG-01-04).
- **2 ADRs** (ADR-064, ADR-065) verankern die mem0-prompt-path-Scope-Grenze bzw. die run/stream-Signatur als Standard.

**Phase-4 Gate-Ergebnisse (alle grün):**
- `just check`: 9/9 grün (Architecture, Lint, Typecheck 0 Fehler, Security, Model-Registry, Prompts, Frontend-Lint, i18n, Frontend-Types 0 Fehler).
- Typecheck: 0 Fehler.
- Tests: 8.779 Backend- + 2.476 Frontend-Tests grün.
- Exception-Baseline: 12 current / 12 baseline / 0 neu / 0 resolved (kein Wachstum).

**Explizit außerhalb des Scopes / deferred (nicht als resolved behauptet):**
- **ADR-043 L834** — defekter historischer `rg`-Befehl (immutable ADR, braucht Supersession-Notiz; Architektur-Entscheidung, außerhalb Scope dieses Reviews).
- **`scripts/checks/ai_operation_inventory.yaml` L526** — trägt weiterhin den stalen `packages/web/messages/`-Pfad (separater Code/Inventory-Drift, außerhalb Scope).
- **AUFG-01-02 RULE-18b-adoption-matrix-Zeile** für `_PROVIDER_DEFAULT_MODELS` — keine `configuration-adoption-matrix.yaml` existiert repo-weit; Klassifizierung stattdessen in ADR-064 festgehalten (deferred, nicht blockierend für die primäre RULE-02b-Auflösung).

**Gesamtaussage:** Die in der ⭐⭐⭐⭐⭐-Bewertung zitierten Detail-Drifts — RULE-16-Pfad-Drift, RULE-13-Signatur-Diskrepanz, zwei Dateien exakt am Hard-Limit (`integration_contracts.py`, `intents.py`), mem0-prompt-Graubereich (§6) und `prompt_loader.py` silent-failure — sind jeweils jetzt **implementiert + erzwungen**. Die Abwertungsgründe von ⭐⭐⭐⭐⭐ auf ⭐⭐⭐⭐ sind adressiert; kein `✅ Resolved`-Claim beruht auf einer der verbotenen Anti-Pattern (ADR-alone / template-exists / check-green-only / implemented-without-enforcement) aus finding-lifecycle §4.
