# Review 04 – Developer Experience & Tooling

> Aktualisiert am 2026-06-29 durch NarrarePlatformSpecialist. Grundlage:
> `_audit/results/technical-review/review-00-kontext.md`,
> `_audit/results/technical-review/review-01-architektur.md`,
> `_audit/results/technical-review/review-02-testing.md`,
> `_audit/results/technical-review/review-03-ai-features.md`,
> `docs/_shared/CONSTRAINTS.md` als SSOT, aktuelle Code-/Checker-Evidenz
> (frische `just`-Läufe in dieser Session), pyproject.toml, package.json,
> justfile, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`,
> `.devcontainer/*`, README, deployment-guide, TECH_STACK, CURRENT_STATE,
> AGENTS.md-Hierarchie, `.opencode/context/narrare-dev/*`, ADR-Verzeichnis.
> Kein Commit, kein `--no-verify`. Nur diese Ergebnisdatei geschrieben.
> Alte Befunde zu Node 20/22-Drift und `install.sh` sind erledigt bzw. obsolet.

## Methodik & ausgeführte Prüfungen

- **Graph-first ausgeführt:** `get_minimal_context` (26.084 Nodes, 185.730 Edges,
  2.777 Files, Risiko low), danach gezielte Reads/Globs/Greps.
- **Frische Checker-Läufe in dieser Session (alle grün, siehe Review 01/02 für
  weitere):**
  - `just check-architecture` → ✅ 1.914 Dateien, 16 genehmigte Exceptions,
    Exception-Baseline 11/11/0/0, Prompt Surface Contract OK.
  - `just check-python-size` → ✅ 0 current / 2 baseline / 0 new / 2 resolved.
  - `just check-frontend-size` → ✅ 0 current / 0 baseline / 0 new.
  - `just check-health` → ✅ 0.93 HEALTHY 🟢 (Architecture 1.00, Prompt 1.00,
    Feature Adoption 0.87, Streaming 1.00, Exception Baseline 0.53 wegen 11
    genehmigten Ausnahmen — dokumentierte Governed Debt, Frontend 1.00,
    Test 1.00).
  - `just check-governance` → ⚠️ GOVERNED_DEBT (507 doc-drift-Warnungen,
    7 registry-drift-Warnungen, 12/2 finding-coverage; nicht-blockierend,
    aber sichtbarer Docs/SSOT-Drift).
- **Geprüfte Quellen:** README.md, pyproject.toml (root + apps/api),
  package.json (root + web), pnpm-workspace.yaml, justfile (607 Zeilen),
  `.pre-commit-config.yaml` (27 Hooks), `.github/workflows/ci.yml`
  (9 Jobs: architecture, lint, typecheck, security, test-unit,
  test-integration, update-coverage-badge, frontend, test-e2e),
  `.devcontainer/{Dockerfile, devcontainer.json, post-create.sh,
  docker-compose.devcontainer.yml, devcontainer-lock.json}`,
  `docs/development/deployment-guide.md`, `docs/_shared/{CONSTRAINTS,
  TECH_STACK, CURRENT_STATE}.md`, `.opencode/context/narrare-dev/{navigation,
  processes/quality-gates, guides/deployment, lookup/{tech-stack,
  current-state}}.md`, AGENTS.md-Hierarchie (root, packages/core, apps/api,
  tests), `docs/architecture/decisions/` (50 dateibasierte ADRs + 7 ohne
  `ADR-`-Präfix).
- **Lokale Tool-Versionen:** Node 24, pnpm 11.5.2 (Dockerfile + Root-Pin
  + CI konsistent), Python 3.14, uv via `pyproject.toml` Workspace.
- **Nicht ausgeführt:** Vollständiges `just dev-setup`, kein Docker Build,
  kein `pnpm test` (Frontend-Evidenz aus Review 02/03 übernommen).

---

## 1. Entwicklungsumgebung aufsetzen

**Bewertung:** ⭐⭐⭐⭐⭐ `Ein-Befehl-Onboarding, README konsistent`

**Befunde:**
- **README Quick Start** ist klar und aktuell: `just dev-setup` → `.env`
  editieren → `just dev` (`README.md:22-39`). Requirements dokumentieren
  Python 3.14+, Node.js 24+, Docker, uv, just (`README.md:14-20`).
- **README klärt `uv sync --all-packages`-Pflicht** explizit
  (`README.md:35-37`) — der alte AUFG-04-04-Befund ist erledigt.
- **`just dev-setup`** führt alles Notwendige durch (uv sync mit `--frozen
  --all-packages --group dev --extra nlp`, spaCy-Modelle, pre-commit,
  pnpm install, Services, Migration, Dev-User-Seed — `justfile:94-105`).
- **Deployment Guide** dokumentiert `uv sync`-Pflicht und die konkreten
  Folgen eines Weglassens (`deployment-guide.md:22-42`):
  „Pre-commit hooks fail … Pyright reports thousands of unresolved
  imports … cannot import `narrare` or `narrare_core`".
- **`install.sh`** existiert nicht mehr — alter Befund obsolet.
- **Setup-Zeit von null** grob: 10–30 Minuten je nach Cache-Stand und
  Netzwerk. Workflow ist schlüssig; Post-create-Skript im DevContainer ist
  robust ( wartet auf DB, migriert, seedet).
- **Onboarding-Simulation aus Neueinsteiger-Sicht** durchlaufbar:
  README → just dev-setup → .env editieren (API-Key + SECRET_KEY +
  NARRARE_ENCRYPTION_KEY) → just dev → Setup Wizard. Keine
  undokumentierten Voraussetzungen识别bar.
- **Kleines DX-Risiko (kein eigener AUFG, da dokumentiert):** `uv sync
  --frozen` in `just dev-setup` bricht, sobald das Lockfile aktualisiert
  wurde (z. B. nach `just deps-update` oder Dependabot-PR). Das ist
  beabsichtigt (Reproduzierbarkeit), kann aber Neueinsteiger überraschen,
  die einen frischen Clone eines Branches mit neuem Lockfile ziehen.
  Deployment Guide sollte diesen Fail-Mode im Abschnitt
  „Troubleshooting" ergänzen — aktuell fehlt er.

| Skript / Befehl | Zweck | Funktioniert? | Probleme |
|---|---|---|---|
| `just dev-setup` | Full local setup | Struktur geprüft, post-create.sh analog im DevContainer verifiziert | `--frozen` bricht bei Lockfile-Drift; keine Troubleshooting-Doku |
| `just dev` | API + Frontend + Services | Struktur geprüft | Langlaufende Prozesse; Cleanup via Ctrl+C dokumentiert |
| `just check` | Kompakter Quality-Runner | Struktur geprüft | Orchestriert `scripts/run_checks.py`; CI nutzt einzelne Jobs |
| `just check-full` | Alle Gates strikt | Struktur geprüft | Schließt streaming, ai-ux, prompts-strict, adoption, governance, health ein |
| `just test-unit` | Unit-Tests schnell | In Review 02 ausgeführt | `-n auto --dist loadfile`; guter DX-Fastpath |
| `pnpm test` | Frontend-Tests | In Reviews 02/03 geprüft | 274 Files / 2.287 Tests / ~182s (Review 02 AUFG-02-03) |

**Verbesserungen seit dem alten Review:**
- Node-Versionen konsistent auf 24+ (erledigt — alter AUFG-04-01).
- `install.sh` entfernt (erledigt).
- README klärt `uv sync --all-packages`-Pflicht (erledigt — alter
  AUFG-04-04).
- DevContainer pnpm-Version auf 11.5.2 angehoben (erledigt — alter
  AUFG-04-03).
- Biome-Extension im DevContainer ergänzt (erledigt — alter AUFG-04-05).
- Pre-commit-Fastpath im Deployment Guide dokumentiert (erledigt — alter
  AUFG-04-06).
- Architecture-Exceptions-Sync als CI-Gate verdrahtet
  (`ci.yml:115-116`: `check_exception_baseline.py --check-sync`)
  (erledigt — alter AUFG-04-07).

---

## 2. DevContainer

**Bewertung:** ⭐⭐⭐⭐⭐ `ADR-029-konform, aktuell und vollständig`

**Befunde:**
- `.devcontainer/devcontainer.json` nutzt Docker Compose aus
  `docker-compose.dev.yml` + `docker-compose.devcontainer.yml`
  (`.devcontainer/devcontainer.json:3`). Das entspricht ADR-029
  (VM-first, DevContainer optional).
- **Base-Image:** `mcr.microsoft.com/devcontainers/python:3.14-bookworm`
  (`.devcontainer/Dockerfile:1`) — aktuell.
- **Python 3.14, Node 24, uv, just, pre-commit** im Dockerfile installiert
  (`.devcontainer/Dockerfile:1-32`).
- **pnpm** auf 11.5.2 gepinnt (`Dockerfile:28: ARG PNPM_VERSION=11.5.2`)
  — Root `package.json:5`, CI (`ci.yml:516,629`) und Dockerfile sind
  konsistent. Alter AUFG-04-03 erledigt.
- **Ports** 3000, 8000, 5432, 6379 korrekt forwarded mit Labels
  (`devcontainer.json:67-73`).
- **Extensions** vollständig: Python/Pylance/Ruff/Debugpy/Tailwind/Docker/
  GitLens/Spellcheck/TOML/YAML/GitHub-Actions, plus **Biome**
  (`devcontainer.json:22`) und ESLint/Prettier. Alter AUFG-04-05 erledigt.
- **Post-create-Skript** (`post-create.sh`, 88 Zeilen): installiert uv
  deps, spaCy-Modelle, pre-commit, kopiert `.env`, passt Hostnamen für
  Container-Netzwerk an (postgres/postgres_test/redis statt localhost),
  wartet bis zu 60s auf DB, migriert, seedet Dev-User. Vollständig und
  robust.
- **`NARRARE_DEV_MODE=container`** wird via Compose-Umgebung
  (`docker-compose.devcontainer.yml:23`) und zusätzlich im Post-create
  gesetzt (`post-create.sh:42-46`); justfile-Helper
  (`justfile:18-25`) nutzen das für korrekte Hostnamen.
- **OpenCode-Bind-Mounts** vorhanden
  (`docker-compose.devcontainer.yml:13-17`):
  `~/.opencode-data/{config,home,state,share,cache}`.
- **devcontainer-lock.json** pinnt die beiden Devcontainer-Features
  (git@1.3.5, github-cli@1.1.0) per Digest — vorbildliche
  Reproduzierbarkeit.

**Checkliste:**
- [x] Base-Image aktuell (`python:3.14-bookworm`)
- [x] Alle Ports korrekt gemappt (3000, 8000, 5432, 6379)
- [x] Post-create-Script vorhanden und vollständig
- [x] Extensions installiert (Python, Ruff, Tailwind, Docker, GitLens,
      Biome, u.a.)
- [x] `.env.example` vorhanden und per Post-create kopiert
- [x] Hostname-Anpassung für Container-Netzwerk automatisiert
- [x] `NARRARE_DEV_MODE=container` gesetzt und von justfile berücksichtigt
- [x] pnpm-Version mit CI/Root-Pin synchron (11.5.2)
- [x] Devcontainer-Features per Digest gelocked
- [ ] Cursor-Kompatibilität nicht explizit dokumentiert (VS Code-First);
      kein Blocker — DevContainer-Standard funktioniert in Cursor, aber
      README erwähnt nur VS Code (`README.md:81-89`).

---

## 3. pyproject.toml

**Bewertung:** ⭐⭐⭐⭐⭐ `Sauber, modern, maschinell synchronisiert`

**Befunde:**
- **PEP 517/518** via Hatchling (`pyproject.toml:29-31`).
- **uv workspace** klar definiert: `apps/api`, `packages/core`,
  `packages/i18n` (`pyproject.toml:36-37`). `uv sync --all-packages`
  installiert alle Workspace-Member.
- **Tool-Konfigurationen** für pyright, ruff, pytest, coverage, bandit,
  architecture zentral in `pyproject.toml` gebündelt. Keine
  Split-Konfiguration über mehrere Dateien (bis auf `.pre-commit-config.yaml`
  für Hook-Wiring, was korrekt ist).
- **Dependency-Pinning** im Dev-Bereich strikt: `ruff==0.15.20`,
  `pyright==1.1.411`, `pytest==9.1.1`, `pydantic-evals==2.0.0`
  (`pyproject.toml:13-27`). App-Abhängigkeiten in `apps/api/pyproject.toml`
  ebenfalls gepinnt (z. B. `fastapi==0.138.1`, `sqlalchemy==2.0.51`,
  `structlog==26.1.0`, `taskiq==0.12.4`, `pyrate-limiter>=4.0,<5`).
- **Pytest-Konfiguration** ist reif: `asyncio_mode=auto`, session-scoped
  loops, `timeout=10`, `timeout_func_only=true`, Marker für
  unit/integration/e2e/requires_db, `norecursedirs`, `pythonpath`
  korrekt gesetzt (`pyproject.toml:171-190`).
- **Coverage-Konfiguration:** `fail_under = 80` in
  `[tool.coverage.report]` (`pyproject.toml:204`) und CI
  (`ci.yml:309`) verwendet `--cov-fail-under=80`. Die frühere
  60%-Übergangsausnahme ist in Code + CI vollständig aufgehoben
  (Review 02). Stale Doku bleibt als AUFG-02-04.
- **Architecture Constraints** als `[tool.narrare.architecture]` section
  (`pyproject.toml:231-361`): `llm_allowed_modules`,
  `agent_allowed_modules`, `prompt_allowed_modules`,
  `file_size_limits`, `configurable_defaults`, `exceptions`. Die
  exceptions-Section ist als **CANONICAL SOURCE** markiert
  (`pyproject.toml:278-283`).
- **Architecture-Exception-Sync maschinell erzwungen:** CI führt
  `check_exception_baseline.py --check-sync` aus (`ci.yml:115-116`),
  das prüft, dass `pyproject.toml`-Einträge mit `CONSTRAINTS.md §7`
  übereinstimmen. Alter AUFG-04-07 damit erledigt — die alte
  manuelle Synchronisationspflicht ist durch ein Gate ersetzt.
- **Exception-Baselining:** Aktuell 16 genehmigte Exceptions (11
  baseline-stabil, 0 new, 0 unresolved — `just check-architecture`
  Output). Einträge sind mit `rule`, `file`, `reason`, `approved_by`,
  `date` sauber strukturiert; die neueste (`memory/suggestion_identity.py`,
  `2026-06-22`) wurde via CR-AUFG-07-24 genehmigt.

**Abhängigkeits-Audit (representative Auswahl):**

| Paket | Pyproject-Pin | CI-Evidence | Status |
|---|---|---|---|
| `ruff` (dev) | `==0.15.20` | `ci.yml:202` | Aktuell |
| `pyright` (dev) | `==1.1.411` | `ci.yml:235` | Aktuell |
| `pytest` (dev) | `==9.1.1` | `ci.yml:304` | Aktuell |
| `pydantic-evals` (dev) | `==2.0.0` | `ci.yml:172` | Aktuell |
| `fastapi` (api) | `==0.138.1` | `apps/api/pyproject.toml` | Aktuell |
| `sqlalchemy` (api) | `==2.0.51` | `apps/api/pyproject.toml` | Aktuell |
| `taskiq` (api) | `==0.12.4` | `apps/api/pyproject.toml` | Aktuell |
| `structlog` (api) | `==26.1.0` | `apps/api/pyproject.toml` | Aktuell |
| `pyrate-limiter` (api) | `>=4.0,<5` | `apps/api/pyproject.toml:30` | Aktuell |
| `Next.js` (web) | `16.2.6` | `packages/web/package.json:56` | Aktuell |
| `React` (web) | `19.2.6` | `packages/web/package.json:58-59` | Aktuell |
| `TypeScript` (web) | `^6.0.3` | `packages/web/package.json:87` | Aktuell |
| `Vitest` (web) | `^4.1.8` | `packages/web/package.json:89` | Aktuell |
| `Biome` (web) | `2.4.15` | `packages/web/package.json:70` | Aktuell |
| `Tailwind` (web) | `^4.3.0` | `packages/web/package.json:86` | Aktuell |

> Siehe Abschnitt 5 für die **TECH_STACK.md**-SSOT-Driftthese: pyproject
> ist aktuell, aber die menschenlesbare SSOT-Doku hinkt hinterher.

---

## 4. Tools-Review & Alternativen

**Bewertung:** ⭐⭐⭐⭐⭐ `Zeitgemäß, konsistent, kein Wechsel empfohlen`

| Kategorie | Aktuelles Tool | Version | Zeitgemäße Alternative | Wechsel sinnvoll? |
|---|---|---|---|---|
| Linter (Python) | Ruff | 0.15.20 | — | Nein — Branchenstandard |
| Linter (Frontend) | Biome | 2.4.15 | ESLint+Prettier | Nein — Biome ist schneller |
| Formatter (Python) | Ruff | 0.15.20 | Black | Nein — Ruff ersetzt Black |
| Formatter (Frontend) | Biome | 2.4.15 | Prettier | Nein |
| Type Checker (Python) | Pyright (strict) | 1.1.411 | basedpyright | Nein — strict ausreichend |
| Type Checker (Frontend) | tsc | 6.0.3 | — | Nein |
| Test Runner (Python) | pytest | 9.1.1 | — | Nein |
| Test Runner (Frontend) | Vitest | 4.1.8 | Jest | Nein — Vitest ist der Jest-Nachfolger |
| Task Runner | just | n/a | mise | Nein — just ist schlank und ausreichend |
| Paket-Manager (Python) | uv | workspace | poetry, pdm | Nein — uv ist schneller |
| Paket-Manager (Frontend) | pnpm | 11.5.2 | npm, yarn | Nein |
| Frontend Build | Next.js | 16.2.6 | — | Nein |
| Frontend E2E | Playwright | 1.60 | Cypress | Nein |
| Security Audit | bandit + pip-audit + Gitleaks | 1.9.4 / 2.10.1 / 8.30.1 | — | Nein |
| AI Evals | Pydantic Evals | 2.0.0 | promptfoo (superseded) | Nein |
| Observability | OpenTelemetry + structlog | 26.1.0 / >=1.39 | Langfuse/Logfire (nur optional) | Nein — ADR-031 |

**Befunde:**
- Toolchain ist vollständig modern. Kein Tool-Wechsel empfohlen (und
  per Review-Regeln auch keine PyPI-Empfehlungen zu geben).
- **Haupt-DX-Themen** sind nicht Tool-Auswahl, sondern:
  1. **Dokumentationsdrift** (Abschnitt 5).
  2. **Performance** (Frontend-Testlaufzeit ~182s — Review 02 AUFG-02-03).
  3. **Pre-commit-Last** (27 Hooks — Abschnitt 6).
- Alle in CI genutzten Versionen sind in pyproject.toml / package.json /
  Dockerfile / ci.yml konsistent gepinnt.

---

## 5. Dokumentationsstruktur

**Bewertung:** ⭐⭐⭐ `Struktur vorbildlich, aber SSOT und extrahierte Kontexte deutlich drift`

**Befunde — Positiv:**
- **README.md** (103 Zeilen): Kompakt, aktuell, enthält Requirements,
  Quick Start, Project Structure, Dev Container, Architecture,
  MCP/A2A-Klarstellung. Coverage-Badge 88%.
- **docs/_shared/**: CONSTRAINTS.md (SSOT für Regeln), TECH_STACK.md,
  CURRENT_STATE.md (Live-Status), GLOSSARY.md.
- **docs/development/**: 11 Dateien — coding-standards, testing-standards,
  deployment-guide, ui-principles, orchestrator, prompt-standards,
  prompt-content-standards, observability-guide, finding-lifecycle,
  how-to-add-an-agent, type-ignore-audit.
- **docs/architecture/decisions/**: INDEX.md + 57 ADR-Dateien (ADR-001
  bis ADR-056 mit Lücken 017/019/025/039/043/052/053/054 als
  numerisch-only-Dateien), strukturiert nach Status.
- **docs/features/**: INDEX.md mit Feature-Specs.
- **CHANGELOG.md**: Automatisch via release-please generiert.
- **docs/DEBT.md**: 4 nicht-blockierende Scaffold-Placeholder-Einträge,
  revalidiert 2026-06-29.
- **API-Dokumentation**: OpenAPI-Export in CI generiert und auf Drift
  geprüft (`ci.yml:121-122`, `export_openapi.py --check`).
- **MCP/A2A-Dokumentation**: Bewusst nicht vorhanden, weil Adapter nicht
  implementiert. README klärt das explizit (`README.md:97-99`).
- **`.opencode/context/narrare-dev/`**: 35 extrahierte Kontextdateien mit
  `Priority`/`Source`/`Updated`-Metadaten, strukturiert in
  `constraints/`, `concepts/`, `standards/`, `processes/`, `guides/`,
  `domain/`, `lookup/`, `templates/`, `examples/` plus `navigation.md`.
  Konzept ist vorbildlich für AI-Agent-Navigation.
- **`.agents/skills/`** (21 plattformunabhängig) + **`.opencode/skills/`**
  (6 opencode-native) + **`.opencode/commands/`** (6 Commands: recall,
  remember, opsx-{propose,explore,apply,archive}). Trennung ist korrekt.
- **`.claude/`** ist nicht vorhanden (Projekt nutzt opencode, nicht
  Claude Code nativ). Kein Befund.
- **AGENTS.md-Hierarchie** (root, packages/core, apps/api, tests):
  SSOT-Disziplin klar deklariert; CONSTRAINTS.md als autoritativ markiert.

**Befunde — Drift (konkret belegt):**

### 5.1 `docs/_shared/TECH_STACK.md` SSOT hat stale Version-Pins

TECH_STACK.md ist laut CONSTRAINTS.md §8 autoritativ, aber PINS und
Abhängigkeitslisten hinken dem tatsächlichen pyproject.toml deutlich
hinterher:

| TECH_STACK.md-Eintrag | Behauptet | Tatsächlich (pyproject.toml / apps/api) |
|---|---|---|
| `pydantic-ai >=1.93` (Zeile 78, 83-84) | 1.93+ | `pydantic-ai-slim[...] 2.0.0` (Review 00) |
| `mem0 >=1.0` (Zeile 103ff) | 1.x | `mem0ai 2.0.10` (Review 00; ADR-033 + 2.0.x) |
| `TaskIQ [redis] >=0.11.0` (Zeile 146) | 0.11+ | `taskiq 0.12.4 / taskiq-redis 1.2.3 / taskiq-fastapi 0.5.0` |
| `PyJWT >=2.10` (Zeile 183) | 2.10+ | `PyJWT 2.13.0` |
| `argon2-cffi >=23.1.0` (Zeile 187) | 23.1+ | `argon2-cffi >=25.1.0` |
| `fastapi-limiter >=0.1.6` (Zeile 193-195) | fastapi-limiter ist aktiv | `fastapi-limiter` wird **nicht** verwendet; Code nutzt `pyrate-limiter >=4,<5` direkt über `_app/rate_limiter_dep.py` (22 Treffer in apps/api) |
| `structlog >=25.5` (Zeile 201) | 25.5+ | `structlog 26.1.0` |
| `pydantic-settings >=2.13` (Zeile 174) | 2.13+ | `pydantic-settings 2.14.2` |
| `Pydantic v2 >=2.12` (Zeile 168) | 2.12+ | `pydantic 2.13.4` |
| `FastAPI >=0.135` (Zeile 33) | 0.135+ | `fastapi 0.138.1` |
| `GLM-5.1 (z.ai)` (Zeile 97) | GLM-5.1 | aktuell ist GLM-5.2 (Runtime-Kontext) |
| „Explicitly NOT Used" slowapi→fastapi-limiter (Zeile 356) | fastapi-limiter als Aktiv-Ersatz | fastapi-limiter ist **selbst** nicht aktiv;(Code nutzt `pyrate-limiter` direkt) |
| `pre-commit` (Zeile 322-324) | „Runs: check_architecture.py, ruff, pyright, bandit, test subset" | tatsächlich 27 Hooks (`.pre-commit-config.yaml`): + prompt-structure, adoption-score, ai-interaction-compliance, exception-baseline, python-file-size, prompt-surface-contract, streaming-compliance, configuration-matrix, locale-sync, openapi-regenerate, version-consistency, biome, validate-i18n, typecheck-frontend, file-hygiene × 6, conventional-commits |

→ **DX-Risiko:** Neueinsteiger, die TECH_STACK.md lesen, treffen
Fehlannahmen über die pydantic-ai-Version (Migration Notes Zeile 83-84
sind für 1.x, nicht 2.x) und über die Rate-Limiter-Architektur.

### 5.2 `docs/_shared/CURRENT_STATE.md` hat interne Statistik-Drift

- Zeile 48 listet **20 AI agents** (beta_reader, character_arc, chat,
  consistency, draft, extraction, fact_extractor, inline_suggest, kb,
  kb_assist, kb_improve, merge, outline, pov_detection,
  preference_analysis, readability, review, summary, timeline,
  worldbuilding). Review 03 hat **26 produktive Agenten** identifiziert
  (zusätzlich: TemporalExtractionAgent, StorySuggestAgent,
  CoreferenceAgent, CharacterVoiceAgent, WikiGenerationAgent,
  PromptLiveTestAgent).
- ADR-Überblick in der gleichen Datei (Zeile 71) nennt „ADR-001–ADR-051",
  tatsächlich liegt ADR-056 vor (Review 00, ADR-Index).
- Dieselbe Art interne Statistik-Drift wie Review 00 CTX-003 bereits
  anmerkt.

### 5.3 Extrahierte Kontext-Dateien sind deutlich stale

`just check-governance` meldet 507 Doc-Drift-Warnungen. Konkrete
Beispiele aus `.opencode/context/narrare-dev/`:

- **`processes/quality-gates.md`** (Priority high, „Updated: 2026-05-31"):
  - Zeile 90-101: „Coverage threshold ⚠️ Warning (≥60%)", „Hard floor 60%",
    „Coverage liegt bei 76%" — tatsächlich ist CI
    `--cov-fail-under=80` blockierend (`ci.yml:309`) und Unit-Coverage
    liegt bei 88.94% (Review 02).
  - Zeile 88: „pyright ⚠️ Partial" — tatsächlich ist pyright full
    blocking im `typecheck` Job (`ci.yml:210-235`, Review 02: 0 Errors).
  - Zeile 78-93: Gate-Tabelle nennt 14 Einträge; aktuelle CI führt 25+
    Gates aus (Gitleaks, system health, governance health, module
    coverage, check-testid, eval smoke, eval drift, ssot facts, gate
    drift, gate expirations, ai-interaction-compliance fehlen).
  - Überschneidet mit AUFG-02-04.
- **`lookup/current-state.md`** (Priority critical, „Updated: 2026-06-05"):
  - Zeile 27: „Knowledge Graph: 15,527 nodes, 112,368 edges" — aktuell
    26.084 / 185.730 (Review 01).
  - Zeile 28: „Backend tests: 4,273 (3,750 unit + 495 integration) across
    396 test files" — aktuell 9.043 gesammelt / 832 Testdateien (Review 02).
  - Zeile 29: „Frontend tests: 1,683 across 186 test files" — aktuell
    2.287 / 274 (Review 02).
  - Zeile 32: „ADRs: 50 (ADR-001 through ADR-038, ADR-040 through
    ADR-051; ADR-039 gap)" — aktuell liegt ADR-056 vor.
  - Zeile 42: „18 AI agents" — tatsächlich 26 (Review 03).
  - Zeile 99: „System Health 0.73 (DEGRADED)" — aktuell 0.93 HEALTHY
    (`just check-health`, diese Session).
  - Zeile 100: „38 frontend RULE-04 legacy violations" — aktuell 0
    (`just check-frontend-size`, diese Session).
- **`lookup/tech-stack.md`** (Priority critical, „Updated: 2026-05-30"):
  - Spiegelt alle TECH_STACK.md-Drifts (5.1): pydantic-ai 1.93, mem0 1.0,
    fastapi-limiter aktiv, etc.
  - Zeile 97: „pre-commit: 9 hooks" — tatsächlich 27.
- **`guides/deployment.md`** (Priority high, „Updated: 2026-06-05"):
  - Zeile 13: `just dev-up` — dieser Befehl **existiert nicht** in der
    justfile (korrekt wäre `just dev-services`, `justfile:217-218`).
  - Zeile 28: „CI Pipeline (7-job workflow)" — tatsächlich 9 Jobs
    (`ci.yml`: architecture, lint, typecheck, security, test-unit,
    test-integration, update-coverage-badge, frontend, test-e2e).
  - Zeile 42-54: „Pre-commit Hooks (9 hooks)" — tatsächlich 27.
  - Überschneidet mit AUFG-02-04 für deployment-guide.md Hauptdokument.

### 5.4 Layer-AGENTS.md mit teils überholten Beispielen

- **`packages/core/AGENTS.md:97-103`** listet unter „Bestehende Agents"
  nur 6 (ChapterSummaryAgent, DraftAgent, OutlineAgent, ReviewAgent,
  KBAgent, WritingGraph). Tatsächlich leben 26 produktive NarrareAgent-
  Subtypen in `core/agents/` (Review 03). Die Liste ist seit mindestens
  Phase 4 nicht aktualisiert.
- **`tests/AGENTS.md:49-62`** zeigt ein MagicMock-Beispiel für
  `MockLLMGateway`. ADR-030 (MagicMock-to-Fake-Migration, als erledigt
  markiert CURRENT_STATE Zeile 266) und `testing-standards.md` verbieten
  bare MagicMock für Domain-Dependencies. Das Beispiel ist mit `spec=`
  annotiert, aber stilistisch inkonsistent mit der Fake-basierten
  Testkultur des Projekts.
- **`tests/AGENTS.md:75-79`** zeigt ein `Base.metadata.create_all()`-
  Fixture. Das widerspricht RULE-14 (jede Modeländerung braucht Migration
  + Integration nutzt echte Alembic-Migrationen, Review 00/02).
- **`tests/AGENTS.md:111-120`** zeigt einen Architecture-Constraint-
  subprocess-Test. Aktuell läuft `check_architecture.py` als Pre-commit-
  Hook (`pre-commit-config.yaml:5-11`) und CI-Job (`ci.yml:103-104`),
  nicht als pytest-Subprocess-Test. Das Beispiel ist überholt.

### 5.5 ADR-Datei-Namenskonvention inkonsistent

In `docs/architecture/decisions/` tragen 50 Dateien das `ADR-XXX-name.md`
-Format, aber 7 Dateien (017, 019, 025, 043, 052, 053, 054) verwenden
das reine `XXX-name.md`-Format ohne `ADR-`-Präfix. INDEX.md referenziert
sie mit `ADR-XXX`-Label, aber die Dateinamen sind uneinheitlich. Kein
Blocker, aber eine DX- und Tooling-Konsistenzlücke (Glob-Muster wie
`ADR-*.md` verfehlen diese 7 Dateien).

**Lücken-Matrix:**

| Zielgruppe | Dokumentiert | Fehlend |
|---|---|---|
| Endnutzer | README Quick Start, Release Bundle README | Nicht-technischer Installer/Onboarding-Guide; Desktop-App |
| Entwickler (Setup) | README, deployment-guide, devcontainer, justfile | Troubleshooting für `--frozen`-Fail-Mode; Hinweis `just dev-up`- Phantom im extrahierten Kontext |
| Entwickler (Architektur) | CONSTRAINTS.md, ADRs, AGENTS.md, .opencode/context | TECH_STACK.md-Pins sind stale; CURRENT_STATE.md-Agent-Statistik ist stale |
| Entwickler (Testing) | testing-standards, quality-gates, Examples/Patterns | quality-gates.md (extrahiert) beschreibt 60%-Coverage-Übergang; tests/AGENTS.md-Beispiele alt |
| API-Konsumenten | OpenAPI exportiert, `/docs`-Endpoint | Öffentliche API-Doku/SDK außerhalb des Repos |
| AI-Agenten / MCP-Clients | `.opencode/`, `.agents/`, AGENTS.md | lookup/current-state.md spiegelt stale Graph-/Test-Counts; Produkt-MCP/A2A fehlt (Roadmap) |

---

## 6. Agent- und Quality-Gate-DX

**Bewertung:** ⭐⭐⭐⭐ `Sehr reif; Code-Graph-First muss operationell stabil bleiben`

**Befunde:**
- **Spezialisierte Narrare-Agents** sind auffindbar und gut geroutet:
  `.opencode/agents/subagents/narrare-dev/` mit je einem Specialist pro
  Layer (`architecture.md`, `backend.md`, `core.md`, `docs.md`,
  `frontend.md`, `platform.md`). Root `AGENTS.md` definiert Trigger-
  Phrasen und Delegation-Muster. Konsistent mit den narrare-XX-Specialists
  aus dem System-Prompt.
- **Skills** sind zahlreich und aktuell: 21 externe (`.agents/skills/`)
  + 6 projektspezifische (`.opencode/skills/`: context7, openspec-*,
  task-management). Wichtige AI-Relevante: `building-pydantic-ai-agents`,
  `mem0`, `frontend-design`, Vercel-/Tailwind-/Shadcn-Pattern.
- **Code-Graph-First-Standard** ist als kritischer Kontext etabliert
  (`.opencode/context/narrare-dev/standards/code-graph-first.md`), und der
  Graph-MCP war in dieser Session stabil nutzbar
  (`get_minimal_context` → 26.084 Nodes). Alte Reviews (00/01) notierten
  wiederholt `Not connected` — das scheint aktuell behoben. Dennoch
  bleibt die Abhängigkeit der gesamten Agent-DX von einem funktionierenden
  MCP-Server ein operatives Risiko.
- **Quality Gates** sind umfassend dokumentiert und in CI/Pre-commit
  integriert:

| Gate | Check-Skript | CI | Pre-commit | Status (Session) |
|---|---|---|---|---|
| Architecture | `check_architecture.py` | ✅ Blocking (`architecture`) | ✅ | ✅ Grün (1.914 Dateien, 16 genehmigte Exceptions) |
| Exception Baseline | `check_exception_baseline.py` | ✅ Blocking | ✅ | ✅ 11/11/0/0 |
| **Exception Sync (pyproject ↔ CONSTRAINTS.md)** | `check_exception_baseline.py --check-sync` | ✅ Blocking (`ci.yml:115-116`) | — | ✅ Aktiv — erledigt alten AUFG-04-07 |
| OpenAPI Drift | `export_openapi.py --check` | ✅ Blocking | ✅ (auto-regenerate) | ✅ Grün |
| Prompt Structure | `check_prompt_structure.py` | ✅ Blocking | ✅ | ✅ Grün (Review 02: 48/48 valid) |
| Feature Adoption | `check_adoption.py` | ✅ Blocking | ✅ | ✅ Grün (Review 01: 0.97 PASS) |
| Streaming | `check_streaming_compliance.py` | ✅ Blocking | ✅ | ✅ Grün (Review 01) |
| AI-UX (ADR-043) | `check_ai_interaction_compliance.py` | ✅ Blocking | ✅ | ✅ Grün (Review 02: 0 Violations) |
| Frontend Size | `check_frontend_file_size.py` | ✅ Blocking | — | ✅ 0/0/0/0 (Session) |
| Python File Size | `check_python_file_size.py` | ✅ Blocking | ✅ | ✅ 0/2/0/2 (Session) |
| System Health | `check_system_health.py` | ✅ Blocking (`architecture`) | — | ✅ 0.93 HEALTHY (Session) |
| Test Coverage Gaps | `check_test_coverage_gaps.py` | ✅ Blocking | — | ✅ Grün (Review 02) |
| Module Coverage | `check_module_coverage.py --fail` | ✅ Blocking (`test-unit`) | — | ⚠️ Regression (Review 02 AUFG-02-01) |
| Locale Sync | `check_locale_sync.py` | ✅ Blocking | ✅ (bedingt) | ✅ Grün |
| Doc Drift | `check_doc_drift.py` | ✅ Blocking | — | ⚠️ 507 Warnungen (Session) |
| Registry Drift | `check_registry_drift.py` | ✅ Blocking | — | ⚠️ 7 Warnungen (Session) |
| Gate Drift | `check_gate_drift.py` | ✅ Blocking | — | ✅ Kein Drift |
| Gate Expirations | `check_gate_expirations.py` | ✅ Blocking | — | ✅ Aktiv |
| Version Consistency | `check_version_consistency.py` | ✅ Blocking | ✅ | ✅ Aktiv |
| Component Markers | `check-testid.ts` | ✅ Blocking (`frontend`) | — | ⚠️ Rot (Review 02 AUFG-02-02) |
| Configuration Matrix | `check_configuration_matrix.py` | ✅ Blocking | ✅ (bedingt) | ✅ Grün (Review 01) |
| Governance Health | `check_governance_health.py` | ✅ Blocking | — | ⚠️ GOVERNED_DEBT (Session) |
| Gitleaks | `check_secrets.py` | ✅ Blocking (`security`) | — | ✅ Aktiv |
| Bandit + pip-audit | `bandit`, `pip-audit` | ✅ Blocking (`security`) | ✅ (bandit) | ✅ Aktiv |
| Eval Smoke | `pydantic-evals` | ✅ Blocking (`architecture`) | — | ✅ Grün (Review 02) |
| Eval Drift | `check_eval_drift.py` | ⚠️ Warning (`architecture`) | — | ✅ Grün (Review 02: 57 Vergleiche) |
| SSOT Facts | `check_current_state_facts.py` | ⚠️ Warning (`architecture`) | — | ✅ Aktiv |

- **CI-Gate-Audit-Tabelle** in `ci.yml:3-43` ist vorbildlich: Jeder Gate
  mit Tool, CI-Status und Notes aufgelistet. Sehr gute DX-Praxis; sollte
  als Vorbild für die extrahierten quality-gates.md/guides/deployment.md
  dienen (siehe 5.3).
- **RULE-21** (Architecture-Review-Invalidierung bei Planänderungen) ist
  in `CONSTRAINTS.md` dokumentiert, aber nicht als maschineller Gate
  automatisiert. Bleibt manueller Prozessschritt.
- **Pre-commit-DX (27 Hooks):** Vollständige Suite läuft pro Commit. Das
  ist schwere Pre-commit-Last, aber der Fastpath ist jetzt im
  Deployment Guide dokumentiert (`deployment-guide.md:195-228`):
  `SKIP=pyright,architecture-constraints,adoption-score,prompt-structure
  git commit -m "feat(core): …"` mit klaren Regeln (CI bleibt
  autoritativ; `just check`/`just check-frontend` vor Push Pflicht).
  Alter AUFG-04-06 erledigt.
- **`ci: skip: [pyright]`** in `.pre-commit-config.yaml:201` — Pyright
  läuft in CI als vollständiger `typecheck`-Job, nicht pro-Datei.
  Konsistent mit der CI-Strategie.

**DX-Risiko — Code-Graph-MCP-Verfügbarkeit:** In dieser Session war der
Graph stabil. Alte Reviews notierten wiederholt `Not connected`. Da der
root `AGENTS.md` und alle Layer-AGENTS.md den Graph-First-Standard als
kritischen Kontext deklarieren, würde ein Ausfall des MCP-Servers die
gesamte Agent-DX massiv verschlechtern (Fallback auf Grep/Glob ist
dokumentiert, aber verliert strukturelle Informationen).

---

## 7. Skripte & Automatisierung

**Bewertung:** ⭐⭐⭐⭐⭐ `Umfangreich, konsistent, vorbildlich strukturiert`

**Befunde:**
- **`scripts/`-Verzeichnis** enthält 40+ Check-, Prüf- und Utility-Skripte.
  Strukturiert in Unterverzeichnisse: `architecture/`, `adoption/`,
  `checks/`, `doc_drift/`, `eval_drift/`, `local/`, `probes/`, `quality/`,
  `test_coverage_gaps/`.
- **Justfile** (607 Zeilen) bietet eine komplette Befehlsoberfläche:
  Setup, Dev, DB, Testing, Quality, Prompts, Release, Utilities. Alle
  Befehle sind dokumentiert und konsistent mit CI.
- **`just check-full`** ist der umfassendste lokale Check: architecture +
  streaming + ai-ux + secrets + prompts-strict + locale + adoption +
  configuration-matrix + models + governance + health.
- **Kein totes `install.sh`** mehr im Repository. Alte Befunde obsolet.

**Justfile-Befehls-Katalog (DX-relevante Highlights):**

| Kategorie | Befehl | DX-Qualität |
|---|---|---|
| Setup | `just dev-setup` | Ein-Befehl-Onboarding ⭐ |
| Development | `just dev`, `just dev-api`, `just dev-frontend`, `just dev-worker`, `just dev-e2e` | Gut aufgeteilt |
| Testing | `just test`, `just test-unit`, `just test-integration`, `just test-e2e`, `just test-frontend`, `just test-file`, `just test-match` | Klar getrennt, Flexible File/Pattern-Tests |
| Quality | `just check`, `just check-verbose`, `just check-full` | Abgestuft nutzbar |
| Database | `just db-migrate`, `just db-revision`, `just db-status`, `just db-history`, `just db-shell`, `just db-reset` | Vollständig |
| Prompts | `just check-prompts`, `just check-prompts-strict`, `just check-locale-sync`, `just check-prompts-de`, `just prompt-list`, `just prompt-stats` | Gut für Prompt-Arbeit |
| Cleanup | `just clean`, `just cleanup`, `just deps`, `just deps-update`, `just hooks-update` | Wartung abgedeckt |

---

## Gesamtbewertung Developer Experience & Tooling

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐⭐ | **Trend:** ➡️ Gleich, aber mit aufgelösten
Altlasten und neu identifizierter SSOT-Drift

**Zusammenfassung:** Die Narrare-DX ist weiterhin auf hohem Niveau:
Ein-Befehl-Onboarding via `just dev-setup`, moderne Toolchain (uv,
pnpm 11.5.2, Ruff, Pyright strict, Biome, Vitest), umfassende CI-Gates
mit transparenter Audit-Tabelle, solide DevContainer-Unterstützung
(ADB-029-konform) und eine vorbildliche Agenten-/Kontext-Infrastruktur
(35 Kontextdateien, 27 Skills, 6 Subagents, 6 Commands). Die alten
Node 20/22-, install.sh-, pnpm-Drift-, Biome-Extension-,
README-Hinweis-, Pre-commit-Fastpath- und Exception-Sync-Befunde sind
alle erledigt. Architektur-, File-Size-, Health- und Governance-Checker
sind in dieser Session frisch grün gelaufen. Das Haupt-DX-Risiko liegt
jetzt nicht mehr in Tool-Auswahl oder Setup, sondern in der
**Dokumentations-SSOT-Drift**: TECH_STACK.md und CURRENT_STATE.md
(agenturativ) sowie quality-gates.md, lookup/current-state.md,
lookup/tech-stack.md, guides/deployment.md und Layer-AGENTS.md
(abgeleitet) sind stellenweise deutlich hinter Code/CI/pyproject.toml
zurückgeblieben. 507 Doc-Drift-Warnungen des Governance-Health-Checks
sichtbar zu machen ist ein Erfolg der Maschinendisziplin; das
Beheben sollte Follow-up sein. Review 05 kann starten und diese Drift
als Kontext mitnehmen.

---

## Erledigte / ersetzte Altaufgaben aus vorherigem Review

- **AUFG-04-01 Node-Versionen vereinheitlichen:** ✅ erledigt. README,
  deployment-guide, CI und DevContainer Dockerfile nutzen nun alle
  Node 24+.
- **AUFG-04-02 (`install.sh`):** ✅ obsolet. `install.sh` existiert nicht
  mehr.
- **AUFG-04-03 pnpm-Version im DevContainer:** ✅ erledigt.
  `.devcontainer/Dockerfile:28` nutzt `ARG PNPM_VERSION=11.5.2`,
  konsistent mit Root `package.json` und CI.
- **AUFG-04-04 `uv sync`-Hinweis in README:** ✅ erledigt.
  `README.md:35-37` erklärt die `--all-packages`-Pflicht explizit.
- **AUFG-04-05 Biome-Extension im DevContainer:** ✅ erledigt.
  `.devcontainer/devcontainer.json:22` enthält `biomejs.biome`, plus
  passende `editor.defaultFormatter`-Settings für TS/TSX
  (`.devcontainer/devcontainer.json:47-52`).
- **AUFG-04-06 Pre-commit-DX Fastpath:** ✅ erledigt.
  `docs/development/deployment-guide.md:195-228` dokumentiert den
  `SKIP=…`-Fastpath mit klaren Regeln (CI bleibt autoritativ, `just check`
  vor Push Pflicht).
- **AUFG-04-07 Architecture-Exceptions-Doppelquelle:** ✅ erledigt.
  CI führt `check_exception_baseline.py --check-sync` aus
  (`ci.yml:115-116`); Sync zwischen `pyproject.toml` und CONSTRAINTS.md
  §7 ist jetzt maschinell erzwungen.

## Aufgaben

### [AUFG-04-08] TECH_STACK.md SSOT-Versionen mit pyproject.toml synchronisieren
**Priorität:** Hoch
**Bereich:** Docs / DX
**Kontext:** `docs/_shared/TECH_STACK.md` ist laut CONSTRAINTS.md §8 die
autoritative Quelle für Technologie-Entscheidungen. Zahlreiche Pins und
Abhängigkeitsaussagen sind jedoch deutlich hinter den tatsächlichen
`pyproject.toml`-/`apps/api/pyproject.toml`-Werten zurück:
- `pydantic-ai >=1.93` vs. tatsächlich `pydantic-ai-slim[...] 2.0.0`
  (inkl. überholter Migration Notes für 1.x).
- `mem0 >=1.0` vs. `mem0ai 2.0.10` (ADR-033 + 2.0.x).
- `TaskIQ [redis] >=0.11.0` vs. `taskiq 0.12.4 / taskiq-redis 1.2.3 /
  taskiq-fastapi 0.5.0`.
- `PyJWT >=2.10` vs. `2.13.0`, `argon2-cffi >=23.1.0` vs. `>=25.1.0`,
  `structlog >=25.5` vs. `26.1.0`, `pydantic-settings >=2.13` vs.
  `2.14.2`, `Pydantic v2 >=2.12` vs. `2.13.4`, `FastAPI >=0.135` vs.
  `0.138.1`.
- **Fehlerhaft:** `fastapi-limiter >=0.1.6` (Zeile 193-195) wird nicht
  verwendet; Code nutzt `pyrate-limiter >=4,<5` direkt über
  `_app/rate_limiter_dep.py` (22 Treffer in `apps/api`). Auch die
  „Explicitly NOT Used"-Zeile slowapi→fastapi-limiter (Zeile 356) ist
  irreführend, da fastapi-limiter selbst nicht aktiv ist.
- **Modell-Drift:** `GLM-5.1 (z.ai)` (Zeile 97) — aktuell ist GLM-5.2.
- **Pre-commit-Angabe:** „Runs: check_architecture.py, ruff, pyright,
  bandit, test subset" (Zeile 322-324) — tatsächlich 27 Hooks.
DX-Risiko: Neueinsteiger und AI-Agenten treffen Fehlannahmen über
pydantic-ai-Version (1.x vs. 2.x sind inkompatibel), Rate-Limiter-
Architektur und Agenten-Statistik.
**Akzeptanzkriterien:**
- [ ] Alle Versions-Pins in TECH_STACK.md sind mit aktuellem
      `pyproject.toml` / `apps/api/pyproject.toml` / `packages/web/package.json`
      synchron oder dokumentiert bewusst „Minimum seit X".
- [ ] `fastapi-limiter`-Erwähnungen durch `pyrate-limiter` ersetzt;
      Architecture-Hinweis auf `_app/rate_limiter_dep.py` aufgenommen.
- [ ] „Explicitly NOT Used"-Tabelle ist konsistent (slowapi-Ersatz ist
      pyrate-limiter direkt, nicht fastapi-limiter).
- [ ] Modellbezeichnungen (z. B. GLM-5.1 → GLM-5.2) werden aktuell
      gehalten oder als Beispiele markiert.
- [ ] Pre-commit-Abschnitt spiegelt die tatsächlichen 27 Hooks oder
      verweist explizit auf `.pre-commit-config.yaml` als SSOT.
- [ ] Optional: ein `check_tech_stack_drift`-Skript (oder Erweiterung
      von `check_doc_drift.py`) vergleicht maschinell TECH_STACK.md-Pins
      gegen pyproject.toml.
**Geschätzter Aufwand:** M

### [AUFG-04-09] Layer-AGENTS.md mit aktueller Architektur synchronisieren
**Priorität:** Mittel
**Bereich:** Docs / AI / DX
**Kontext:** Die Layer-spezifischen AGENTS.md-Dateien enthalten teils
überholte Beispiele und Statistiken, die der Code-Realität und den
SSOT-Docs widersprechen:
- `packages/core/AGENTS.md:97-103`: listet nur 6 „Bestehende Agents"
  (ChapterSummary, Draft, Outline, Review, KB, WritingGraph).
  Tatsächlich leben 26 produktive NarrareAgent-Subtypen in
  `core/agents/` (Review 03: inkl. Chat, KBDiverse, KBAssist, KBImprove,
  KBMerge, Extraction, Readability, Timeline, CharacterArc,
  TemporalExtraction, FactExtractor, Consistency, StorySuggest,
  Coreference, BetaReader, Worldbuilding, PreferenceAnalysis,
  PromptLiveTest, CharacterVoice, POVDetection, InlineSuggest,
  WikiGeneration, WikiChapter).
- `tests/AGENTS.md:49-62`: MagicMock-Beispiel für `MockLLMGateway`.
  ADR-030 und testing-standards verbieten bare MagicMock für Domain-
  Dependencies; Fake-basierte Testkultur ist Standard.
- `tests/AGENTS.md:75-79`: `Base.metadata.create_all()`-Fixture.
  Widerspricht RULE-14 und Integration-Test-Setup (echte Alembic-
  Migrationen).
- `tests/AGENTS.md:111-120`: Architecture-Constraint-subprocess-Test.
  `check_architecture.py` läuft heute als Pre-commit + CI-Job, nicht
  als pytest-Subprocess.
**Akzeptanzkriterien:**
- [ ] `packages/core/AGENTS.md` „Bestehende Agents"-Liste enthält alle
      26 produktiven NarrareAgent-Subtypen oder verweist auf
      `agents/__init__.py` als SSOT (statt eine händische Teilliste zu
      pflegen).
- [ ] `tests/AGENTS.md`-Beispiele verwenden Fake-Klassen (siehe
      testing-patterns.md / tests/fakes/) statt bare MagicMock, oder
      dokumentieren explizit, dass `MagicMock(spec=...)` nur für
      Nicht-Domain-Infrastruktur erlaubt ist.
- [ ] `Base.metadata.create_all()`-Beispiel durch Alembic-Migrations-
      Fixture ersetzt (oder entfernt, falls conftest das bereits
      abdeckt).
- [ ] Architecture-Constraint-subprocess-Test-Beispiel durch Hinweis
      auf Pre-commit-Hook + CI-Job ersetzt.
- [ ] SSOT-Disziplin beibehalten: AGENTS.md verweist auf CONSTRAINTS.md
      statt Regeln zu reproduzieren.
**Geschätzter Aufwand:** S–M

### [AUFG-04-10] ADR-Dateinamen-Konvention vereinheitlichen
**Priorität:** Niedrig
**Bereich:** Docs / DX / Tooling
**Kontext:** In `docs/architecture/decisions/` tragen 50 Dateien das
`ADR-XXX-name.md`-Format, aber 7 Dateien (017, 019, 025, 043, 052, 053,
054) verwenden das reine `XXX-name.md`-Format ohne `ADR-`-Präfix.
INDEX.md referenziert sie mit `ADR-XXX`-Label, aber die Dateinamen
sind uneinheitlich. Glob-Muster wie `ADR-*.md` oder Auto-Linker
verfehlen diese 7 Dateien; das ist eine DX- und Tooling-Konsistenzlücke
(kein fachlicher Blocker).
Betroffen: `017-embedding-cascade.md`, `019-system-prompt-consistency.md`,
`025-feature-adoption-infrastructure.md`, `043-ai-interaction-primitives.md`,
`052-session-stop-recovery.md`, `053-ai-session-lifecycle.md`,
`054-inline-feature-prompt-debt-migration.md`.
**Akzeptanzkriterien:**
- [ ] Alle ADR-Dateien folgen derselben Namenskonvention
      (`ADR-XXX-name.md`), oder die abweichenden 7 werden bewusst als
      „historisch, nicht umbenennen" markiert (z. B. in INDEX.md
      dokumentiert).
- [ ] Bei Umbenennung: INDEX.md, alle Querverweise in CURRENT_STATE.md,
      Feature-Specs, .opencode/context und anderen ADRs werden
      aktualisiert.
- [ ] Optional: ein `scripts/check_adr_naming.py` validiert die
      Namenskonvention maschinell.
**Geschätzter Aufwand:** S

### [AUFG-04-11] Lookup-Kontextdateien synchronisieren oder automatisch aus SSOT generieren
**Priorität:** Mittel
**Bereich:** Docs / DX / AI
**Kontext:** `.opencode/context/narrare-dev/lookup/{current-state,
tech-stack}.md` sind als Priority critical markiert und spiegeln die
SSOT-Docs CURRENT_STATE.md und TECH_STACK.md wider. Beide sind
deutlich stale (Beispiele siehe Review 04 Abschnitt 5.3): Graph 15.527
vs. 26.084 Nodes, 4.273 vs. 9.043 Backend-Tests, 38 vs. 0 Frontend-
Violations, 18 vs. 26 AI-Agents, 50 vs. 56+ ADRs, fastapi-limiter
vs. pyrate-limiter, pydantic-ai 1.93 vs. 2.0.0, „9 hooks" vs. 27
Hooks. AI-Agenten, die diese Kontextdateien als Erstes laden,
arbeiten mit falschen Annahmen. Überschneidet mit AUFG-02-04
(testing-standards, deployment-guide, quality-gates) und AUFG-04-08
(TECH_STACK SSOT), ist aber ein eigenes Skalierungsproblem der
abgeleiteten Kontextdateien.
**Akzeptanzkriterien:**
- [ ] `lookup/current-state.md` ist mit aktuellem Graph (`just
      code-review-graph list-graph-stats`), Test-Counts (`just test
      --collect-only -q`), Agent-Count (Review 03) und ADR-Index
      synchron oder verweist explizit auf „run `just …` for current".
- [ ] `lookup/tech-stack.md` ist mit TECH_STACK.md (nach AUFG-04-08)
      synchron, insbesondere ohne fastapi-limiter/pdantic-ai 1.x/
      „9 hooks"-Drift.
- [ ] Optional evaluiert: Können die lookup-Dateien (oder Teile davon)
      automatisch aus SSOT generiert werden (z. B. via
      `scripts/sync_extracted_context.py`)? Falls ja, wird die
      manuelle Pflege ersetzt; falls nein, wird ein Reviewer-Cadence
      dokumentiert.
- [ ] `check_doc_drift.py` deckt diese Lookup-Dateien ab und warnt
      konkret, wenn sie gegenüber der SSOT-Quelldatei zurückliegen.
**Geschätzter Aufwand:** M

---

## Handoff an den Coordinator

**DX-/Tooling-Gesamtbewertung:** ⭐⭐⭐⭐ — Solide, moderne DX mit
vorbildlicher Toolchain, DevContainer, Agenten-/Skill-Infrastruktur
und Quality-Gate-Automatisierung. Alle alten AUFG-04-01 bis AUFG-04-07
sind erledigt. Die aktuelle Schwäche liegt in der Dokumentations-SSOT-
und abgeleiteten-Kontext-Drift.

**Wichtigste Befunde (Kurzfassung):**
1. **Setup-Prozess (`just dev-setup`, README, DevContainer)**
   vorbildlich; alter Node/pnpm/Biome/Fastpath/Exception-Sync-Bestand
   erledigt.
2. **pyproject.toml sauber und maschinell synchronisiert** (Exception-
   Sync via `check_exception_baseline.py --check-sync` in CI).
3. **TECH_STACK.md als autoritative SSOT hat stale Version-Pins und
   eine falsche Rate-Limiter-Aussage** (`fastapi-limiter` wird nicht
   verwendet; Code nutzt `pyrate-limiter` direkt) — AUFG-04-08.
4. **CURRENT_STATE.md** listet 20 AI agents (tatsächlich 26) und
   ADR-001–051 (tatsächlich bis ADR-056); interne Statistik-Drift
   (Review 00 CTX-003 vertieft).
5. **Extrahierte Kontextdateien** (`processes/quality-gates.md`,
   `lookup/{current-state,tech-stack}.md`, `guides/deployment.md`)
   sind deutlich stale: 60%-Coverage-Claim (tatsächlich 80% blockierend),
   Phantom-Befehl `just dev-up` (existiert nicht), 7-job-CI (tatsächlich
   9), „9 pre-commit hooks" (tatsächlich 27). Überschneidet mit
   AUFG-02-04 und neuem AUFG-04-11.
6. **Layer-AGENTS.md** (packages/core, tests) enthalten teils überholte
   Beispiele (MagicMock vs. Fake, `Base.metadata.create_all()` vs.
   Alembic, 6 vs. 26 Agents) — AUFG-04-09.
7. **ADR-Dateinamen inkonsistent**: 7 von 57 Dateien ohne `ADR-`-Präfix
   — AUFG-04-10 (klein).
8. **Code-Graph-First** war in dieser Session stabil; operatives
   Risiko bleibt, falls der MCP-Server ausfällt.
9. **Governance Health** meldet 507 Doc-Drift-Warnungen (nicht blockierend,
   aber sichtbar) — die Maschinendisziplin arbeitet; das Beheben ist
   Follow-up.

**Aufgaben-IDs:** AUFG-04-08 (Hoch, Docs/DX — TECH_STACK SSOT),
AUFG-04-09 (Mittel, Docs/AI/DX — Layer-AGENTS.md), AUFG-04-10 (Niedrig,
Docs/DX/Tooling — ADR-Namenskonvention), AUFG-04-11 (Mittel, Docs/DX/AI
— Lookup-Kontextdateien). Überschneidungen mit AUFG-02-04 (testing-
standards/deployment-guide/quality-gates.md) sind dokumentiert;
Coordinator kann bei der Terminierung abstimmen.

**Geänderte Dateien:** Nur
`_audit/results/technical-review/review-04-dx-tooling.md` (diese Datei).
Kein Code-Change, kein Commit, kein `--no-verify`.

**Blocker / Unsicherheiten:**
- Keine harten Blocker für nachfolgende Reviews.
- Alle frischen Checker-Läufe (`just check-architecture`, `just
  check-python-size`, `just check-frontend-size`, `just check-health`,
  `just check-governance`) waren in dieser Session verfügbar und
  ausgewertet. Vollständige Unit-/Integration-/E2E-Suites wurden nicht
  erneut ausgeführt; Evidenz aus Review 02 übernommen.
- Code-Graph-MCP war stabil; falls er in Review 05 ausfällt, sind die
  Graph-basierten Befunde dieser Review-Serie nicht reproduzierbar ohne
  Fallback.
- Die 507 Doc-Drift-Warnungen aus `just check-governance` wurden nicht
  einzeln validiert; Stichproben bestätigen die SSOT-Driftthese
  (Abschnitt 5). Voll-Validierung wäre eigener Auftrag.

**Review 05 kann starten.** Wichtige Kontextmitnahmen:
- Dokumentations-SSOT-Drift ist das Haupt-DX-Thema (AUFG-04-08,
  AUFG-04-09, AUFG-04-11; Überschneidung AUFG-02-04).
- CI/CD-Pipeline ist 9 Jobs, nicht 7 wie in abgeleiteten Doks beschrieben.
- Pre-commit hat 27 Hooks, nicht 9.
- Setup-Prozess, DevContainer und Toolchain sind vorbildlich und
  können als Referenz für Release-Doku dienen.
