# Narrare – Projekt-Kontext für Reviews

> Aktualisiert für Technical Review 00 am 2026-06-29. SSOT-Reihenfolge: `CONSTRAINTS.md` / `TECH_STACK.md` / akzeptierte ADRs vor abgeleiteten Dokumenten; `CURRENT_STATE.md` und `docs/features/INDEX.md` sind aktuelle Status-Snapshots, aber bei internen Widersprüchen konservativ gegen Code/ADR/CI prüfen.

---

## Projekt-Überblick

**Name:** Narrare
**Beschreibung:** AI-assisted creative writing environment — local-first, fully customizable (`README.md`).
**Zielgruppe:** Romanautoren und kreative Schreiber, die KI-Unterstützung beim Schreiben, Weltbau und Plot-Management suchen.
**Aktueller Entwicklungsstand:** Phasen 0–5 vollständig; Phase 6 / Post-MVP Features in Arbeit. `CURRENT_STATE.md` (2026-06-29) meldet u. a. ANAL-008 Character Voice Profiling + ADR-055 implementiert, ADR-054 Inline-Feature-Prompt-Debt-Migration abgeschlossen, INFRA-012/INFRA-007/PLAN-006/WRITE-009/ANAL-005 stabil. README-Coverage-Badge: 88%. `character_voice` Runtime-Adoption bleibt governed debt: static-verified, Runtime-Evidence pending CI/Integration.

---

## Verbindliche Review-Quellen

| Quelle | Zweck | Geprüft? |
|---|---|---|
| `docs/_shared/CONSTRAINTS.md` | RULE-XX Architekturverfassung | Ja — maßgeblich, 23 Regeln inkl. RULE-02b, RULE-18b, RULE-23; letzte Notiz 2026-06-24 |
| `docs/development/coding-standards.md` | Code-Standards | Ja — Python 3.14, async-first, DI, Repository-Pattern, Migration Discipline |
| `docs/development/testing-standards.md` | Test-Standards | Ja — 3 Testlevel, Fakes statt MagicMock, Cross-Layer Contract Tests, Config-Matrix Gate |
| `docs/development/prompt-standards.md` | Prompt-Inhalt und Versionierung | Ja — 9-teiliger Prompt-Skeleton, Kategorie-/Variablenregeln, XML-Wrapping, ADR-037/INFRA-012 |
| `docs/development/prompt-content-standards.md` | Maschinenprüfbare Prompt-Qualität | Ja — Role/Output/Do-NOT/Injection/Runtime-Input-Contract/Formality-Register |
| `docs/development/ui-principles.md` | Frontend/UI/AI-UX Regeln | Ja — Studio Layout, i18n, Tailwind v4 Tokens; AI-UX-Detailregeln zusätzlich über ADR-043/Governance prüfen |
| `docs/development/deployment-guide.md` | CI/CD, Release, Deployment | Ja — Operations-Anleitung geprüft; CI-Details gegen `.github/workflows/ci.yml` abgeglichen |
| Relevante ADRs | Architekturentscheidungen seit letztem Audit | Ja — ADR-044 bis ADR-055 besonders review-relevant; ADR-010/017/018 superseded; ADR-039 ist im Index nicht belegt |

---

## Technologie-Stack

| Bereich | Technologie | Version |
|---|---|---|
| Backend Runtime | Python | `>=3.14` |
| Backend API | FastAPI / Uvicorn | FastAPI 0.138.1, Uvicorn 0.49.0 |
| Datenbank | PostgreSQL + pgvector, SQLAlchemy async, asyncpg, Alembic | SQLAlchemy 2.0.51, asyncpg 0.31.0, Alembic 1.18.4, pgvector 0.4.2, CI image `pgvector/pgvector:pg17` |
| Cache/Broker | Redis + TaskIQ | Redis `>=7,<9`; CI/dev image `redis:8-alpine`; TaskIQ 0.12.4 / taskiq-redis 1.2.3 / taskiq-fastapi 0.5.0 |
| Python Package Manager | uv workspace | Workspace: `apps/api`, `packages/core`, `packages/i18n` |
| Python Validation/Config | Pydantic / pydantic-settings | Pydantic 2.13.4, pydantic-settings 2.14.2 |
| LLM Runtime | pydantic-ai slim | `pydantic-ai-slim[openai,anthropic,google,groq]` 2.0.0 |
| Memory | mem0 OSS | mem0ai 2.0.10 |
| Observability | structlog + OpenTelemetry | structlog 26.1.0; OTel API/SDK `>=1.39,<1.43`; Langfuse/Logfire nicht Core-Runtime |
| Security/Auth | PyJWT, argon2-cffi, pyrate-limiter | PyJWT 2.13.0, argon2-cffi `>=25.1.0`, pyrate-limiter `>=4,<5` |
| Frontend Runtime | Node.js / pnpm | Node `>=24`; root `packageManager`: pnpm 11.5.2; web engines allow pnpm `>=10` |
| Frontend | Next.js / React / TypeScript | Next 16.2.6, React 19.2.6, TypeScript 6.0.3 |
| Editor | TipTap | 3.26.0 |
| Frontend State/Data | TanStack Query, Zustand | TanStack Query 5.101.0, Zustand 5.0.14 |
| Styling/UI | Tailwind CSS v4, shadcn/base-ui/Radix, motion | Tailwind 4.3.0, shadcn 4.10.0, `@base-ui/react` 1.5.0, motion 12.40.0 |
| Charts | Recharts | 3.8.1 |
| Frontend Tests | Vitest, Playwright, Testing Library, MSW | Vitest 4.1.8, Playwright 1.60, Testing Library React 16.3.2, MSW 2.14.6 |
| Python Quality | ruff, pyright, pytest, bandit, pip-audit | ruff 0.15.20, pyright 1.1.411, pytest 9.1.1, pytest-cov 7.1.0, bandit 1.9.4, pip-audit 2.10.1 |
| AI Evals | Pydantic Evals | 2.0.0 |

---

## Aktuelle Kernregeln für alle Reviews

| Regel | Kurzinhalt | Review-Relevanz |
|---|---|---|
| RULE-01b | Agents/ModelRegistry statt direkte Provider/Agent-Instanzierung | Direkte LLM-/Agent-Nutzung nur an erlaubten Grenzen; aktuelle Ausnahmen stehen in `pyproject.toml` und `CONSTRAINTS.md` §7. |
| RULE-02/02a | Prompts in `core/prompts/`; Content-Kategorien: Capability / Cascade / Dynamic Data | Feature-Prompts via PromptComposer/Cascade; garantierte Inhalte via Capabilities; dynamische Daten via agent instructions/Deps. Keine Service-f-Strings als System-/Task-Prompts. |
| RULE-02b | Prompt-Resolution-Path Compliance | Kein direkter Registry-Zugriff/App-Layer-Loader/User-Channel-Systemprompt/Inline-Fallback; ADR-046/049/054 sind aktuelle Referenz. |
| RULE-03 | Contracts before implementation | Services, cross-feature consumers und Fakes brauchen Protocols/Contracts vor Implementation; relevant für alle neuen Analyse-/Adapter-/Serviceflächen. |
| RULE-04/06 | Datei-Limits und eine Verantwortung pro Datei | Hard limits bleiben blockierend; Modularisierung statt Kommentar-/Whitespace-Löschung. Graph meldet einige Dateien knapp/über 400 Zeilen, v. a. Tests/Tooling und einzelne Produktionsdateien — für Folge-Reviews gezielt bewerten. |
| RULE-10 | Tests und Coverage-Mindestwerte | Neue Service-Methoden brauchen Unit-Tests, Router Integration-Tests; `core/` 90%, `apps/api/` 80% als Standard. CI nutzt aktuell global `--cov-fail-under=80` plus module coverage ratchet. |
| RULE-14 | Model-Änderung braucht Alembic-Migration | Jede SQLAlchemy-Modeländerung braucht Migration + Regressionstest; Integration nutzt echte Postgres/Alembic-Migrationen. |
| RULE-15 | Next.js Route Middleware nur `proxy.ts`, niemals `middleware.ts` | `packages/web/proxy.ts` ist einziger Route-Middleware-Ort; `prebuild` und Architekturcheck blocken `middleware.ts`. |
| RULE-16/17 | i18n Namespace und API-Frontend-Contract Konsistenz | UI-Strings en/de/fr; Backend-Schemafelder müssen mit Frontend-Typen übereinstimmen; CI führt Locale-/i18n-/Contract-Gates aus. |
| RULE-18/18b/19 | Keine hardcoded Router-Konfig; Configuration Effect Integrity; `SessionDep` in Dependency Factories | Provider/Modelle aus Settings/DI; material settings brauchen runtime_consumer + enforcement_evidence in Config-Matrix; FastAPI dependencies nutzen `SessionDep`. |
| RULE-20/22 | Keine Half-Implementations; Cross-Feature Coherence Gate | SSE-fähige AI-Backends brauchen Frontend-SSE; shared data braucht Integration-Contract und Change/Delete-Semantik. Dokumentiert ≠ implementiert — Implementation + Enforcement prüfen. |
| RULE-23 | Keine undisziplinierten `# type: ignore` Suppressions | Bare Suppressions verboten; erlaubte Suppressions brauchen Code + Grund und dürfen Baseline nicht erhöhen. |

---

## Einstiegspunkte & Zugriffs-Layer

- **CLI:** Kein Produkt-CLI implementiert. Dev-/Ops-Zugriff über `justfile`, Setup-/Seed-Skripte, `uv`, `pnpm`; Evals via `python -m evals`.
- **API (REST/FastAPI):** `apps/api/narrare`, App in `apps/api/narrare/_app/main.py`; REST, SSE und WebSocket-Endpunkte über Domain-Router. Aktuelle Domainmodule laut `CURRENT_STATE.md`: analysis, auth, chapters, consistency, embeddings, events, generation, kb, memory, metrics, novels, planning, prompts, settings, setup, tasks, templates, volumes, writing plus `_app`.
- **MCP-Server:** Nicht implementiert; kein `apps/mcp/` im aktuellen Repo. MCP/ADAPTER-001 bleibt Roadmap/Idee; Q-001 (MCP Auth) offen.
- **WebUI:** `packages/web`, Next.js 16 App Router, primärer Client mit TipTap v3 Editor, Setup Wizard, Studio, Worldbuilding, Analysis, Settings.
- **A2A:** Nicht als Produktadapter implementiert; kein `apps/a2a/`. Feature-Index enthält INFRA-006 als in-progress, aber Adapter-Abschnitt und Q-002 führen A2A weiter als nicht implementierten Roadmap-Adapter/Blocker.

---

## Review-Methodik

- Graph-first ausgeführt: `get_minimal_context`, `list_graph_stats`, `get_architecture_overview`, `list_communities`, `get_hub_nodes`, `find_large_functions`, `semantic_search_nodes` für `character_voice`.
- Graph-Snapshot: 25.812 Nodes, 183.761 Edges, 2.752 Dateien; Sprachen: Python, Bash, TypeScript, TSX, JavaScript; letzter Graph-Update: 2026-06-29T18:07:15; Embeddings: 0.
- Top-Communities (size ≥100): `tests-it:renders` (591), mehrere `tests-when`-Cluster, `planning-service` (452), `scripts-check` (345), `prompts-prompt` (321), `fakes-called` (317), `analysis-when` (266), `chapters-service` (174).
- Hotspots aus Graph: `fetchApi`, `useTipTapEditorController`, `KBSessionFieldList`, `MetadataSidebar`, `useKnowledgeGraphController`; Test-Hubs und initiale Alembic-Migration sind ebenfalls hochgradig verbunden.
- Danach gezielte Reads der Template-/SSOT-Dokumente, ADR-/Feature-/Question-Indizes, Package-Metadaten, CI Workflow, `justfile`, README/CHANGELOG. Keine vollständigen Checks/Tests ausgeführt, kein Commit erstellt.

---

## Verzeichnisstruktur (Top-Level)

```
_audit/              Review-Prompts und Audit-Ergebnisse
apps/                FastAPI Backend (`api/`); MCP/A2A Adapter derzeit nicht im Repo
packages/            core, i18n, web
docs/                SSOT-Dokumentation, ADRs, Features, MVP/Reference
scripts/             Architektur-, Prompt-, Drift-, Health-, CI- und Dev-Checks
tests/               Unit, Integration, E2E
evals/               Pydantic-Evals Suiten und Runner
data/                Demo-/Seed-Daten
openspec/            OpenSpec-Artefakte
.github/             CI/Release Workflows
.devcontainer/       Optionaler DevContainer Overlay
.opencode/ .agents/  Agent-/Skill-Kontext und lokale Tooling-Konfiguration
.evidence/           Invocation-/Runtime-Evidence Artefakte
Dockerfile docker-compose.dev.yml docker-compose.release.yml docker-compose.prod.yml
README.md CHANGELOG.md pyproject.toml package.json pnpm-workspace.yaml justfile uv.lock pnpm-lock.yaml
```

---

## Bekannte Probleme & offene Punkte (Stand Review)

| ID | Problem | Status | Priorität |
|---|---|---|---|
| CTX-001 | `character_voice` Runtime-Adoption ist laut `CURRENT_STATE.md`/Feature-Index governed debt: static-verified, Runtime-Evidence pending CI/integration. | Offen/governed debt; nicht als vollständig runtime-adopted behaupten | Mittel |
| CTX-002 | Abgeleitete Gate-Dokumentation ist teilweise stale: `.opencode/.../quality-gates.md` beschreibt noch Coverage-Übergangsausnahme `--cov-fail-under=60`; `.github/workflows/ci.yml` ist aktueller und blockt Unit Coverage aktuell bei 80% plus Module-Coverage-Ratchet. | Dokumentationsdrift; CI Workflow ist operative Quelle | Mittel |
| CTX-003 | `CURRENT_STATE.md` Codebase Overview enthält kleinere interne Drifts (z. B. 20 AI agents / ADR-001–051 Überblick), während spätere Abschnitte und ADR-INDEX ADR-055/CharacterVoiceAgent enthalten. | Kontextfalle; neuere Abschnitte, Feature-Index, ADR-Index und Code bevorzugen | Niedrig |
| CTX-004 | A2A/MCP Status ist weiterhin nicht implementiert: Q-001 MCP Auth, Q-002 A2A Streaming und Q-011 Distribution bleiben offen; Feature-Index markiert INFRA-006 als in-progress, Adapter-Abschnitt hält A2A/MCP aber als Roadmap/Idee fest. | Offen/Statusdrift prüfen vor Adapter-Reviews | Niedrig |
| CTX-005 | Graph-Architektur-/Knowledge-Gap-Ausgaben waren sehr groß/truncated; kompakte Graph-Werte sind belastbar, Detailanalysen sollten in Folge-Reviews gezielt mit fokussierten Queries erfolgen. | Tooling-Einschränkung; kein fachlicher Blocker | Niedrig |
| CTX-006 | `CHANGELOG.md` ist auto-generiert und enthält ältere/unreleased Sammelblöcke; für aktuelle Statusaussagen nicht allein verwenden. | SSOT-Hinweis; CURRENT_STATE/Feature-Index/ADR-Index bevorzugen | Niedrig |

Nicht erneut als offen führen: alte Backend-Unit-Failures, Streaming-Compliance-Verstöße, KB-Adoption 0.78, Frontend-RULE-04-Altlasten, alte inline Feature-Prompt Baseline 3→0 und manuelle AbortController in AI-Komponenten sind laut aktuellem Status erledigt. Bei jeder „resolved/implemented“-Behauptung trotzdem Implementation + Enforcement prüfen.

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
