# Narrare – Projekt-Kontext für Reviews

> **Hinweis für die Projekt-AI:** Diese Datei ist der gemeinsame Ausgangspunkt für alle
> Review-Prompts (01–05). Fülle sie einmalig aus, bevor du die anderen Prompts ausführst.
> Alle nachfolgenden Review-Dateien referenzieren diesen Kontext.

---

## Aufgabe

Analysiere das Projekt und befülle die Abschnitte unten mit den tatsächlichen Werten aus
dem Repository. Sei präzise und vollständig – die anderen Review-Prompts bauen darauf auf.

---

## Projekt-Überblick

**Name:** Narrare
**Beschreibung:** AI-gestützte, kreative Schreibumgebung („AI-assisted creative writing environment") — local-first (lokal-first) und vollständig anpassbar. Romanautoren schreiben, bauen Welten (Worldbuilding), pflegen eine Knowledge Base (KB), planen (Outline, Character Arc, Timeline) und lassen sich von KI-Agents beim Generieren, Erweitern, Umschreiben, Analysieren (Beta Reader, Sentiment, Readability, POV, Coreference, Character Voice, Consistency) und beim Inline-Suggest/Co-Authoring unterstützen. KI-Aufrufe laufen über pydantic-ai-Agents (RULE-01b) und ein zentrales LLM-Gateway mit Intent-Routing; Prompts werden ausschließlich in `core/prompts/` gebaut (RULE-02/02a/02b). Modell/Provider ist über eine Settings-Cascade konfigurierbar (OpenAI, Anthropic, z.ai/GLM, OAI-kompatibel).
**Zielgruppe:** Romanautoren und kreative Schreiber, die KI-Unterstützung beim Schreiben, Weltbau und Plot-Management suchen.
**Aktueller Entwicklungsstand:** MVP abgeschlossen; **Phase 6 (Post-MVP) in Arbeit** (Stand `CURRENT_STATE.md` 2026-06-30). Phasen 0–5 (Repository Foundation, Core Infrastructure, API Foundation, Setup Wizard Backend, Frontend Foundation, Integration & Polish) sind alle ✅ COMPLETE. Phase 6 hat >70 Post-MVP-Workitems abgeschlossen, darunter WRITE-003/004/006/007/009/010, KB-002/003/005/006/007/009, ANAL-001–005/008, CONS-001, PLAN-004/006, WIKI-001, CHAT-001, INFRA-004/007/012/013, SET-005, ONBOARD-001, PROMPT-003, KEYBOARD-001 und die Remediation-Cycles CR-01–CR-08. Testumfang: ca. 8.341 Backend-Unit- + ~4.814 Core- + ~2.287/2.339 Frontend-Tests grün; README-Coverage-Badge 92 %; CI-Badge grün. AI Feature Freeze wurde 2026-06-03 unter ratcheted Governance aufgehoben. MCP- und A2A-Adapter sind laut `docs/features/INDEX.md` (ADAPTER-001/002) und README weiterhin „Planned, Not Implemented" (blockiert durch Q-001/Q-002). Governed Rest-Schulden: Inline-Fallback-Adoption-Baseline, strategische Deferrals (SET-006 Project Writing Profile, CONS-003/KB-011/WRITE-013 Multi-Step-Workflows).

---

## Verbindliche Review-Quellen

> Prüfe diese Quellen zuerst. Wenn sich ein Template und eine akzeptierte ADR widersprechen,
> gilt die neuere ADR bzw. `CONSTRAINTS.md`.

| Quelle | Zweck | Geprüft? |
|---|---|---|
| `docs/_shared/CONSTRAINTS.md` | RULE-XX Architekturverfassung | ✅ Ja — Verfassung mit 23 Kardinal-/Struktur-/Qualitäts-/Implementierungs-/Zukunftsregeln (RULE-01b–RULE-23 + Sub-Regeln 02a/02b/18b). Maschinell erzwungen via `scripts/check_architecture.py` (pre-commit + CI). Enthält §6 Enforcement-Summary, §7 Approved-Exceptions-Register (gespiegelt in `pyproject.toml [tool.narrare.architecture.exceptions]`, 10 aktive Ausnahmen), §8 SSOT-Hierarchie. |
| `docs/development/coding-standards.md` | Code-Standards | ✅ Ja — Python 3.14-Typisierung (`\|` statt `Union`, `type`/`Self`/`ParamSpec`), Naming-Konventionen, async/Result-Pattern, DI, SQLAlchemy-Pattern; TypeScript-Regeln (React, Tailwind v4, native `fetch`+`connectSSE`, i18n, RULE-15 `proxy.ts` nicht `middleware.ts`). 606 Zeilen. |
| `docs/development/testing-standards.md` | Test-Standards | ✅ Ja — 3-Level-Archite (`unit` < 5 s / `integration` realer DB+Redis, gemocktes LLM / `e2e` Playwright nur main), Fake-Klassen statt MagicMock (RULE-TEST-01), Coverage-Minima core 90 % / api 80 %, E2E-Muster (Playwright, `NARRARE_E2E_TEST=1`), Mutation-Testing-Scope. 1.353 Zeilen. |
| `docs/development/prompt-standards.md` | Prompt-Inhalt und Versionierung | ✅ Ja — Obligatorischer 9-Sektion-Prompt-Skeleton (Frontmatter `prompt_type/prompt_language/prompt_version`), Versionierungsregeln, System-Prompt-Konsistenz (ADR-019), Capabilities (ADR-026), Verweis auf `prompt-content-standards.md`. ADR-Bezug: 002/019/026/032/037. 744 Zeilen. |
| `docs/development/prompt-content-standards.md` | Maschinenprüfbare Prompt-Qualität | ✅ Ja — 8 verbindliche Elemente (Rolle, Output-Format, ≥4 Do-NOT, Injection-Defense via `USER_CONTENT_VARS`+Wrapper, Generated-Candidate-Boilerplate, Analysis-Evidence/False-Positive-Gates, Runtime-Input-Contract, Formality-Register DE/FR = Du/tu) + Quality-Checklist. Erzwungen via `check_prompt_structure.py --strict` + `prompt_governance_checks.py` + ADR-037-Manifest. |
| `docs/development/ui-principles.md` | Frontend/UI/AI-UX Regeln | ✅ Ja — 6 Design-Prinzipien, 3-Shell-Taxonomie (Dashboard/Wizard/Studio-Workspace), Design-Tokens (Light/Dark), §16 AI-Interaction-Compliance (`useAIOperation` ADR-043), Component-Konventionen. Stand 2026-07-05. 1.213 Zeilen. |
| `docs/development/deployment-guide.md` | CI/CD, Release, Deployment | ✅ Ja — Dev-Umgebung (`uv sync --frozen --all-packages --group dev --extra nlp`), Docker-Compose (PostgreSQL+pgvector+Redis), CI als einziger blockierender Setup/Architektur-Gate, Release-Image + GHCR + SBOM, Env-Variablen. 796 Zeilen. |
| Relevante ADRs | Architekturentscheidungen seit letztem Audit | ✅ Ja — `docs/architecture/decisions/INDEX.md` listet ADR-001–ADR-063 (ADR-039 ist eine Lücke: 038 → 040). Stichtag-relevante neuere/steuernde ADRs: ADR-046 (Prompt-Path-Compliance/RULE-02b), ADR-049 (Prompt-Surface-Identity/Path), ADR-050 (Cross-Feature Context Contracts), ADR-051 (Configuration-Effect-Adoption/RULE-18b), ADR-052/053 (WebSocket Session Stop/Recovery + Lifecycle), ADR-054 (Inline-Feature-Prompt-Debt-Migration), ADR-055/057 (Character Voice/Check Contracts), ADR-056 (Runtime-Evidence-Aware Commit Gate), ADR-059 (VRT + Design-System), ADR-060 (Retry False-Control), ADR-063 (Deterministic CI venv). Hinweis: INDEX markiert ADR-047/051/061/062 mit ⛔, während `CURRENT_STATE.md` z. T. „✅ Implemented/Accepted" nennt — Status-Diskrepanz beachten. |

---

## Technologie-Stack

> Versionsquellen: `pyproject.toml` (Root), `apps/api/pyproject.toml`, `packages/core/pyproject.toml`, `packages/web/package.json`, Root-`package.json`. TECH_STACK.md gibt Major-Version-Commitments aus; die Pins unten sind die tatsächlich installierten/manifestierten Versionen.

| Bereich | Technologie | Version |
|---|---|---|
| Backend Runtime | Python | `>=3.14` (Ruff `target-version = "py314"`) |
| Backend Framework | FastAPI | `0.139.0` |
| Backend ASGI | uvicorn[standard] | `0.50.0` |
| Datenbank ORM | SQLAlchemy (async) | `2.0.51` |
| DB Treiber | asyncpg | `0.31.0` |
| Migrationen | Alembic | `1.18.5` (0001–0030) |
| Vektorsuche | pgvector | `0.4.2` |
| Cache/Broker | Redis | `>=7.0.0,<9` |
| Hintergrund-Tasks | TaskIQ (+ taskiq-redis / taskiq-fastapi) | `0.12.4` / `1.2.3` / `0.5.0` |
| Validierung | Pydantic v2 / pydantic-settings | `2.13.4` / `2.14.2` |
| LLM-Agents | pydantic-ai-slim[openai,anthropic,google,groq] | `2.5.0` |
| Memory | mem0ai (ADR-033) | `2.0.11` |
| HTTP Client | httpx | `0.28.1` |
| Auth | PyJWT / argon2-cffi | `2.13.0` / `>=25.1.0` |
| Rate-Limiting | pyrate-limiter | `>=4.0,<5` |
| Logging | structlog | `26.1.0` |
| Observability | OpenTelemetry api/sdk/fastapi/otlp | `1.39.x` (<1.44.0) |
| Email | aiosmtplib | `5.1.2` |
| Templating | jinja2 | `3.1.6` |
| NLP (optional) | spaCy | `>=3.8` (`[nlp]` extra) |
| Embeddings (optional) | sentence-transformers | `>=3.0` (`[embeddings]` extra) |
| Frontend Runtime | Node.js | `>=24.0.0` |
| Package Manager | pnpm | `11.5.2` (Root-`packageManager`) |
| Frontend Framework | Next.js (App Router) | `16.2.10` |
| UI Runtime | React / react-dom | `19.2.7` |
| Editor | TipTap v3 (+ starter-kit, react, pm, …) | `^3.27.1` |
| Typing (FE) | TypeScript | `^6.0.3` |
| Styling | Tailwind CSS v4 | `^4.3.2` |
| Client State | Zustand | `5.0.14` |
| Server State | TanStack Query v5 | `^5.101.2` |
| i18n | next-intl | `^4.13.1` |
| Form/Validation | react-hook-form + zod | `^7.80.0` / `^4.4.3` |
| Charts | recharts | `^3.9.1` |
| Animation | motion (ex-Framer Motion) | `^12.42.2` |
| Edge-JWT | jose | `^6.2.3` |
| FE Linter/Formatter | Biome | `2.5.2` |
| FE Test | Vitest (+ @vitest/coverage-v8) | `^4.1.9` |
| FE E2E | Playwright | `^1.61.1` |
| Dev Python Lint | Ruff | `0.15.20` |
| Dev Type Check | pyright (strict) | `1.1.411` |
| Dev Python Test | pytest (+ asyncio 1.4.0 / cov 7.1.0) | `9.1.1` |
| Dev Security | bandit / pip-audit | `1.9.4` / `2.10.1` |
| Dev Mutation | mutmut | `3.6.0` |
| Dev AI Quality | pydantic-evals (ADR-032) | `2.5.0` |

---

## Aktuelle Kernregeln für alle Reviews

Dokumentiere hier kurz, welche Regeln im aktuellen Stand besonders review-relevant sind.

| Regel | Kurzinhalt | Review-Relevanz |
|---|---|---|
| RULE-01b | Agents/ModelRegistry statt direkte Provider/Agent-Instanzierung (`pydantic_ai.Agent` nur in `core/agents/`, Model-Klassen nur in `core/llm/`, keine direkten `openai`/`anthropic`-Imports/HTTP-Calls) | Höchste Relevanz für alle LLM/Agent-Reviews. 6 aktive genehmigte Ausnahmen (embedding_providers, mem0_client, planning/remap, wiki/agent*, llm/gateway, setup/provider_service). Checker: AST-Import- + Instantiierungs-Scan + URL-Scan. Bei LLM-bezogenen Diffs zuerst prüfen, ob Aufruf durch `NarrareAgent.run()`/Gateway erfolgt. |
| RULE-02/02a | Prompts in `core/prompts/`; Content-Kategorien: Capability (garantiert) / Cascade (anpassbar) / Dynamic Data (`@agent.instructions`/`for_run`) | Höchste Relevanz für Prompt- & Service-Reviews. Service darf nur Laufzeit-Input an `agent.run(prompt=...)` übergeben, keine Inline-System-/Task-Strings. Mode-1 (PromptComposer + intent + context_mode + governed template) ist der Standardpfad; ADR-054 hat Inline-Feature-Prompt-Baseline auf 0 gebracht. |
| RULE-03 | Contracts before implementation (Protocol in `contracts.py`/`_types.py` vor `service.py`); Cross-Feature-Integration-Contracts erforderlich | Jeder neue Service braucht vorherigen Protocol; Consumer-Feature muss Integrations-Contract bei geteilten Daten definieren (Änderungs-/Löschverhalten, erwartete Version). Direkt verknüpft mit RULE-22 Cross-Feature-Gate. |
| RULE-04/06 | Datei-Limits (Python 400/Soft 250; Router 150/80; Service 300/200; Agent 200/150; Test 400/300) + eine Verantwortung pro Datei (Router delegiert sofort, Service hat Logik, Repository nur SQL) | Modularisierung statt Kompression. Frontend-Legacy-Schulden sind auf 0 rasiert (53→0); Backend/Core weiter überwacht. Bei Review auf File-Size-Überschreitungen und Logik-im-Router prüfen. |
| RULE-10 | Tests sind nicht optional; Coverage core ≥90 %, api ≥80 %; Unit/Integration/E2E getrennt; Test-File-Spiegelung der Source-Struktur | Bei jedem neuen Service/Endpoint: zugehöriger Unit-/Integration-Test? Fakes statt MagicMock (RULE-TEST-01). Mutation-Testing-Scope core/prompts, core/writing, core/llm/intents.py. |
| RULE-14 | Model-Änderung braucht Alembic-Migration (in gleicher Task); Cross-Table-Check bei gemeinsamem Concern | Bei jedem `models.py`-Diff: zugehörige Migration 0001–0030 + Schema-Regression-Test? Motiviert durch früheren Setup-Wizard-Crash (`token_limit_profile` fehlte). |
| RULE-15 | Next.js Route Middleware nur `proxy.ts`, niemals `middleware.ts` (beide → harter Build-Fehler in Next.js 16+) | Frontend-Reviews: kein `middleware.ts` in `packages/web/**`. Vorhanden: `packages/web/proxy.ts` mit Header-Warnung; `prebuild`-Guard bricht ab, falls `middleware.ts` existiert. Checker: file-existence-Scan. |
| RULE-16/17 | i18n: jedes `useTranslations("X")` braucht Eintrag in `namespaces` (`lib/i18n/request.ts`) + `X.json` in en/de/fr; API-Frontend-Contract Konsistenz (Pydantic-Feldname == TS-Feldname, gleicher Commit) | Runtime-only-Fehlerquelle (rohe Keys statt Übersetzungen). Bei Schema-/Namespace-Änderungen Parität in allen 3 Locales + TS-Typ-Update prüfen. Tests: `i18n-namespace-registry.test.ts`, `validate-i18n.ts`, `test_prompt_contract.py`. |
| RULE-18/19 | Keine hardcoded Router-Konfig (Provider/Model/Keys via DI/Settings-Cascade); `SessionDep` (nicht bare `AsyncSession`) in `dependencies.py`-Factories | 1 genehmigte RULE-18-Ausnahme (`memory/suggestion_identity.py`), 1 RULE-19-Ausnahme (`metrics/router.py` Health-Check). RULE-18b (Configuration-Effect) fordert zusätzlich Runtime-Konsumenten + Regressions-Evidenz pro Setting. |
| RULE-20/22 | Keine Half-Implementations (komplett oder gar nicht; SSE nicht aufschieben); Cross-Feature Coherence Gate (Stage 2.5: geteilte Daten, Änderungs-/Lösch-Verhalten, Variablen-Registrierung, Kontext-Precedence) | „Documented ≠ Implemented" (Discipline §7). Cross-Feature-Abhängigkeiten (KB, Storyboard, Frontmatter, wiki, memory, settings) sind unsichtbar auf Feature-Ebene — ADR-050/049 checkers sind CI-blockierend. Bei AI-Feature-Reviews Streaming-Compliance + Coherence-Checkliste verlangen. |

---

## Einstiegspunkte & Zugriffs-Layer

> MCP und A2A sind **Roadmap-Adapter, nicht implementiert** (ADAPTER-001/002; README; blockiert durch Q-001/Q-002). Nur Service Layer ist implementierte öffentliche API (RULE-12).

- **CLI:** Keine dedizierte Narrare-CLI implementiert. Entwicklungs-/Task-Zugriff erfolgt über den `just`-Taskrunner (`justfile`: `just dev/dev-api/dev-frontend/dev-worker`, `just test/test-unit`, `just check/db-migrate/db-revision`). `scripts/` enthält Tooling-Checkskripte (kein produktiver CLI-Client). CLI ist ein geplanter 4. Client gemäß RULE-12, aber nicht gebaut.
- **API (REST/FastAPI):** `apps/api/narrare/_app/main.py` → `create_app()` erzeugt die FastAPI-App (`app = create_app()`), Lebenszyklus via `_app/lifespan.py`, Telemetrie via `_app/telemetry.py`, Middleware (CORS, `OriginValidationMiddleware`, `RequestLoggingMiddleware`), Domain-Error-Handler. Alle Domain-Router werden unter Prefix `/api/v1` registriert (20 Module: analysis, auth, chapters, chat, consistency, embeddings, events, generation, kb, memory, metrics, novels, planning, prompts, settings, setup, tasks, templates, volumes, writing, wiki). Health/Ready ohne Prefix (`/health`, `/ready`); Monitoring `/tasks/status`. Uvicorn-Server Port 8000.
- **MCP-Server:** **Nicht implementiert** (`apps/mcp/` existiert nicht; README vermerkt „planned; calls Service Layer when built"). Roadmap-Adapter gemäß RULE-12; blockiert durch Q-001 (MCP-Auth-Strategie, 🟡 Open). ADAPTER-001 spec = „Planned, Not Implemented".
- **WebUI:** `packages/web/` — Next.js 16 App Router. Root-Layout `packages/web/app/layout.tsx`; Route-Groups: `app/(auth)/`, `app/(studio)/` (mit `AuthGate` in `app/(studio)/layout.tsx`), 3 Shells (Dashboard `/`, Wizard `/wizard`, Studio-Workspace `/novel/[id]/**`). Route-Middleware ausschließlich über `packages/web/proxy.ts` (RULE-15). Editor mit TipTap v3 + SSE-Streaming via `lib/api/streaming.ts` (`connectSSE`). Dev-Server Port 3000.
- **A2A:** **Nicht implementiert** (`apps/a2a/` existiert nicht). Roadmap-Adapter gemäß RULE-12; blockiert durch Q-002 (A2A-Streaming-Anforderung, 🟡 Open). ADAPTER-002 spec = „Planned, Not Implemented".

---

## Review-Methodik

- Nutze zuerst die Code-Review-Graph MCP Tools (`minimal_context`, `semantic_search_nodes`, `query_graph`, `detect_changes`, `impact_radius`).
- Nutze Dateisystem-Tools nur gezielt, wenn der Graph die gesuchte Information nicht enthält.
- Führe Checks/Audits nur aus, wenn dieser Prompt aktiv als Audit ausgeführt wird; beim Review der Templates selbst keine Ergebnisdateien befüllen.

> **Audit-Beobachtung (graph-exploration):** Der `code-review-graph` ist gebaut und frisch
> (26.940 Knoten, 193.137 Kanten über 2.857 Dateien, Risiko low). Semantische Suchen nach
> Entry-Point-Knoten („FastAPI app main", „create_app lifespan", „Next.js app layout") lieferten
> jedoch **0 Treffer** — App-Factory (`main.py`) und Next.js-Layouts sind als Knoten unter diesen
> Queries nicht auffindbar. Entry-Points wurden daher ergänzend via Glob/Read verifiziert.
> `codebase-memory-mcp` ist laut Vorgabe **nicht** indiziert. Known Risk in `CURRENT_STATE.md`:
> „Code Knowledge Graph MCP intermittently unavailable" — Fallback auf Read/Glob/Grep.

---

## Verzeichnisstruktur (Top-Level)

```
narrare/
├── apps/
│   └── api/                  ← FastAPI-Backend (Python 3.14); Paketname `narrare`
│                                (apps/mcp und apps/a2a sind geplant, NICHT implementiert)
├── packages/
│   ├── core/                 ← Geteilte Domain-Logik (Paketname `narrare_core`) — 19 Submodule:
│   │                            agents, ai_invocation, analysis, cache, chat, context,
│   │                            embeddings, events, kb, llm, memory, nlp, planning, prompts,
│   │                            schemas, shared, templates, wiki, writing
│   ├── i18n/                 ← Übersetzungen (Paketname `narrare_i18n`)
│   └── web/                  ← Next.js 16 Frontend (App Router + TipTap v3)
├── docs/
│   ├── _shared/              — CONSTRAINTS.md (SSOT), TECH_STACK.md, GLOSSARY.md, CURRENT_STATE.md
│   ├── architecture/         — decisions/ (ADR-001–063, INDEX.md), questions/ (INDEX.md), governance/
│   ├── development/          — coding/testing/prompt/ui/deployment-Standards
│   ├── features/             — Feature-Spezifikationen (INDEX.md)
│   ├── mvp/                  — Produkt-Roadmap (Phasen 0–6 + Post-MVP)
│   └── reference/            — directory-structure, project-vision
├── scripts/                  ← Dev-Tooling + Checkers: check_architecture.py, check_adoption.py,
│                                check_system_health.py, check_prompt_structure.py,
│                                check_streaming_compliance.py, governance/, architecture/, adoption/,
│                                quality/, doc_drift/, probes/, run_checks.py, run_mutmut.py, …
├── tests/                    ← Test-Suite: unit/ (core, api), integration/, e2e/ (Playwright)
├── evals/                    ← Pydantic Evals — AI-Quality SSOT (ADR-032)
├── data/                     ← Dev-/Seed-Daten
├── _audit/                   ← Review-Prompts + Ergebnisse (dieses Audit)
├── _scratch/                 ← Scratch-Bereich (git-ignored-ähnlich)
├── .devcontainer/            ← Optionaler DevContainer-Overlay (ADR-029)
├── .github/workflows/        ← CI (blockierender Setup/Architektur-Gate), Release, Mutation-Testing
├── .evidence/                ← Invocation-Evidence (ADR-041/045, `.evidence/invocations.jsonl`)
├── .opencode/, .agents/      ← Agent-/Context-Konfiguration + extrahierte Standards/Skills
├── justfile                  ← Task-Runner (Dev/Test/Check/Migrate-Befehle)
├── pyproject.toml            ← Python-Workspace-Root (uv workspace: apps/api, packages/core, packages/i18n)
├── package.json              ← JS-Workspace-Root (packageManager pnpm@11.5.2)
├── pnpm-workspace.yaml       ← pnpm-Workspace
├── uv.lock / pnpm-lock.yaml  ← gesperrte Dependencies
├── Dockerfile                ← Release-Image
├── docker-compose.dev.yml / .prod.yml / .release.yml
├── README.md / CHANGELOG.md / LICENSE (MIT)
└── AGENTS.md                 ← Open-Code-Instruktionen (Orchestrator)
```

---

## Bekannte Probleme & offene Punkte (Stand Review)

> Quelle: `docs/architecture/questions/INDEX.md`, `docs/_shared/CURRENT_STATE.md` (Known Risks,
> Follow-up Debt). Nur real existierende Einträge — nichts erfunden.

| ID | Problem | Status | Priorität |
|---|---|---|---|
| Q-001 | MCP-Auth-Strategie (wie authentifiziert MCP gegen die API?) — blockiert `apps/mcp/` Adapter | 🟡 Open | Mittel (Post-MVP, blockiert ADAPTER-001) |
| Q-002 | A2A-Streaming-Anforderung (benötigt A2A-Protokoll Streaming?) — blockiert `apps/a2a/` Adapter | 🟡 Open | Mittel (Post-MVP, blockiert ADAPTER-002) |
| Q-011 | Distributions-Strategie für nicht-technische Nutzer (Zielgruppen-Positionierung, Post-MVP Distribution) | 🟡 Open | Mittel (Post-MVP) |
| ADR-039 | ADR-Nummern-Lücke: INDEX springt ADR-038 → ADR-040 (kein ADR-039 vorhanden) | Offen (Dokumentations-Lücke) | Niedrig |
| ADR-Status-Diskrepanz | `decisions/INDEX.md` markiert ADR-047, ADR-051, ADR-061, ADR-062 mit ⛔ (Superseded), während `CURRENT_STATE.md` teils „✅ Implemented/Accepted" nennt | Offen (Status-Inkonsistenz SSOT) | Mittel (Review-Relevanz: welcher Status gilt?) |
| Inline-Fallback-Adoption-Schuld | Einzige verbleibende Adoption-Debt-Klasse: registrierte Inline-Fallback-Baseline (ADR-045/056); `just check-adoption` = autoritative Quelle | Governed Debt (ratcheted) | Niedrig (governed, blockiert nur Wachstum) |
| Strategische Deferrals | SET-006 (Project Writing Profile), CONS-003/KB-011/WRITE-013 (Multi-Step-Workflows) bewusst außer Scope (INFRA-012 assessed complete) | Deferred (dokumentiert) | Niedrig |
| Graph-MCP-Verfügbarkeit | `code-review-graph` MCP zeitweise nicht verfügbar; Entry-Point-Knoten unter nativen Queries teils nicht auffindbar (0 Treffer) | Known Risk (CURRENT_STATE) | Mittel (verlust strukturellen Kontexts; Fallback Read/Glob/Grep) |
| TipTap v3 API-Drift | TipTap v3 API kann sich ändern → exakter Pin erforderlich | Known Risk (CURRENT_STATE) | Niedrig (Pin vorhanden: `^3.27.1`) |
| Python 3.14 fehlende Type-Stubs | Einige Drittanbieter ohne Stubs → `reportMissingTypeStubs`-False-Positives | Known Risk (CURRENT_STATE) | Niedrig (dokumentiert in pyproject.toml) |

> Zusätzlich gelöst (zur Vollständigkeit): Q-003–Q-010, Q-012–Q-014 sind ✅ Resolved (siehe
> `questions/INDEX.md`). Die CR-04-/CR-07-Follow-up-Debts sind laut `CURRENT_STATE.md` mit
> Implementation- + Enforcement-Evidenz geschlossen (FIND-009/010/011 resolved; `just check-ai-ux` = 0 Violations).

## Bewertungs-Skala (gilt für alle Review-Dateien)

Alle Reviews verwenden diese einheitliche Skala:

| Note | Bedeutung |
|---|---|
| ⭐⭐⭐⭐⭐ | Vorbildlich, kein Handlungsbedarf |
| ⭐⭐⭐⭐ | Gut, kleinere Verbesserungen möglich |
| ⭐⭐⭐ | Akzeptabel, deutliche Optimierungspotenziale |
| ⭐⭐ | Problematisch, baldiger Handlungsbedarf |
| ⭐ | Kritisch, sofortiger Handlungsbedarf |

---

## Ausgabe-Konvention für alle Reviews

Jede Review-Datei (01–05) endet mit einem Abschnitt `## Aufgaben` im folgenden Format,
damit die Ergebnisse direkt als AI-Aufgaben weiterverwendet werden können:

```markdown
## Aufgaben

### [AUFG-XX] Titel der Aufgabe
**Priorität:** Hoch / Mittel / Niedrig
**Bereich:** Architektur / Testing / AI / DX / Release
**Kontext:** Kurze Beschreibung, warum diese Aufgabe notwendig ist.
**Akzeptanzkriterien:**
- [ ] Kriterium 1
- [ ] Kriterium 2
**Geschätzter Aufwand:** S / M / L / XL
```
