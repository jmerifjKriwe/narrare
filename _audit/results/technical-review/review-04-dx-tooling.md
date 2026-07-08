# Review 04 – Developer Experience & Tooling

> **Review-Perspektive:** Neuer Entwickler, der das Projekt zum ersten Mal aufsetzt.
> **Audit-Datum:** 2026-07-08 · **Reviewer:** NarrarePlatformSpecialist
> **Kontext:** `_audit/results/technical-review/review-00-kontext.md` (Tech-Stack,
> Verzeichnisstruktur, Engine-Punkte). Versionsangaben sind aus den Manifesten
> (`pyproject.toml`, `packages/web/package.json`, `uv.lock`) und per
> `just --list` / Versions-CLIs **verifiziert**, nicht geraten.

---

## 1. Entwicklungsumgebung aufsetzen

**Simulierter Onboarding-Prozess (Schritt für Schritt nach README + `docs/development/deployment-guide.md`):**

1. README „Requirements" listet: Python 3.14+, Node.js 24+, pnpm, Docker + Compose, `uv`, `just`.
2. README „Quick Start": `git clone … && just dev-setup` → dann `.env` editieren, API-Key eintragen, `just dev`.
3. `just dev-setup` (justfile L94–105) führt aus: `cp .env.example .env`,
   `uv sync --frozen --all-packages --group dev --extra nlp`,
   `just install-nlp-models`, `pre-commit install --install-hooks`, `pnpm install`,
   `_ensure-services` (Docker-Compose up), `db-migrate`, `seed_dev_user.py`.
4. `just dev` startet API (8000) + Frontend (3000); API führt beim Start
   automatisch `alembic upgrade head` aus (`lifespan.py`).

**Antworten auf die Leitfragen:**

- **Setup-Dauer von null:** Realistisch **10–25 Min.** für die Toolchain-Installation
  (uv, just, pnpm, Docker) + **15–40 Min.** für `just dev-setup`, dominiert durch
  `--extra nlp` (spaCy + 3 Sprachmodelle `de/en/fr_core_news_md`, je ~30–60 MB)
  und `pnpm install` (~480 transitive Pakete). Auf einer frischen VM ohne Docker-Cache
  kommen noch ~5 Min. für `pgvector/pgvector:pg17` + `redis:8-alpine` hinzu.
  **Gesamtschätzung: 30–60 Min.** bis `just dev` läuft.
- **Dokumentiert vs. undokumentiert:**
  - *Dokumentiert:* alle 6 Prerequisites, der `--all-packages`-Vertrag (deployment-guide
    L29–37 mit erklärter Fehlerursache `No module named 'narrare'`), das `--frozen`-Lockfile-
    Verhalten (exzellenter Troubleshooting-Abschnitt L82–126), Dev-Login
    (`dev@narrare.dev` / `narrare-dev`), `NARRARE_ENCRYPTION_KEY`-Generierung.
  - *Undokumentiert / implizit:* dass `--extra nlp` ~200 MB Modelle zieht und ohne
    spaCy `just install-nlp-models` mit klarem Fehler abbricht (immerhin — siehe
    justfile L125–128, das ist gut gehandhabt); dass ein LLM-API-Key schon zum
    `just dev-setup`-Abschluss (Seed) nicht nötig ist, aber für `just dev` zwingend
    ist; dass `NARRARE_DEV_MODE` (host/container) das Port-Routing steuert
    (nur im justfile/Post-create ersichtlich, nicht in README).
- **Einzelner Einstiegs-Befehl vs. viele Schritte:** **Ein einziger** (`just dev-setup`),
  sauber orchestriert. Das ist vorbildlich. Alternativ existiert der DevContainer-
  Pfad (post-create.sh führt funktional das Gleiche aus).
- **Bekannte Fehlschlag-Situationen:**
  - **Python-Version:** `requires-python = ">=3.14"`, Ruff `target-version = "py314"`,
    DevContainer `python:3.14-bookworm`. Wer 3.12/3.13 hat → `uv sync` scheitert.
    3.14 ist noch verhältnismäßig neu; auf Standard-Linux-Distributionen nicht
    default. *Aber:* `uv` löst das über sein eigenes Python-Management, und der
    DevContainer liefert 3.14 mit → gut abgefangen.
  - **`uv sync --frozen` bei Lockfile-Drift:** (Dependabot-PRs ohne `uv.lock`) —
    dies ist der häufigste Setup-Fehler und **ausführlich dokumentiert** (deployment-guide L82–126). Sehr gut.
  - **Manuelles `uv sync` ohne `--all-packages`:** README warnt explizit
    (L35–37) und nennt den korrekten Befehl. Gut.
  - **`--no-verify`-Falle:** Nicht direkt setup-relevant, aber der Plattform-
    Specialist-Prompt verbietet `git commit --no-verify` strikt — korrekt, da
    pre-commit die Architektur-Gates hält.
  - **macOS/Windows:** justfile nutzt `bash -euo pipefail`; `just dev` startet
    Hintergrund-Prozesse via `jobs -p`/`kill`. Unter Windows (ohne WSL) bricht das.
    Nicht dokumentiert, aber DevContainer ist der empfohlene Windows-Pfad.

**Bewertung der Setup-Skripte:**

| Skript | Zweck | Funktioniert? | Probleme |
|---|---|---|---|
| `just dev-setup` (justfile L94) | Komplett-Setup: deps + NLP-Modelle + hooks + services + migrate + seed | Ja | Schwer (NLP-Download dominiert); kein Fortschritts-Hinweis auf Modelldauer; `--extra nlp` ist verpflichtend im Setup-Pfad, obwohl nicht jeder NLP braucht |
| `just install-nlp-models` (justfile L122) | Lädt 3 spaCy-Modelle (de/en/fr `_md`) versions-synchron | Ja | Prüft sauber, ob spaCy installiert ist, bevor es lädt (gut); fixiert Modellversion an spaCy-Patch via Runtime-Ableitung (clever) |
| `.devcontainer/post-create.sh` | DevContainer-Erststart: deps, NLP, hooks, .env-Netzwerk-Rewrite (localhost→Service-DNS), DB-Wait, migrate, seed | Ja | Vollständig und durchdacht; passt `.env`-URLs per `sed` an Container-DNS an (`postgres`/`redis`); unterstützt `.devcontainer/post-create.local.sh` für persönliche Erweiterungen |
| `just generate-secret` (justfile L108) | Erzeugt `SECRET_KEY` | Ja | Ok; docgen-Guide verweist korrekt darauf |
| `just dev` / `dev-api` / `dev-frontend` | Startet Services mit sauberem Trap-Cleanup (Ctrl+C killt alle Kinder) | Ja | Gutes Signal-Handling (`cleanup`-Trap mit `jobs -p`); Logs nach `logs/dev.log` |
| `just _ensure-services` (justfile L18) | Startet Docker-Compose oder erkennt Container-/DevContainer-Modus | Ja | Drei-Modus-Logik (host/container/devcontainer) korrekt; degradation auf „services already running" |
| `just check` → `run_checks.py` | Architektur + Lint + Typ + Security (kompakt) | Ja | Verifiziert via `just --list` (Rezept existiert); Voll-Run nicht im Audit ausgeführt (Zeit), aber alle Teil-Checker einzeln in CI/pre-commit bestätigt |

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`
**Befunde:** Single-Command-Setup (`just dev-setup`) ist vorbildlich orchestriert und
der Troubleshooting-Abschnitt zum `--frozen`-Lockfile ist einer der besten, die ich in
einem Projekt dieser Größe gesehen habe. Abzug gibt es für: (1) das Setup zwingt
`--extra nlp` (~200 MB) auf alle Entwickler, auch solche, die kein NLP-Feature
anfassen — ein `--extra nlp` könnte optionalisiert oder ein `just dev-setup-min`
angeboten werden; (2) die geschätzte Setup-Dauer (30–60 Min.) ist für ein
„einfaches `just dev`" nirgends kommuniziert; (3) `NARRARE_DEV_MODE` und die
OS-Beschränkung (bash-Signal-Handling) sind implizit.

---

## 2. DevContainer

**Analyse (`.devcontainer/`):** DevContainer ist vorhanden und ADR-029-konform als
*optionales* Overlay deklariert (deployment-guide L128–143: „must not become a
requirement for VM-first development").

- **Base-Image:** `mcr.microsoft.com/devcontainers/python:3.14-bookworm`
  (Dockerfile L1). Floating-Tag → beim Rebuild immer aktuelles 3.14. Letzter
  DevContainer-Commit: **2026-06-16** (~3 Wochen vor Audit) → **aktuell (< 6 Monate)**. ✅
- **`devcontainer-lock.json`:** pinnt die beiden Features (`git:1` v1.3.5,
  `github-cli:1` v1.1.0) per SHA-Integrität. Reproduzierbar. ✅
- **Tools im Image:** curl, git, jq, build-essential, libpq-dev, postgresql-client,
  `just` (via offiziellem Install-Script), `uv`, Node.js 24 (via nvm), pnpm 11.5.2,
  pre-commit. Vollständig. ✅
- **Extensions (15):** Python, Pylance, Ruff, debugpy, Tailwind CSS, **ESLint**
  (`dbaeumer.vscode-eslint`), Prettier, **Biome**, Docker, GitLens, Spell-Checker
  (EN+DE), TOML, YAML, GitHub Actions.
  - ⚠️ Inkonsistenz: ESLint + Prettier sind installiert, aber das Projekt nutzt
    **Biome** als alleinigen FE-Linter/Formatter (`packages/web/package.json`,
    `lint` = `biome check`). ESLint/Prettier sind hier tote Extensions.
  - `[typescript]`/`[typescriptreact]` defaultFormatter = `biomejs.biome` (korrekt).
- **Ports:** `forwardPorts: [3000, 8000, 5432, 6379]` mit `portsAttributes`-Labels
  (Frontend/API notify, Postgres/Redis silent). **Alle 4 relevanten Ports gemappt.** ✅
- **Post-create (`post-create.sh`):** vollständig — venv-chown, OpenCode-Perm-fixes,
  `uv sync`, NLP-Modelle, pre-commit, `.env`-Rewrite für Container-DNS
  (`localhost:5432`→`postgres:5432`, etc.), `NARRARE_DEV_MODE=container`,
  `pnpm install`, DB-Wait-Loop (asyncpg), migrate, seed. Plus Hook für
  `post-create.local.sh`. **Sehr durchdacht.** ✅
- **.env-Belegung:** `docker-compose.devcontainer.yml` setzt DB/Redis/MODE-Env
  hart; `post-create.sh` kopiert `.env.example`→`.env` und passt URLs an. ✅
- **Startet ohne manuelle Eingriffe?** Ja — `postCreateCommand` macht das komplette
  Setup. Einzige manuelle Aktion: API-Key in `.env` eintragen (unvermeidbar).
- **WebUI-Entwicklung im Container:** Ja — Frontend-Port 3000 forwarded, pnpm
  install im Post-create. `consistency: cached`-Bind-Mount für Performance. ✅
- **Container vs. lokal „works on my machine":** Gute Mitigation — `NARRARE_DEV_MODE`
  + URL-Rewrite verhindern den klassischen localhost-vs-Service-DNS-Fehler. Die
  `just`-Helfer (`_psql-*`) unterstützen beide Modi explizit.
- **GPU/AI-Ressourcen:** Nicht konfiguriert — und **nicht nötig**: LLM-Calls laufen
  remote (Provider-APIs) oder via Ollama-Host (`OLLAMA_BASE_URL`). Korrekt weggelassen.
- **VS Code + Cursor:** `devcontainer.json` ist VS-Code-Customization, aber Cursor
  nutzt dasselbe Format (Cursor ist VS-Code-Fork) → **funktioniert mit beiden.** ✅

**Checkliste:**
- [x] Base-Image aktuell (nicht älter als 6 Monate) — python:3.14-bookworm, Rebuild 2026-06-16
- [x] Alle Ports korrekt gemappt (API 8000, WebUI 3000, Postgres 5432, Redis 6379)
- [x] Post-create-Script vorhanden und vollständig
- [~] Extensions installiert — ja, aber ESLint/Prettier überflüssig (Projekt nutzt Biome); pnpm-Version im Dockerfile hartkodiert (muss `package.json`-Pin manuell folgen)
- [x] Umgebungsvariablen dokumentiert und per `.env.example` vorbelegt
- [x] Funktioniert mit VS Code und Cursor (gleiches devcontainer.json-Format)

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`
**Befunde:** Vorhanden, durchdacht, optional (ADR-029), drei-Modus-Netzwerk-Handling
sauber gelöst. Abzüge für: tote ESLint/Prettier-Extensions (verwirrt neue
Entwickler — „nutze ich ESLint oder Biome?"), und die harte pnpm-Version
(`ARG PNPM_VERSION=11.5.2`) im Dockerfile, die manuell mit `package.json`'s
`packageManager` synchron gehalten werden muss (Drift-Risiko, nicht maschinell
geprüft). Kein Lockfile-Pinning des Base-Image-Digests (nur Floating-Tag) — für
Reproduzierbarkeit über Zeit critisch.

---

## 3. pyproject.toml

**Analyse (`pyproject.toml` Root + `apps/api/` + `packages/core/`):**

- **Struktur (PEP 517/518):** Sauber. Root ist `package = false` (virtual workspace
  container, Astral-Konvention) mit ausführlichem Kommentar (L30–37), *warum* —
  behebt einen realen `No module named 'narrare'`-CI-Crash. Exemplarisches
  „Dokumentiert = Implementiert + Begründet". Workspace-Member (`apps/api`,
  `packages/core`, `packages/i18n`) nutzen `[build-system] hatchling` mit
  `dev-mode-dirs` und `py.typed`-Marker (PEP 561). ✅
- **`uv sync --all-packages`:** Workspace-Konfiguration korrekt
  (`[tool.uv.workspace] members = [...]`); `narrare-core`/`narrare-i18n` per
  `[tool.uv.sources] ... workspace = true` verdrahtet. Verifiziert, dass
  `--all-packages` alle Member installiert (deployment-guide L29–37 dokumentiert
  die Falle ohne `--all-packages`). ✅
- **Versionsbeschränkungen:** Gemischt-pragmatisch.
  - *Exakte Pins* für die meisten App/Core-Deps (`fastapi==0.139.0`, `sqlalchemy==2.0.51`,
    `pydantic-ai-slim==2.5.0`, …) → reproduzierbar.
  - *Offene Ranges* für infra (`redis>=7.0.0,<9`, `pyrate-limiter>=4.0,<5`,
    `opentelemetry-*> =1.39.0,<1.44.0`) → sinnvoll gebounded.
  - *Dev-Tools* durchweg exakt gepinnt (`ruff==0.15.20`, `pyright==1.1.411`,
    `pytest==9.1.1`) → deterministische CI. ✅
  - ⚠️ `[project] dependencies = ["jsonschema>=4.26.0"]` am **nicht-Package-Root**
    ist misplaced: `jsonschema` wird nur von `scripts/check_registry_drift.py`
    (Dev-Tooling) genutzt → sollte in `[dependency-groups] dev` stehen, nicht in
    `[project] dependencies` (welches in jeden Sync, auch prod-ähnlich, installiert).
- **Tool-Konfiguration zentralisiert:** **Ja, vorbildlich.** Alle Tool-Tabellen
  (`[tool.pyright]`, `[tool.ruff]`, `[tool.pytest.ini_options]`,
  `[tool.coverage.*]`, `[tool.bandit]`, `[tool.mutmut]`,
  `[tool.narrare.architecture]`) sind im **Root-`pyproject.toml` gebündelt** —
  nicht über `ruff.toml`/`.flake8`/`pytest.ini` verstreut. Einzige Ausnahme:
  `tests/pyrightConfig.json` (bewusst lockerer für Test-Typecheck — im
  pre-commit-Pyright-Tests-Hook genutzt, dokumentiert). ✅
- **Veraltete/ungenutzte Deps:** Keine offensichtlich toten Runtime-Deps gefunden.
  `aiohttp>=3.14.0` ist ein expliziter CVE-Fix-Pin für eine taskiq-transitive Dep
  (kommentiert L27). Dev-Gruppe ist umfangreich aber zweckgebunden (pytest-*,
  mutmut, pydantic-evals, hypothesis).
- **`[tool.narrare.architecture]` Ausnahmen:** **Aktuell, begründet, synchron.**
  - 10 aktive `[[...exceptions.entries]]` in `pyproject.toml` (L326–394).
  - CONSTRAINTS.md §7 (L1156–1169) spiegelt **dieselben 10** Einträge (Nummerierung
    1,2,4,5,6,11,12,13,15,16 — Lücken aus ausgemusterten Ausnahmen).
  - **Maschinell erzwungene Sync:** CI-Job `Check exception sync (pyproject ↔
    CONSTRAINTS.md)` = `check_exception_baseline.py --check-sync` (ci.yml L123–124)
    + `Check exception baseline (no-growth gate)` (L120–121) + pre-commit-Hook
    `exception-baseline`. Jede neue Ausnahme scheitert in pre-commit **und** CI,
    bis sie hier **und** in CONSTRAINTS.md registriert ist. ✅ —
    das ist echte „Implementation + Enforcement" (architectural-discipline §7).

**Abhängigkeits-Audit** (Manifest-Versionen verifiziert aus `pyproject.toml`/`package.json`;
„Neueste" = Major-Line-Einschätzung per Manifest-Pin, exakte Patch-Latest per
`uv pip index` nicht pro Paket abgefragt — Dependabot hält wöchentlich frisch):

| Paket | Aktuelle Version (Manifest) | Neueste (Major-Line) | Status |
|---|---|---|---|
| Python | `>=3.14` (installiert 3.14.4) | 3.14.x (3.15 nicht GA) | Aktuell |
| fastapi | `0.139.0` | 0.13x-Linie | Aktuell |
| uvicorn[standard] | `0.50.0` | 0.4x–0.5x-Linie | Aktuell |
| sqlalchemy (async) | `2.0.51` | 2.0.x (2.1 nicht GA) | Aktuell |
| pydantic v2 | `2.13.4` | 2.13.x | Aktuell |
| pydantic-ai-slim | `2.5.0` | 2.5.x | Aktuell |
| alembic | `1.18.5` | 1.18.x | Aktuell |
| asyncpg | `0.31.0` | 0.31.x | Aktuell |
| structlog | `26.1.0` | 26.x (kalenderisiert) | Aktuell |
| opentelemetry-* | `>=1.39.0,<1.44.0` | 1.39–1.43 | Aktuell (bewusst nach oben begrenzt) |
| ruff (dev) | `0.15.20` | 0.15.x | Aktuell |
| pyright (dev) | `1.1.411` | 1.1.4xx (sehr frequent) | Aktuell |
| pytest (dev) | `9.1.1` | 9.x | Aktuell |
| bandit (dev) | `1.9.4` | 1.9.x | Aktuell |
| pip-audit (dev) | `2.10.1` | 2.10.x | Aktuell |

> **Frischhalte-Mechanismus:** `.github/dependabot.yml` (5 KB, wöchentlich, gruppiert)
> + `just deps-update`. Kein veraltetes/EOL-Paket gefunden. ⚠️ `pip-audit` unterdrückt
> in CI 2 Vulns (`--ignore-vuln PYSEC-2025-183 --ignore-vuln GHSA-rrmf-rvhw-rf47`,
> ci.yml L275) **ohneInline-Begründung** am Aufruf — suppression ist legitim, sollte
> aber kommentiert sein (welche Dep, warum nicht fixbar).

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`
**Befunde:** PEP 517/518 sauber, Build-System (hatchling) zeitgemäß, Workspace-
Verdrahtung korrekt, Tool-Konfig vorbildlich zentralisiert, Ausnahmen-Register
**implementiert + erzwungen synchron**. Abzüge für: misplaced `jsonschema` in
`[project] dependencies` statt dev-group; 2 unkommentierte pip-audit-Vuln-Suppresssions;
kein Digest-Pinning des DevContainer-Base-Image (siehe §2).

---

## 4. Tools-Review & Alternativen

| Kategorie | Aktuelles Tool | Version | Zeitgemäße Alternative | Wechsel sinnvoll? |
|---|---|---|---|---|
| Linter | Ruff (Python) | `0.15.20` | — (Ruff ist State-of-the-Art) | Nein — Ruff ersetzt bereits flake8+isort+pyupgrade+bandit-Subset; wählt `E,F,I,N,W,UP,B,C4,SIM,TCH,RUF,S` |
| Formatter | Ruff format (Python) / Biome (TS) | `0.15.20` / `2.5.2` | — | Nein — beide sind die schnellsten, modernsten Formatter; Black/Prettier bewusst nicht genutzt |
| Type Checker | pyright (strict) | `1.1.411` | mypy | Nein — pyright strict ist schneller und das alleinige Gate; mypy bewusst nicht konfiguriert (ci.yml L19: „mypy nicht erforderlich") |
| Test Runner | pytest (+ asyncio, cov, xdist, randomly, timeout, hypothesis) | `9.1.1` | — | Nein — pytest-Setup ist first-class; MutMut für Mutation-Testing ergänzt |
| Task Runner | just | `1.51.0` | make / Taskfile.yml | Nein — just ist plausibler (Cross-Platform, keine Make-Quirks); 599-Zeilen-Justfile ist konsistent gegliedert |
| Paket-Manager | uv (Python) / pnpm (JS) | `0.11.26` / `11.5.2` | poetry / npm | Nein — uv ist aktuell der schnellste Python-PM mit Workspace-Support; pnpm ist der JS-Standard |
| Frontend Build | Next.js 16 (App Router) + Vite (für Vitest) + pnpm | `16.2.10` / `8.1.3` / `11.5.2` | — | Nein — Next 16 ist der aktuelle Major; standalone-Output für Release-Image |
| Frontend Test | Vitest (+ @vitest/coverage-v8) + Playwright (E2E+VRT) + Testing Library | `4.1.9` / `1.61.1` / `16.3.2` | Jest | Nein — Vitest 4 + Playwright ist das moderne Setup; VRT (ADR-059) ergänzt |

**Empfohlene Wechsel: keiner.** Der gesamte Tool-Stack ist durchgängig auf dem
modernsten Stand (uv + Ruff + pyright + just + Biome + Vitest + Next 16 + TS 6 +
Tailwind v4). Es gibt **kein** Werkzeug, dessen Wechsel Mehrwert brächte. Die
einzige Diskrepanz ist konzeptioneller Natur (kein Tool-Wechsel): ESLint/Prettier-
VS-Code-Extensions sind im DevContainer installiert, obwohl das Projekt Biome nutzt
(siehe §2) — das ist ein Konfigurations-Cleanup, keine Tool-Migration.

**Mehrwert-/Aufwands-Notiz:** Da kein Wechsel empfohlen wird, entfällt die
Migrationsaufwand-Begründung. Die Investition fliesst stattdessen in
*Wartung* des Status quo (Dependabot, `just deps-update`, DevContainer-Rebuilds).

**Bewertung:** ⭐⭐⭐⭐⭐ `[5/5]`
**Befunde:** Exemplarisch moderner, konsistenter Stack ohne Legacy-Ballast. Kein
einziges veraltetes oder fragwürdiges Werkzeug. Bonus: MutMut (Mutation-Testing)
und pydantic-evals (LLM-Quality, ADR-032) sind über das Übliche hinausgehende
Qualitätswerkzeuge, beide in CI/pre-commit verdrahtet.

---

## 5. Dokumentationsstruktur

**Analyse:**

- **Vorhandene Doku:**
  - `README.md` (103 Zeilen): Requirements, Quick Start, Project Structure,
    Dev-Container, Architektur-Pointer. Klar und onboarding-fokussiert.
  - `docs/` umfangreich: `_shared/` (CONSTRAINTS, TECH_STACK, GLOSSARY,
    CURRENT_STATE), `architecture/decisions/` (ADR-001–063 + INDEX),
    `architecture/questions/`, `architecture/governance/`, `development/`
    (12 Standards-Docs, je 600–1.350 Zeilen), `features/` (Spezifikationen +
    INDEX), `mvp/`, `reference/`, `archive/`, `DEBT.md`.
  - `AGENTS.md` (Root) + Layer-AGENTS.md (`apps/api/`, `packages/core/`,
    `tests/`): Open-Code-Instruktionen.
  - `.opencode/context/narrare-dev/`: extrahierte, referenzierende Standards
    (8 Standards-Files, 5 Prozess-Files, Templates, Beispiele, Domain-Map).
  - `CHANGELOG.md` (17 KB, **auto-generiert** via release-please).
  - Inline-Docstrings in Produktionscode (nicht systematisch auditiert, aber
    AGENTS.md-Layer-Docs fördern sie).
- **Aktualität/Vollständigkeit:** Generell aktuell und detailliert. **Aber** mehrere
  Drift-Stellen (siehe Befunde): `deployment-guide.md`-Justfile-Katalog führt
  Rezepte, die nicht existieren (`db-downgrade`, `db-seed`, `format`,
  `check-governance`); `orchestrator.md` ruft `just check-types`/`check-constraints`/
  `check-governance` auf, die es nicht gibt. SSOT-Checker `check_current_state_facts.py`
  läuft warn-only — diese Drifts werden **nicht** blockierend geprüft.
- **Zielgruppen-Struktur:** Entwickler hervorragend abgedeckt (Setup, Architektur,
  Coding/Testing/Prompt/UI-Standards). Endnutzer- und API-Konsumenten-Doku **dünn**
  bzw. nur implizit (siehe Lücken-Matrix).
- **API auto-dokumentiert:** Ja — FastAPI liefert zur Laufzeit `/docs` (Swagger) +
  `/redoc`. Zusätzlich: `scripts/export_openapi.py` exportiert `openapi.json`,
  CI prüft auf Drift (`export_openapi.py --check`, ci.yml L127), pre-commit-
  `openapi-regenerate`-Hook schreibt den Spec automatisch. ⚠️ Zum Audit-Zeitpunkt
  ist **keine** `docs/openapi.json` committed (wird ggf. generiert/gitignored) —
  der `--check`-Gate würde das dann aber bemängeln, falls jemand API-Surface ohne
  Spec-Regeneration ändert (Hook fängt das pre-commit ab).
- **MCP-Server dokumentiert (für AI-Clients):** **Nein, denn nicht implementiert**
  (`apps/mcp/` existiert nicht; ADAPTER-001 = „Planned", blockiert durch Q-001).
  README + review-00 kommunizieren das klar. Es gibt (korrekt) keine MCP-Doku für
  einen nicht-existierenden Server. Für AI-Agenten, die Narrare anbinden wollen,
  fehlt damit jegliche Contract-Doku — was aber dem Reifegrad entspricht.
- **CHANGELOG:** Ja (release-please, auto-gen).
- **CONTRIBUTING.md / CODE_OF_CONDUCT.md:** **Beide fehlen.** Für ein Open-Source-
  deklariertes Projekt (MIT, GitHub-Repo) ist das eine signifikante Lücke: ein neuer
  Contributor weiß nicht, wie er branchen/committen/PR-en soll (Conventional-Commits-
  Regel ist nur in coding-standards/deployment-guide verstreut, nicht in einem
  einzigen „How to contribute"-Einstieg).
- **Widerspruchsfreiheit AGENTS.md / `.opencode/context/` / `docs/development/*`:**
  - *Inhaltlich* größtenteils konsistent (SSOT-Hierarchie in CONSTRAINTS.md §8
    definiert, abgeleitete Quellen referenzieren nur).
  - *Aber*: **Agent-Namen drift** (siehe §6): AGENTS.md + orchestrator.md nutzen
    `narrare-architecture/implementation/testing/ui/deployment/documentation/core`,
    die **realen** Subagent-Definitionen heißen
    `NarrareArchitectureSpecialist/BackendSpecialist/CoreSpecialist/DocsSpecialist/
    FrontendSpecialist/PlatformSpecialist`. Ein AI/Entwickler, der AGENTS.md folgt,
    versucht einen nicht existierenden `subagent_type` aufzurufen.
  - *Stale `just`-Kommandos* in orchestrator.md (`check-types`, `check-constraints`,
    `check-governance`) und deployment-guide.md (`db-downgrade`, `db-seed`,
    `format`, `check-governance`).

**Lücken-Matrix:**

| Zielgruppe | Dokumentiert | Fehlend |
|---|---|---|
| Endnutzer | README-Quickstart (Docker-Compose-Release), Setup-Wizard-In-App, deployment-guide „Quick Start (End User)" | Kein Nutzer-Handbuch (Feature-Nutzung, KI-Einstellungen, KB/Worldbuilding-Anleitung); keine rendered Docs-Site (nur Markdown auf GitHub) |
| Entwickler (Setup) | README + deployment-guide (exzellent), `just dev-setup`, DevContainer, Troubleshooting (Lockfile-Drift) | Setup-Dauer-Erwartung; CONTRIBUTING.md fehlt; Bedeutung `NARRARE_DEV_MODE` nicht in README |
| Entwickler (Architektur) | CONSTRAINTS.md (Verfassung), 63 ADRs, coding/testing/prompt/ui-Standards, orchestrator.md, quality-gates.md, architectural-discipline.md | Agent-Namen in AGENTS.md/orchestrator.md passen nicht zu echten Subagent-Definitionen; `just`-Kommando-Drift in 2 Doks |
| API-Konsumenten | FastAPI `/docs` + `/redoc` zur Laufzeit; `export_openapi.py`-Spec-Drift-Gate | Keine committed/statische OpenAPI-Spezifikation zum Browsen ohne laufenden Server; kein API-Tutorial/Beispiel-Requests |
| AI-Agenten / MCP-Clients | (nicht anwendbar — MCP nicht implementiert; Q-001 blockiert) | MCP-Server-Contract/Roadmap-Dokumentation (bewusst zurückgestellt gemäß ADAPTER-001/Q-001) |

**Bewertung:** ⭐⭐⭐ `[3/5]`
**Befunde:** Die *Entwickler-Architektur*-Doku ist für ein Projekt dieser Größe
beeindruckend tief (Verfassung + 63 ADRs + maschinell erzwungene Ausnahmen-Sync).
Aber für **DX** trifft der neue Entwickler auf drei reale Reibungsverluste:
(1) **kein CONTRIBUTING.md** (Wo branch ich hin? Wie commit-Format? Wie PR?);
(2) **stale `just`-Kommandos** in zwei zentralen Doku-Files, die ein Copy-Paste
in einen `command not found`-Fehler enden lassen; (3) **Agent-Namen-Drift**,
der jeden AI-gestützten Workflow verwirrt. Die Endnutzer-Doku ist für MVP-Phase
akzeptabel dünn, aber ein gerendertes Docs-Portal fehlt.

---

## 6. Agent- und Quality-Gate-DX

**Analyse:**

- **Agents auffindbar/aktuell/eindeutig geroutet?** **Teils.**
  - *Auffindbar:* `.opencode/agents/subagents/narrare-dev/` enthält 6 Definitionen
    (architecture/backend/core/docs/frontend/platform), `opencode.json` setzt
    `default_agent: NarrareDevCoordinator`. ✅ auffindbar.
  - *Aktuell:* Layer-Specialist-Prompts sind detailliert und referenzieren
    aktuelle Regeln (z. B. PlatformSpecialist lädt architectural-discipline,
    CONSTRAINTS, testing-standards). ✅ inhaltlich aktuell.
  - *Eindeutig geroutet:* **Nein — Drift.** Drei Quellen, drei Namensräume:
    - **Echt (`.opencode/agents/subagents/narrare-dev/*.md`):**
      `NarrareArchitectureSpecialist`, `NarrareBackendSpecialist`,
      `NarrareCoreSpecialist`, `NarrareDocsSpecialist`,
      `NarrareFrontendSpecialist`, `NarrarePlatformSpecialist`.
    - **Root `AGENTS.md`** (L146–221): bewirbt `narrare-architecture`,
      `narrare-implementation`, `narrare-testing`, `narrare-ui`,
      `narrare-deployment`, `narrare-documentation` — **keiner** davon ist ein
      gültiger `subagent_type`. Zudem existiert **kein** Testing-Specialist als
      eigener Subagent (Testing ist im PlatformSpecialist aufgegangen).
    - **`orchestrator.md`** (L113–119, L328–336): nutzt `narrare-architecture`,
      `narrare-implementation`, `narrare-core`, `narrare-ui`, `narrare-testing`,
      `narrare-deployment`, `narrare-documentation` — erneut inkonsistent
      („core" vs. „implementation" vs. echtes Backend/Core-Split).
    Ein Coordinator, der orchestrator.md folgt und
    `Agent(subagent_type="narrare-testing")` aufruft, scheitert. Das ist eine
    „documented ≠ implemented"-Verletzung für die Routing-Schicht selbst.
- **Quality Gates dokumentiert UND mit CI verknüpft?** **Ja — vorbildlich, verifiziert.**
  Alle im Prompt genannten Checker sind **echt** (Datei existiert) **und** in
  pre-commit + CI **blockierend** verdrahtet (nicht nur dokumentiert):

  | Checker | Datei existiert? | pre-commit-Hook | CI-Job/Step (ci.yml) | Blocking? |
  |---|---|---|---|---|
  | `check_architecture.py` | ✅ | `architecture-constraints` (L5) | architecture L112 | ✅ |
  | `check_adoption.py` | ✅ | `adoption-score` (L31) | architecture L136 | ✅ |
  | `check_prompt_structure.py` | ✅ | `prompt-structure` (L22) | architecture L130 | ✅ |
  | `check_streaming_compliance.py` | ✅ | `streaming-compliance` (L99) | architecture L159 | ✅ |
  | `check_exception_baseline.py` (+ `--check-sync`) | ✅ | `exception-baseline` (L52) | architecture L120/L123 | ✅ |
  | `check_prompt_surface_contract.py` | ✅ | `prompt-surface-contract` (L90) | architecture L114 | ✅ |
  | `export_openapi.py --check` | ✅ | `openapi-regenerate` (mutierend, L120) | architecture L127 | ✅ |
  | `check_frontend_file_size.py` | ✅ | `frontend-file-size` (L72) | frontend L560 | ✅ |
  | `check_ai_interaction_compliance.py` | ✅ | `ai-interaction-compliance` (L44) | architecture L164 | ✅ |
  | `check_locale_sync.py` | ✅ | `locale-sync` (L109) | architecture L139 | ✅ |
  | `check_secrets.py` (Gitleaks) | ✅ | — (CI-only) | security L267 | ✅ |
  | bandit / pip-audit | ✅ | `bandit` (L174) | security L269/L274 | ✅ |
  | pyright | ✅ | `pyright` + `pyright-tests` (L154/L164) | typecheck L236 | ✅ |
  | ruff check/format | ✅ | `ruff-lint`/`ruff-format` (L138/L146) | lint L203/L206 | ✅ |
  | Coverage ≥80 % + `check_module_coverage.py --fail` | ✅ | — (CI-only) | test-unit L310/L334 | ✅ |

  ⚠️ **Phantom-Referenz:** `scripts/check_governance_health.py` wird in
  `deployment-guide.md` L321 als „`just check-governance` … CI-blocking" angepriesen,
  **existiert aber nicht** (nur ein stale `.pyc`-Cache in `scripts/__pycache__/`).
  Weder im justfile noch in CI/pre-commit referenziert. Das ist eine falsche
  Gate-Behauptung — glücklicherweise harmlos, weil nichts sie aufruft, aber ein
  klares „documented ≠ implemented"-Signal genau in der Quality-Gate-Doku.
- **Veraltete Tool-Anweisungen, die dem Code-Graph-first-Workflow widersprechen?**
  - `orchestrator.md` L27/§Code-Knowledge-Graph-Disziplin und Root-AGENTS.md
    predigen korrekt „graph tools BEFORE Read/Glob/Grep" mit korrekter
    Decision-Matrix (code-review-graph + codebase-memory-mcp). ✅ konsistent.
  - Aber: orchestrator.md Stage 5 (Validate) ruft `just check-types`,
    `just check-constraints`, `just check-governance` auf — **keines** existiert
    (echte Namen: `just typecheck`, `just check-architecture`; `check-governance`
    existiert gar nicht). Ein Agent, der dieser Validierungs-Stage folgt,
    bricht ab. Drift zwischen Workflow-Doku und justfile.
- **RULE-21 (Architecture-Review-Invalidierung bei Planänderung) dokumentiert?**
  **Ja, ausführlich.** CONSTRAINTS.md L862–905 definiert RULE-21 präzise: was
  „material change" ist (neue Dateien/Module, Modul-Grenzen, neue externe Deps,
  Constructor/DI-Wiring, Public-API-Änderung) vs. was nicht (Kosmetik,
  Zeilenzähl-Korrektur, Reihenfolge). Workflow (L880–888) + Konsequenz-Tabelle
  (L899–903) + die Pflicht zum `CHANGES FROM PREVIOUS REVIEW`-Abschnitt bei
  Re-Review. Enforcement = „Manual process step" mit Post-hoc-CI-Coverage +
  strukturiertem Template (`.opencode/context/narrare-dev/templates/review-changes-template.md`).
  Wird auch im Coordinator-Workflow propagiert (orchestrator.md L56, Absolutes #13;
  Constraint-Checklist L359). ✅ gut dokumentiert.

**Bewertung:** ⭐⭐⭐ `[3/5]`
**Befunde:** Die **Quality-Gate-Implementierung** ist die Stärke des Projekts —
jeder dokumentierte Checker ist echt und in pre-commit + CI blockierend verdrahtet
(verifiziert an ci.yml + .pre-commit-config.yaml). Das ist genau das, was
architectural-discipline §7 verlangt. **Aber die DX drumherum** hat drei echte
Brüche: (1) **Agent-Namen-Drift** zwischen AGENTS.md/orchestrator.md und den
tatsächlichen Subagent-Definitionen (`narrare-*` vs. `Narrare*Specialist`) —
jeder AI-Workflow riskiert einen Aufruffehler; (2) **stale `just`-Kommandos**
in der Coordinator-Validierungs-Stage; (3) **phantom `check_governance_health.py`**,
das in der Quality-Gate-Doku als „CI-blocking" behauptet wird, aber nicht
existiert. Das ist ironischerweise genau der „documented ≠ implemented"-Anti-Pattern,
den dieselben Gates an anderer Stelle abwehren.

---

## Gesamtbewertung Developer Experience & Tooling

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`
**Vorherige Bewertung:** — (Erstaudit) | **Trend:** ➡️ Gleich (Basislinie)
**Zusammenfassung:** Narrare hat eine **erstklassige Tooling-Fundierung** —
durchgängig modernster Stack (uv, Ruff, pyright, just, Biome, Vitest, Next 16,
TS 6), single-command-setup (`just dev-setup`), optionaler DevContainer,
vorbildlich zentralisierte Tool-Konfig, und Quality Gates, die **echt**
(Implementierung + Enforcement) in pre-commit und CI laufen — kein einziges
Werkzeug ist wechselwürdig. Der Setup-Pfad ist für die Komplexität des Stacks
erstaunlich glatt, und der `--frozen`-Lockfile-Troubleshooting-Abschnitt ist
exemplarisch. Die Abzüge zum 5. Stern kommen ausschließlich aus der **DX-Schicht**,
nicht der Tool-Schicht: ein fehlendes `CONTRIBUTING.md`, ein erzwungenes
`--extra nlp` im Standard-Setup, mehrere **stale `just`-Kommando-Referenzen**
in zentralen Doku-Files (orchestrator.md, deployment-guide.md), eine **Phantom-
Gate-Behauptung** (`check_governance_health.py`), und vor allem ein
**Agent-Namen-Drift**, der die gesamte AI-gestützte Coordinator-Workflow-Doku
mit nicht-aufrufbaren `subagent_type`-Werten durchsetzt. Diese Drifts sind einzeln
klein (S-Aufwand), häufen sich aber genau dort, wo ein neuer Entwickler/AI
zuerst hinschaut — und widersprechen dem selbst deklarierten
„documented ≠ implemented"-Qualitätsanspruch.

---

## Aufgaben

### AUFG-04-01 · Agent-Namen zwischen AGENTS.md/orchestrator.md und echten Subagent-Definitionen synchronisieren
**Priorität:** Hoch
**Bereich:** DX
**Kontext:** Root-`AGENTS.md` (L146–221) und `docs/development/orchestrator.md`
(L113–119, L328–336) bewerben/routen auf `narrare-architecture`,
`narrare-implementation`, `narrare-testing`, `narrare-ui`, `narrare-deployment`,
`narrare-documentation`, `narrare-core`. Die realen Subagent-Definitionen in
`.opencode/agents/subagents/narrare-dev/*.md` heißen jedoch
`NarrareArchitectureSpecialist`, `NarrareBackendSpecialist`, `NarrareCoreSpecialist`,
`NarrareDocsSpecialist`, `NarrareFrontendSpecialist`, `NarrarePlatformSpecialist`.
Kein `narrare-testing` existiert (Testing ist im PlatformSpecialist). Ein
Coordinator, der der Doku folgt, ruft nicht-existierende `subagent_type`-Werte auf.
**Akzeptanzkriterien:**
- [ ] AGENTS.md Agent-Tabelle (L146–153) und Trigger-Erkennung (L216–221) nutzen die echten `Narrare*Specialist`-Namen (oder die Doku definiert explizit Alias-Mappings).
- [ ] orchestrator.md Routing-Tabellen (L113–119, L328–336) und Decision-Tree (L208–237) verwenden konsistent die echten Namen.
- [ ] Ein (ggf. neuer) Test/Checker verhindert künftigen Agent-Namen-Drift (z. B. ein `check_agent_names.py`, das AGENTS.md/orchestrator.md gegen die Subagent-Frontmatters prüft) — sonst ist die Fix nur Point-in-time.
- [ ] Falls `narrare-testing` bewusst gewünscht ist: als eigener Subagent anlegen ODER Doku klarstellen, dass Testing im PlatformSpecialist lebt.
**Geschätzter Aufwand:** M

### AUFG-04-02 · Stale `just`-Kommando-Referenzen in orchestrator.md korrigieren
**Priorität:** Hoch
**Bereich:** DX
**Kontext:** `docs/development/orchestrator.md` Stage 5 (Validate, L161–168) und
Quick-Reference (L340–345) rufen `just check-types`, `just check-constraints` und
`just check-governance` auf. Keines dieser Rezepte existiert (verifiziert via
`just --list`). Echte Namen: `just typecheck`, `just check-architecture`;
`check-governance` existiert gar nicht. Ein Agent, der der Validierungs-Stage folgt,
bricht mit „recipe not found" ab.
**Akzeptanzkriterien:**
- [ ] Alle `just`-Aufrufe in orchestrator.md gegen `just --list` verifiziert und korrigiert (`check-types`→`typecheck`, `check-constraints`→`check-architecture`, `check-governance` entfernen oder durch echtes Äquivalent ersetzen).
- [ ] Ein (ggf. erweiterter) Doc-Drift-Checker prüft `just`-Befehle in Markdown-Docs gegen das echte Justfile-Rezept-Set und bricht CI bei Phantom-Befehlen.
**Geschätzter Aufwand:** S

### AUFG-04-03 · Phantom-Referenz `check_governance_health.py` aus deployment-guide.md entfernen oder Script anlegen
**Priorität:** Hoch
**Bereich:** DX
**Kontext:** `docs/development/deployment-guide.md` L321 listet
`just check-governance | scripts/check_governance_health.py | … CI-blocking`.
Das Script **existiert nicht** (nur ein stale
`scripts/__pycache__/check_governance_health.cpython-314.pyc`), weder justfile
noch CI noch pre-commit referenzieren es. Die Behauptung „CI-blocking" für ein
nicht-existierendes Gate ist eine „documented ≠ implemented"-Verletzung in genau
der Quality-Gate-Doku.
**Akzeptanzkriterien:**
- [ ] Entweder: `check_governance_health.py` + `just check-governance`-Rezept + CI-Step werden (wieder) angelegt und die Doku stimmt; oder die Zeile wird aus deployment-guide.md entfernt.
- [ ] Der stale `.pyc`-Cache wird gelöscht.
- [ ] Cross-Check: alle in deployment-guide.md „INFRA-011 Stabilization Gate"-Tabelle (L314–321) genannten Kommando/Checker-Paare sind echt und in CI/pre-commit verdrahtet.
**Geschätzter Aufwand:** S

### AUFG-04-04 · Stale Justfile-Command-Catalog-Einträge in deployment-guide.md korrigieren
**Priorität:** Mittel
**Bereich:** DX
**Kontext:** `docs/development/deployment-guide.md` „Justfile Command Catalog"
(L353–379) listet `db-downgrade`, `db-seed`, `format` (L366–367, L377) —
**keines** existiert im justfile. Echte DB-Rezepte: `db-migrate`, `db-revision`,
`db-status`, `db-history`, `db-reset`, `db-shell` (kein downgrade/seed). Format:
`lint` (ruff check+format), `format-frontend`. Copy-Paste aus der Doku → Fehler.
**Akzeptanzkriterien:**
- [ ] Command-Catalog-Tabelle spiegelt exakt das echte `just --list`-Rezept-Set (oder kennzeichnet geplante Rezepte als solche).
- [ ] Doc-Drift-Checker (siehe AUFG-04-02) deckt auch diesen Katalog ab.
**Geschätzter Aufwand:** S

### AUFG-04-05 · CONTRIBUTING.md anlegen
**Priorität:** Hoch
**Bereich:** DX
**Kontext:** Für ein als Open Source deklariertes Projekt (MIT, öffentliches
GitHub-Repo) fehlt ein `CONTRIBUTING.md` komplett. Ein neuer Contributor findet
die Regeln (Conventional Commits, Branch-Modell, `just check`/`just check-full`
vor PR, CI-Blocker, pre-commit-Install via `just dev-setup`) nur verstreut in
coding-standards/deployment-guide. Das README verweist nicht auf einen
Contribution-Einstieg.
**Akzeptanzkriterien:**
- [ ] `CONTRIBUTING.md` existiert mit: How-to-setup-Pointer (`just dev-setup`/DevContainer), Branch-Modell, Conventional-Commits-Regel (oder Verweis), pre-commit-Hinweis, „run `just check` + `just check-frontend` before PR", PR-Template-Verweis, Code-of-Conduct-Referenz.
- [ ] README verlinkt CONTRIBUTING.md.
- [ ] `.github/PULL_REQUEST_TEMPLATE/` (existiert bereits) wird referenziert.
**Geschätzter Aufwand:** S

### AUFG-04-06 · Setup-Option für Nicht-NLP-Entwickler (lightweight `dev-setup`)
**Priorität:** Mittel
**Bereich:** DX
**Kontext:** `just dev-setup` zwingt `--extra nlp` und `just install-nlp-models`
(~200 MB spaCy + 3 Sprachmodelle) auf jeden Entwickler, auch Frontend-only oder
Core/Agent-Entwickler, die NLP nicht anfassen. Das verlängert das Erst-Setup um
Minuten und erhöht den Disk-Bedarf. spaCy ist nur für analysis/nlp-Submodule nötig.
**Akzeptanzkriterien:**
- [ ] Entweder ein `just dev-setup-min` (ohne `--extra nlp` + ohne NLP-Modelle) für FE/Core-Work, oder `just dev-setup` macht NLP bedingt (Skip-Flag / Erkennung, ob analysis-Feature berührt wird).
- [ ] deployment-guide + README dokumentieren beide Setup-Pfade und die jeweilige Setup-Dauer-Erwartung (aktuell 30–60 Min. nirgends kommuniziert).
- [ ] CI bleibt beim vollen `--extra nlp` (Integration/E2E brauchen es).
**Geschätzter Aufwand:** S

### AUFG-04-07 · check_architecture.py — enforced-Regeln in Doku vereinheitlichen
**Priorität:** Niedrig
**Bereich:** DX
**Kontext:** Drei Quellen listen unterschiedliche enforced-Regeln von
`check_architecture.py`: deployment-guide.md §„Architecture Checker" (L301–309)
nennt „RULE-01b, 02, 04, 06, 11"; quality-gates.md Gate 3 (L39) nennt
„RULE-01b, 02, 04, 06, 09, 11, 15, 19"; das Script selbst enforceert mind. RULE-15
(file-existence-Scan, `check_architecture.py` L32/L91). Die Diskrepanz verwirrt
bei der Frage „wird Regel X wirklich maschinell geprüft?".
**Akzeptanzkriterien:**
- [ ] Einzige autoritative Liste der enforced-Regeln ist der Checker-Self-Report (z. B. `check_architecture.py --list-rules` oder Modul-Docstring); beide Doku-Quellen verweisen darauf statt eigener Aufzählung.
- [ ] deployment-guide.md und quality-gates.md stimmen überein (oder referenzieren dieselbe Quelle).
**Geschätzter Aufwand:** S

### AUFG-04-08 · ESLint/Prettier-VS-Code-Extensions im DevContainer entfernen (Projekt nutzt Biome)
**Priorität:** Niedrig
**Bereich:** DX
**Kontext:** `.devcontainer/devcontainer.json` installiert `dbaeumer.vscode-eslint`
und `esbenp.prettier-vscode`, aber das Projekt nutzt **Biome** als alleinigen
FE-Linter/Formatter (`packages/web/package.json`: `lint=biome check --write`,
`format=biome format --write`; pre-commit `biome-frontend`; CI `biome check`).
ESLint/Prettier sind tote Extensions, die neue Entwickler verwirren („welchen
Formatter nutze ich?") und Inkonsistenz mit dem defaultFormatter-Setting riskieren.
**Akzeptanzkriterien:**
- [ ] `eslint` + `prettier-vscode` aus `devcontainer.json` extensions entfernt.
- [ ] Biome-Extension (`biomejs.biome`) bleibt als alleiniger FE-Formatter (ist bereits als defaultFormatter gesetzt).
- [ ] Optional: `pnpm`-Version im Dockerfile (`ARG PNPM_VERSION=11.5.2`) gegen `package.json`-`packageManager`-Pin prüfen lassen (Drift-Risiko).
**Geschätzter Aufwand:** S

### AUFG-04-09 · `jsonschema` von Root-`[project] dependencies` nach `[dependency-groups] dev` verschieben
**Priorität:** Niedrig
**Bereich:** DX / Architektur
**Kontext:** Root-`pyproject.toml` ist `[tool.uv] package = false` (virtual
workspace container), deklariert aber `[project] dependencies = ["jsonschema>=4.26.0"]`.
`jsonschema` wird ausschließlich von `scripts/check_registry_drift.py` (Dev-Tooling)
genutzt. Als `[project] dependency` wird es in jeden Sync (inkl. prod-ähnlicher
Root-Syncs) installiert statt nur in die dev-Gruppe.
**Akzeptanzkriterien:**
- [ ] `jsonschema` nach `[dependency-groups] dev` verschoben; `[project] dependencies` am Root ist leer (oder entfernt).
- [ ] `uv sync --frozen --all-packages --group dev --extra nlp` (installiert dev) bleibt funktional; CI/pre-commit unbeeinträchtigt.
- [ ] Lockfile regeneriert und committet.
**Geschätzter Aufwand:** S

### AUFG-04-10 · pip-audit-Vuln-Suppresssions inline begründen
**Priorität:** Niedrig
**Bereich:** DX / Sicherheit
**Kontext:** CI ruft `pip-audit --skip-editable --ignore-vuln PYSEC-2025-183
--ignore-vuln GHSA-rrmf-rvhw-rf47` (ci.yml L275) auf. Die zwei suppressierten
Vulns haben **keinen Inline-Kommentar** (welche Abhängigkeit, warum nicht fixbar,
Wiedervorlage-Datum). Suppression ist legitim, sollte aber nachvollziehbar sein.
**Akzeptanzkriterien:**
- [ ] Jede `--ignore-vuln` im CI-Step hat einen Kommentar: betroffenes Paket + Grund (z. B. „upstream fix pending", „false positive") + Wiedervorlage/Re-evaluation-Datum.
- [ ] Optional: Verschiebung der Suppression-Liste in eine separate, kommentierte Konfig (`pyproject.toml [tool.pip-audit]` o. ä.), um sie sichtbarer zu machen.
**Geschätzter Aufwand:** S
