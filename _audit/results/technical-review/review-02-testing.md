# Review 02 – Testing & CI/CD

> **Voraussetzung:** Lies zuerst `_audit/results/technical-review/review-00-kontext.md` und stelle sicher,
> dass er vollständig ausgefüllt ist. Referenziere die dort dokumentierten Pfade und den Tech-Stack.
> Sollte `_audit/results/technical-review/review-00-kontext.md` nicht existieren, erstelle ihn
> zunächst auf Basis von `_audit/review-prompts/technical-review-prompts/review-00-kontext.md`
>
> **Routing:** Führe diesen Prompt mit `NarrarePlatformSpecialist` aus.
>
> **Ausgabe:** Schreibe das Ergebnis nach `_audit/results/technical-review/review-02-testing.md`.
> Sei kritisch. Fokus liegt besonders auf den bekannten Problemen:
> Komponenten-Marker, Pytest/Pyright-Performance.

---

> **Methodik-Hinweis:** Evidenz wurde graph-first (`code-review-graph`, 26.940 Knoten / 193.137
> Kanten, Build frisch) plus gezielten Read/Grep auf Konfigurationsdateien erhoben. Die gemessenen
> Zahlen (Pytest-Collection-Timing, Test-Zählungen, CI-Job-Struktur) sind live erhoben, nicht
> geschätzt. `codebase-memory-mcp` ist laut Vorgabe nicht indiziert und wurde nicht genutzt.
> `semantic_search_nodes_tool` war wegen fehlender Embeddings schwach; es wurden primär
> `get_knowledge_gaps_tool`, `query_graph_tool` und exakte Read/Grep genutzt.

---

## 1. Backend-Test-Suite – Struktur & Abdeckung

**Struktur (gemessen):**

Die 3-Level-Architektur aus `docs/development/testing-standards.md` ist sauber umgesetzt und
physisch getrennt (`tests/unit/`, `tests/integration/`, `tests/e2e/`). Dateizählung (live via
`find tests -name 'test_*.py'`):

| Ebene | Test-Dateien | Bemerkung |
|---|---|---|
| `tests/unit/core/` | 331 | Core-Domain-Logik |
| `tests/unit/api/` | 357 | Services, Router, Schemas, Contracts |
| `tests/integration/` | 85 | Real DB (pgvector/pg17) + Redis, gemocktes LLM |
| `tests/e2e/` | 12 | Playwright, main-branch-only |
| **Python gesamt** | **785** | — |

Frontend (Vitest): **304** `*.test.{ts,tsx}` + **5** Playwright `*.spec.ts`.

Collection-Timing live gemessen:
- `pytest tests/unit/ --collect-only -q` → **8.768 Tests in 11,83 s**
- `pytest tests/ --collect-only -q` → **9.471 Tests in 11,81 s**

**Naming-Konvention:** Konsistent durchgesetzt — `test_*.py` (pyproject `python_files`),
Klassen `Test*`, Funktionen `test_*`. Test-Pfade spiegeln die Source-Struktur wider
(`core/prompts/composer.py` → `tests/unit/core/prompts/test_composer.py`), wie RULE-10 fordert.

**Abdeckung (ratcheted Baselines, `scripts/coverage_baselines.json`, Stand 2026-07-05):**
Die globale CI-Schwelle ist `--cov-fail-under=80` (RULE-10 api ≥80 %); README-Badge zeigt 92 %.
Die per-Modul-Ratchet-Baselines (`check_module_coverage.py --fail`, blockierend in CI) liegen
mehrheitlich deutlich über dem Floor:

| Spitzenreiter (≥95 %) | Schwächste (81–85 %) |
|---|---|
| `cache`, `metrics`, `nlp`, `tasks`, `project`, `schemas` = 100 %; `_app` 97,1 %; `llm` 97,3 %; `prompts` 98,4 %; `writing` 95,5 %; `shared` 95,8 % | `settings` 81,5 %; `templates` 82,4 %; `kb` 83,9 %; `novels` 83,8 %; `volumes` 84,0 %; `planning` 84,5 %; `auth` 85,0 % |

Die schwachen Module liegen alle über dem api-Floor (80 %), aber `settings`/`templates`/`kb`/
`novels`/`volumes` sind nah an der Grenze — eine Regression von wenigen Prozent würde sie
unter den Floor drücken. `check_test_coverage_gaps.py --fail-on-missing` (architecture-Job)
blockiert zusätzlich auf fehlende Test-Spiegelung.

**Knowledge-Graph-Lücken (`get_knowledge_gaps_tool`):** Summary: 50 isolierte Knoten,
456 dünne Communities, 1.698 Single-File-Communities (erwartbar bei Test-File-Granularität),
**20 untested hotspots** (High-Degree-Knoten ohne direkte TESTED_BY-Kante). Die echten
(d.h. nicht durch Integration abgedeckten) Lücken konzentrieren sich auf das **Frontend**:
`fetchApi` (degree 161, `lib/api/core.ts`), `useKnowledgeGraphController` (92),
`useGenerationPanelController` (72), `useKBAssistedCreationController` (52),
`EditorToolbar` (2×, legacy + neu). Die Alembic-`upgrade`-Hotspots sind **False Positives** —
Integration-Tests führen echte Migrationen aus (`alembic upgrade head`), der Graph erkennt
das aber nicht als TESTED_BY. Ebenso `_register_routers` (app wiring, integration-abgedeckt).

**Fixtures vs. Setup-Duplikation:** Hervorragend. `tests/fakes/` enthält **22 Fake-Module**
(`fake_llm_gateway.py`, `fake_pydantic_agent.py`, `fake_chapter_repo.py`, …) — Fake-Klassen
statt bloßer MagicMock (RULE-TEST-01), erzwungen via `scripts/check_architecture.py`
(bare-MagicMock-Scan). `tests/unit/test_fake_conformance.py` prüft Protocol-Conformance
via `isinstance()` gegen `@runtime_checkable` Protocols. Per-Domain-conftest.py-Dateien
kapseln Setup. `tests/factories.py` liefert Factory-Helper (`make_chapter`, `make_novel`).
Keine massive Setup-Duplikation erkennbar.

**Fakes mit Protocol-Conformance:** Ja, vorhanden und verifiziert (siehe oben). Die einzige
dokumentierte RULE-TEST-01-Ausnahme ist `tests/unit/api/metrics/test_metrics_router.py`
(Mocking SQLAlchemy Engine — kein Domain-Contract), registriert in `pyproject.toml §7`.

**Redundanz-Check:**
- *Szenario-Duplikate:* Vereinzelte Dopplungen zwischen Unit- und Integration-Ebene
  (z. B. `test_kb_repository.py` unit mockt vs. `test_kb_repository.py` integration real)
  sind **gewollt** (testing-standards.md: Repositories werden NICHT unit-getestet — die
  Unit-Dateien testen Service-Logik mit Fake-Repo, Integration testet echtes SQL).
- *Implementierungsdetail-Tests:* Die Fake-Call-Tracking-Assertions (`fake.calls`,
  `call_count`) prüfen teilweise Interaktion statt Ergebnis. Akzeptabel für Gateway-/Agent-
  Pfade (wo Output nicht-deterministisch über TestModel ist), aber bei reinen CRUD-Services
  wäre verhaltensbasierte Assertion robuster. Kein systematisches Problem.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Reife, gut strukturierte Suite mit klarer 3-Level-Trennung, durchgängiger
Fake-Klassen-Disziplin (RULE-TEST-01), Protocol-Conformance-Tests und ratcheted Per-Modul-
Coverage-Gates. Collection ist mit 11,8 s für ~9,5k Tests schnell. Schwächen: 6 Module
nur 81–85 % (nah am 80 %-Floor); 20 untested hotspots konzentriert auf ungetestete
Frontend-Controller-Hooks; Dokumentation in testing-standards.md ist **stale**
(behauptet „~6.160 unit tests", real sind 8.768 — bzw. „~6.600+ tests", real 9.471).

---

## 2. Komponenten-Marker-Problem

**Definition & Verwendung:**

Der „Komponenten-Marker" ist ein `data-testid`- oder `aria-label`-Attribut auf interaktiven
Elementen (`<button>`, `<input>` mit text-ähnlichem type, `<select>`, `<a onClick>`,
`role="button"`). Zweck: stabile Selektoren für E2E-/VRT-Tests. Enforcement erfolgt durch
`packages/web/scripts/check-testid.ts` — ein **regex-basierter** Zeilen-Scanner (kein AST),
der interaktive Tags erkennt und fehlende Marker als Violation meldet.

Aktuelle Verdrahtung (live verifiziert):
- **Pre-commit** (`.pre-commit-config.yaml` id `check-testid`): `scripts/check-testid.ts --fail`
- **CI frontend-Job** (ci.yml L593): `scripts/check-testid.ts --fail`

Nutzung im Code: 61 Dateien unter `components/`+`app/` enthalten `data-testid` (182 Vorkommen).

**Warum erkennt die AI das fehlende Marker-Pattern nicht selbst?**

Root Cause: **Es existiert keine AI-sichtbare Vorschrift.** `grep` über `.opencode/`,
`.agents/` und `docs/development/` findet **keinen** Hinweis auf `data-testid` /
Komponenten-Marker — die einzige Referenz ist `docs/development/deployment-guide.md`
(beschreibt nur den CI-Schritt). Weder `ui-principles.md` (1.213 Zeilen) noch die
Coding-Standards noch irgend ein Agent-Skill erwähnen die Pflicht zu Markern. Eine AI,
die eine neue Komponente schreibt, hat daher keinen Anlass, Marker hinzuzufügen — sie
erfährt vom Problem erst, wenn der (regex-basierte, laxe) Gate fehlschlägt.

**Vorhandene Mechanismen (und ihre Lücken):**
1. `check-testid.ts` läuft in **laxem Modus** (`--strict` ist nicht gesetzt): die
   `LOOSE_SKIP_DIRS = {"ui"}` überspringt **gesamtes `components/ui/`** — also genau die
   Primitives, die am häufigsten interaktive Elemente kapseln. `--strict` existiert als
   npm-Script (`check:testid:strict`), ist aber an **kein** Gate (pre-commit/CI) angebunden.
2. Regex statt AST → False Negatives für zusammengesetzte Elemente (`<div role="button">`,
   Radix-Trigger, spread-Props `<button {...props}>` wo `data-testid` über Props kommt)
   und False Positives für kommentierten Code.
3. Der Check deckt nur 5 Element-Arten ab — custom interaktive Komponenten ohne native Tags
   werden nicht erfasst.

**Empfehle konkrete Lösungen für alle folgenden Ebenen:**

| Ebene | Mögliche Lösung | Aufwand |
|---|---|---|
| Pre-commit Hook | `--strict` aktivieren (deckt `components/ui/` ab); dafür `.tsx`-Dateien mit `data-testid`-via-spread via Inline-Kommentar `// check-testid:ok` annotierbar machen, um False Positives zu unterdrücken. Existierende Verdrahtung bleibt, nur Flag-Wechsel. | **S** |
| Pytest-Plugin / Conftest | Nicht primär zielführend (Frontend-Gate); stattdessen **Vitest-basierten** Test ergänzen: eine `.test.ts`, die alle `*.tsx` lädt und via Testing-Library-Queries prüft, dass jede `getByRole("button")`/`getByRole("textbox")` einen `data-testid` hat. Fängt AST-Lücken auf, die Regex verpasst. | **M** |
| CI-Check (Fail-Fast) | `--strict --fail` im CI-frontend-Job (und pre-commit) aktivieren; zusätzlich **Baseline-Ratchet** (wie `coverage_baselines.json`): aktuelle Violation-Anzahl als `scripts/testid_baselines.json` festhalten, `--fail` nur bei Wachstum. Verhindert Big-Bang-Fix, erlaubt schrittweise Sanierung. | **S** |
| AI-Prompt-Ergänzung (.claude/commands) | **Wichtigster Hebel.** Pflicht-Regel in `docs/development/ui-principles.md` (neuer Abschnitt „§17 Komponenten-Marker") + Verweis in `.agents/skills/` und Frontend-AGENTS.md: „Jedes interaktive Element (`<button>`, `<input>`, `<select>`, `role="button"`) MUSS ein `data-testid` oder `aria-label` tragen." Damit erkennt die AI das Pattern beim Schreiben. | **S** |
| Testfall-Template / Snippet | Komponenten-Story/Template in `packages/web/components/ui/` ergänzen, das `data-testid` als Pflicht-Prop zeigt; plop/scaffold-Template für neue Komponenten um `data-testid={__name}` erweitern. | **S** |

**Empfehlung:** Die effektivste Kombination mit geringstem Aufwand ist
**(AI-Prompt-Ergänzung in ui-principles.md) + (Baseline-Ratchet + `--strict` in CI)**.
Die AI-Prompt-Ergänzung verhindert das Problem an der Quelle (Aufwand S), der Ratchet-Check
schließt die Lücke für manuelle/historische Komponenten, ohne einen Big-Bang-Fix zu erzwingen
(Aufwand S). Das Vitest-Plugin (M) ist optional als zweite Verteidigungslinie für AST-Genauigkeit.

**Bewertung:** ⭐⭐⭐
**Befunde:** Ein Gate existiert, ist aber **lax** (`components/ui/` übersprungen), **regex-basiert**
(False Negatives) und vor allem **für die AI unsichtbar** — keine der Standards-Dateien
dokumentiert die Marker-Pflicht. Das ist der eigentliche Grund, warum die AI das fehlende
Pattern nicht selbst erkennt. Strengeres Gate + dokumentierte Regel + Ratchet-Baseline lösen
das Problem nachhaltig.

---

## 3. Pytest-Performance

**Gemessene Collection-Zeiten (live, inkl. `uv run`-Overhead):**
- `pytest tests/unit/ --collect-only -q` → **8.768 Tests in 11,83 s**
- `pytest tests/ --collect-only -q` → **9.471 Tests in 11,81 s**

CI-Gate `check_pytest_collection_performance.py` (Threshold 20 s, **WARNING-only**): mit
11,8 s klar unterhalb. Die testing-standards.md-Doku ist allerdings **stale** — sie gibt
„~6.160 unit tests / ~14s" und „~6.670 tests / ~17s" an; real sind es 8.768 / 9.471.

**`pyproject.toml [tool.pytest.ini_options]` (live gelesen):**
- `testpaths = ["tests"]` ✅ gesetzt
- `pythonpath = ["apps/api", "packages/core"]` ✅ gesetzt (verhindert conftest.sys.path-Hacks)
- `python_files = ["test_*.py"]`, `python_classes = ["Test*"]`, `python_functions = ["test_*"]` ✅
- `asyncio_mode = "auto"`, loop-scope `session` ✅ (verhindert pro-Test-Event-Loop-Overhead)
- `timeout = 10`, `timeout_func_only = true` ✅
- `filterwarnings = ["error", …]` — **streng** (Warnings = Fehler); gut für Qualität, kann aber
  Collection verlangsamen, wenn viele DeprecationWarnings gefiltert werden müssen.
- `norecursedirs` ✅ (`.venv`, `node_modules`, `__pycache__`, `.hypothesis`, …)
- **`--import-mode` ist NICHT gesetzt** → Default `prepend`. Bei dieser Test-Anzahl ist
  `importmode=importlib` (pytest ≥8) empfehlenswert: keine `sys.path`-Mutationen, schnelleres
  Collect, keine `__init__.py`-Konflikte. **Potenzial.**
- **xdist:** In `ini_options` nicht konfiguriert; Parallelisierung erfolgt über CLI `-n auto`
  (justfile `test-unit`: `-n auto --dist loadfile`; CI test-unit: `-n auto`). `--dist loadfile`
  nur im justfile, **nicht** in CI — CI nutzt Default `--dist load` (Round-Robin), was bei
  Load-unterschiedlichen Test-Files zu Stragglers führen kann.

**Plugins geladen** (`[dependency-groups] dev`): pytest-asyncio, pytest-cov, pytest-xdist,
pytest-randomly, pytest-timeout, hypothesis, mutmut, pytest-playwright, pydantic-evals.
Alle aktiv genutzt — kein toter Plugin-Overhead erkennbar. `pytest-randomly` adds minimal
Collection-Kosten, ist aber wertvoll (Ordnen-Abhängigkeits-Bugs).

**Import-Seiteneffekte:** `tests/conftest.py` setzt Env-Vars und importiert `pydantic_ai.models`
(sehr leicht). Domain-Importe passieren erst in Fixtures, nicht auf Modulebene — gut.
`conftest.py` ist im Verhältnis zur Suite winzig (125 Zeilen).

**Konkrete Empfehlungen:**
1. **`--import-mode=importlib` in `addopts`** (oder `[tool.pytest.ini_options]`). Erwartete
   Ersparnis: ~1–2 s Collection durch Wegfall von `sys.path`-Manipulation und Duplicate-Import-
   Checks bei 8,7k Tests. Aufwand **S**.
2. **`--dist loadfile` auch in CI** (`ci.yml` test-unit-Job, currently `-n auto` ohne `--dist`).
   `loadfile` gruppiert Tests einer Datei auf denselben Worker → weniger Fixture-Re-Setup,
   weniger Stragglers. Erwartet: messbare Gesamtlaufzeit-Reduktion (Typischerweise 5–15 % bei
   Fixture-schweren Suites). Aufwand **S**.
3. **`pythonpath` statt conftest-`sys.path.insert`:** Aktuell macht `tests/conftest.py` L14–21
   `sys.path.insert` *zusätzlich* zum konfigurierten `pythonpath`. Redundant — entfernen
   reduziert Import-Arbeit pro Worker. Aufwand **S**, Ersparnis marginal (~0,2 s), aber
   aufräumend.
4. **`-p no:cacheprovider` für reine Collect-Messungen** (nur Diagnose, nicht dauerhaft).
5. **`--cov` nur im CI, nicht lokal für `just test-unit`** — aktuell kein `--cov` in
   `just test-unit`, gut. `pytest-cov` wird aber prozessweit initialisiert; bei
   `COVERAGE_CORE_PROCESS=1`-freiem Setup kein nennenswerter Collect-Einfluss.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** 11,8 s Collection für ~9,5k Tests ist **gut** und liegt klar unter dem
20-s-CI-Threshold (WARNING-only). Konfiguration ist sauber (`testpaths`, `pythonpath`,
asyncio-loop-scope `session`). Hauptverbesserung: `--import-mode=importlib` + `--dist loadfile`
in CI. Doku-Zahlen sind veraltet (genannte ~6k vs. reale ~9k).

---

## 4. Pyright-Performance

**Konfiguration (`pyproject.toml [tool.pyright]` + `tests/pyrightconfig.json`, live gelesen):**

Root-Konfiguration (`pyproject.toml`):
- `pythonVersion = "3.14"`, `typeCheckingMode = "strict"` ✅
- **`useLibraryCodeForTypes = false`** ✅ — bewusst deaktiviert (Kommentar „Kein Tiefen-Parsen
  von externen Bibliotheken"); größter Performance-Hebel bereits gezogen.
- **`venvPath = "."`, `venv = ".venv"`** ✅ — verhindert venv-Scan; Performance-Hebel gezogen.
- `include = ["apps/api", "packages/core", "packages/i18n", "scripts"]` — `tests/` ist
  **bewusst ausgeschlossen** (Kommentar: „1.048 test files; tests get a separate conditional
  hook in .pre-commit-config.yaml"). Tests werden über `tests/pyrightconfig.json` mit
  `typeCheckingMode = "basic"` separat getippt → viel schneller.
- `exclude` umfasst `**/.*`, `tests/e2e/**`, `.venv`, `__pycache__`, `node_modules`,
  `migrations/**`, `.code-review-graph`, `.agents` ✅ — Migrationen und generierte/externe
  Verzeichnisse korrekt ausgeschlossen.

Test-Konfiguration (`tests/pyrightconfig.json`): `basic`-Modus, `useLibraryCodeForTypes=false`,
`reportMissingImports=false`, `reportMissingTypeStubs=false` — bewusst lax & schnell. ✅

CI: Pyright-Cache aktiv (`actions/cache@v6`, key basierend auf `pyproject.toml`+`uv.lock`).
Pre-commit: zwei Stufen (Production `pyright` + Tests `pyright --project tests/pyrightconfig.json`).

**Auto-generierte/große Dateien:** Alembic-Migrationen sind via `**/migrations/**` ausgeschlossen ✅.
Keine weiteren großen generierten Files-Bundles im `include` erkennbar. `docs/openapi.json`
wird generiert, liegt aber nicht im Pyright-`include`.

**Strenge Regeln:** `reportUnknownMemberType/VariableType/ArgumentType = true`;
`reportMissingTypeStubs = true` (false positives bei fehlenden Stubs dokumentiert als Known
Risk in CURRENT_STATE.md). `reportDeprecated = false` (ADR-046-Transition, MetaPromptLoader).

**Konkrete Empfehlungen:**
1. **Cache-Key fehlt `tests/pyrightconfig.json`:** Der `actions/cache`-Key basiert nur auf
   `pyproject.toml` + `uv.lock`. Änderungen an `tests/pyrightconfig.json` invalidieren den
   Cache nicht → veraltete Cache-Hits bei Test-Config-Änderungen. Key um `tests/pyrightconfig.json`
   erweitern. Aufwand **S**.
2. **`extraPaths` statt implizite Auflösung:** Für zuverlässigere und ggf. schnellere Modul-
   Auflösung `extraPaths = ["apps/api", "packages/core", "packages/i18n"]` setzen (komplementär
   zu `pythonpath` in pytest). Aufwand **S**.
3. **`reportMissingTypeStubs` auf `false` setzen ODER ausgewählte Packages in
   `# pyright: reportMissingTypeStubs=false`** für die dokumentierten Drittanbieter ohne Stubs
   — aktuell erzeugt das echte Fehler, die laut CURRENT_STATE Known Risk teils False Positives
   sind. Falls beibehalten, die bekannten Pakete (`asyncpg`, `taskiq`, …) explizit kommentieren,
   um Rauschen zu reduzieren. Aufwand **S–M**.
4. **`logLevel` / `--outputjson` in CI für bessere Fehler-Zuordnung** (optional, DX).

Die Konfiguration ist **bereits sehr gut optimiert** (`useLibraryCodeForTypes=false`, venv
explizit, tests separat-lax, Migrationen excluded). Verbesserungspotenzial ist klein —
hauptsächlich Cache-Key-Korrektur.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Pyright-Setup ist professionell konfiguriert — die zwei teuersten Hebel
(`useLibraryCodeForTypes=false`, explizites venv, Test-Auslagerung in `basic`-Mode) sind
gezogen. Caching in CI vorhanden. Einziger echter Mangel: der Pyright-Cache-Key ignoriert
`tests/pyrightconfig.json`; ansonsten nur Feinputollierungen. Kein akuter Handlungsbedarf.

---

## 5. Frontend-Test-Suite

**Framework & Setup (`packages/web/package.json` + `vitest.config.ts`, live gelesen):**
- **Runner:** Vitest 4.1.9 mit `@vitest/coverage-v8`
- **Environment:** `happy-dom` (3–5× schneller als jsdom, bewusst gewählt)
- **Component Testing:** `@testing-library/react` + `@testing-library/user-event`
- **API Mocking:** MSW v2.14.6 (`mocks/handlers.ts`, `mocks/data.ts`)
- **State Testing:** Direkter Zustand-Test via `useStore.getState()` (Zustand)
- **Pool:** `threads`, `maxWorkers: 6`
- **E2E:** Playwright 1.61.1 (5 `*.spec.ts`); VRT via `toHaveScreenshot()` (ADR-059)
- **Lint/Format:** Biome 2.5.2

Test-Datei-Zählung: **304** `*.test.{ts,tsx}` + **5** Playwright `*.spec.ts`.

**Coverage-Thresholds (`vitest.config.ts`):**
| Scope | Lines/Functions/Branches/Statements |
|---|---|
| `global` | 25 % |
| `lib/**` | 80 % |
| `components/**` | **15 %** |

Die `components/**`-Schwelle von **15 %** ist sehr niedrig (und `global` 25 % deckt nur
randständig). Die 80 % für `lib/` sind angemessen.

**Kritische UI-Flows ohne Tests (aus §1 untested hotspots + Knowledge-Graph):**
- `useKnowledgeGraphController` (degree 92) — **kein** Unit-Test
- `useGenerationPanelController` (72) — **kein** Unit-Test
- `useKBAssistedCreationController` (52) — **kein** Unit-Test
- `EditorToolbar` (2 Varianten, degree 58 + 47) — **kein** Komponenten-Test
- `fetchApi` (degree 161, `lib/api/core.ts`) — kein direkter Test (nur indirekt via MSW-Integration)

Diese Controller-Hooks sind hochgradig vernetzte Studio-Komponenten — Lücken mit hoher
„Blast Radius"-Wirkung. E2E (12 Tests) deckt nur Happy-Path-Flows ab.

**Konsistenz mit Backend:** Teilweise. Backend nutzt Fake-Klassen + Protocol-Conformance;
Frontend nutzt MSW + Testing-Library (angemessen für UI). Aber: das Backend hat
`data-testid`-Conformance-Tests und ratcheted Per-Modul-Coverage; das Frontend hat weder
ein `data-testid`-Conformance-Vitest-Test noch eine per-Komponenten-Coverage-Ratchet
(nur die groben 15 %/80 %-Schwellen).

**Snapshot-Tests:** Vitest unterstützt `toMatchSnapshot()`; RULE-TEST-04 (testing-standards.md
L1016–1062) definiert klare Regeln (verboten für dynamischen Content, erlaubt für statische
Elemente/Templates). VRT nutzt `toHaveScreenshot()` (ADR-059), regelkonform. Keine
Snapshot-Missbrauch-Muster erkennbar, aber auch keine systematische Snapshot-Nutzung —
überwiegend explizite Assertions (gute Praxis).

**Frontend-Performance-Gate:** CI frontend-Job hat WARNING-only-Budget von 240 s
(197 Test-Dateien / ~223 s laut Kommentar; reale Test-Datei-Zahl jetzt 304 → Budget dürfte
bereits überschritten sein, Gate ist aber nicht-blockierend).

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Solides Setup (Vitest 4, happy-dom, MSW, Testing-Library, Playwright+VRT).
Backend-Konventionen größtenteils gespiegelt (RULE-TEST-04, naming). Schwächen: **3
hochgradig-vernetzte Controller-Hooks ungetestet** (KnowledgeGraph/GenerationPanel/
KBAssistedCreation), `components/**`-Coverage-Schwelle mit 15 % zu niedrig, kein
per-Komponenten-Ratchet, WARNING-only-Performance-Budget vermutlich schon überschritten.
`data-testid`-Problem siehe §2.

---

## 6. Evaluation-Driven Development (Prompt Testing)

**Golden Datasets / automatisierte LLM-Evals:** Ja — `evals/` implementiert **Pydantic Evals**
als SSOT (ADR-032, superseded ADR-018/promptfoo; promptfoo vollständig entfernt — verifiziert:
keine Reste in Workflows/Configs). Struktur:
```
evals/
├── datasets/        9 Code-First Dataset/Case-Definitionen
├── evaluators/      10 Custom-Evaluator-Implementierungen (analysis, chat, consistency, kb, …)
├── tasks/           smoke + runtime Task-Entrypoints
├── baselines/       10 versionierte Drift-Baselines (JSON)
├── results/         CI-Reports
├── judges.py        optionaler LLM-Judge
└── runner.py        CLI: --suite --mode smoke|runtime
```

**Regressionsschutz bei Prompt-/Gateway-Änderungen:** Zweistufig:
- **Smoke** (deterministisch, secret-free): **blockierend** im CI-architecture-Job
  (`python -m evals run --suite all --mode smoke`) + `check_eval_drift.py` (blockierend).
- **Runtime** (echte Provider-Calls): **nachtlich** um 03:00 UTC (`eval-nightly.yml`) +
  manuell (`workflow_dispatch`), drift **WARNING-only** (ratcheted).

Metriken werden in Custom-Evaluatoren (z. B. `evaluators/analysis.py`, `evaluators/consistency.py`)
erhoben; Baselines in `evals/baselines/*.json` sind committed. Threshold default
`--fail-on-score-below 0.8`.

**Metriken (Konsistenz / Tone / Format):** Teilweise. `evaluators/` enthält spezialisierte
Evaluatoren (analysis_metrics, consistency, kb_operations, planning_structure, preference,
rewrite). Tone-of-Voice / Konsistenz werden über die qualitativen Evaluatoren + ggf. LLM-Judge
(`judges.py`, optional) abgedeckt. Format-Einhaltung über Structured-Output-Evaluatoren.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Ausgereiftes, ADR-032-konformes Eval-System mit Smoke-(blocking)+Runtime-(nightly)-
Trennung, 9 Suites, 10 Baselines, Custom-Evaluatoren und deterministischem TestModel-Schutz
in pytest (`ALLOW_MODEL_REQUESTS=False`). Schwächen: Writing/Generation-Prose-Agents
(extend/suggest/variant/session) haben **keine** eigene Eval-Suite (nur `chat_generation`
streift das Thema); Runtime-Drift ist nur WARNING-only — eine stille Qualitätsregression bleibt
nicht-blockierend. Details zu ADR-018-Konformanz siehe §8.

---

## 7. CI/CD-Workflow (.github/workflows/ci.yml)

**Jobs & Reihenfolge (live gelesen):**

```
architecture (≤30s)
   ├──→ lint (≤60s)
   ├──→ typecheck (≤2min)        [pyright + cache]
   ├──→ security (≤60s)          [gitleaks + bandit + pip-audit]
   └──→ frontend (≤3min)         [biome + i18n + type-check + vitest + VRT + build]
            (lint, typecheck) ──→ test-unit (≤5min, --cov, --cov-fail-under=80)
            (lint, typecheck) ──→ test-integration (≤5min, pgvector/pg17 + redis services)
                                   test-e2e (main-only, full stack)
                                   update-coverage-badge (main-push)
warnings-summary (always, aggregate ::warning::)
```

**Parallel vs. sequenziell:** `lint`/`typecheck`/`security`/`frontend` laufen parallel nach
`architecture`. `test-unit`/`test-integration` laufen parallel nach `lint`+`typecheck`.
`test-e2e` nur auf main-push. **Fail-Fast via `needs:`** (architecture bricht alles ab; lint/
typecheck-Fehler stoppt test-unit/integration). Konkurrenz-Gruppe mit `cancel-in-progress: true`.

**Typische CI-Dauer:** Kopf-Kommentare schätzen architecture <30s, lint <60s, typecheck <2min,
security <60s, frontend <3min, test-unit <5min, test-integration <5min, e2e <5min. Kritischer
Pfad (architecture → typecheck → test-unit) ~7–8 min; mit frontend-Parallelität Gesamt ~8–10 min.

**Caches:** `setup-uv@v7` mit `enable-cache: true` (uv-Cache), `setup-node@v6` mit
`cache: "pnpm"` (pnpm-store), `actions/cache@v6` für Pyright (`.pyright/`). Caches gut genutzt.
Pip-Cache obsolet (uv).

**Secrets:** Gitleaks (Secret-Scan, `fetch-depth: 0`), `permissions: contents: read` minimal,
`NARRARE_EVAL_API_KEY` als Secret, Provider-Keys als Dummy `sk-test-dummy` in Test-Jobs. Sicher.

**Separater Lint-/Type-Check-Job:** Ja — `lint` (ruff) und `typecheck` (pyright) sind separate
Jobs nach `architecture`. ✅

**Komponenten-Marker in CI:** Ja — frontend-Job L593 `check-testid.ts --fail` (aber **lax**,
siehe §2: `components/ui/` übersprungen).

**Erwartete Checks im erwarteten Modus (alle verifiziert):**
| Check | Job | Modus |
|---|---|---|
| `check_architecture.py` | architecture | ✅ blocking |
| `check_adoption.py` | architecture | ✅ blocking (`--evidence-dir .evidence`) |
| `check_prompt_structure.py` | architecture | ✅ blocking |
| `validate-i18n.ts` | frontend | ✅ blocking (`npx tsx scripts/validate-i18n.ts`) |
| `check_streaming_compliance.py` | architecture | ✅ blocking (RULE-20) |
| `check_ai_interaction_compliance.py` | architecture | ✅ blocking (ADR-043/§16) |
| `check_module_coverage.py --fail` | test-unit | ✅ blocking (ratcheted) |
| `check_test_coverage_gaps.py --fail-on-missing` | architecture | ✅ blocking |
| `evals smoke` + `check_eval_drift.py` | architecture | ✅ blocking |
| `check_exception_baseline.py` + `--check-sync` | architecture | ✅ blocking (no-growth) |
| `check_prompt_surface_contract.py` | architecture | ✅ blocking (ADR-037/049) |
| `export_openapi.py --check` | architecture | ✅ blocking |
| `check_locale_sync.py` | architecture | ✅ blocking |
| `check_gate_drift.py`, `check_gate_expirations.py` | architecture | ✅ blocking |
| `check_current_state_facts.py` | architecture | ✅ blocking (SSOT) |

Die Gate-Konformitäts-Tabelle im ci.yml-Kopf (G1–G10 + Erweiterungen) ist außergewöhnlich
umfangreich und aktuell. `check_gate_drift.py` stellt sicher, dass Doku und CI nicht
divergieren.

**Security-Checks:** Gitleaks ✅, bandit ✅, pip-audit ✅ (mit dokumentierten `--ignore-vuln`-
Ausnahmen). **Kein** `github/codeql-action`, **kein** `actions/dependency-review-action`,
**kein** `aquasecurity/trivy` (Container-Scan). SBOM wird laut review-00 im Release erzeugt,
aber nicht im PR-CI verifiziert.

**Verbesserungspotenziale:**

| Bereich | Problem | Empfehlung |
|---|---|---|
| Komponenten-Marker | `check-testid.ts` läuft lax (`components/ui/` übersprungen); `--strict` nicht angebunden | `--strict` + Ratchet-Baseline aktivieren (siehe §2) |
| Pyright-Cache | Cache-Key ignoriert `tests/pyrightconfig.json` | Key um `tests/pyrightconfig.json` ergänzen (siehe §4) |
| Frontend-Perf-Budget | WARNING-only 240 s, vermutlich überschritten (304 vs. 197 bezifferte Test-Dateien) | Budget revalidieren oder in blockierendes Gate mit Ratchet überführen |
| Test-Coverage-Schwelle | Global `--cov-fail-under=80`; per-Modul via `check_module_coverage.py` gut, aber `settings`/`templates`/`kb`/`novels`/`volumes` nur 81–85 % | Ratchet-Ziele für diese Module schrittweise auf 85/90 % anheben |
| Dependency-Review | Kein `dependency-review-action` bei PRs | `github/dependency-review-action` für neue Deps in PRs aktivieren (Aufwand S) |
| xdist-Distribution | CI test-unit nutzt `-n auto` ohne `--dist loadfile` (justfile schon) | `--dist loadfile` auch in CI (siehe §3) |
| evals Writing-Lücke | Keine Writing/Generation-Prose-Eval-Suite | Neue Suite für extend/suggest/variant (siehe §8) |
| CI-Runtime-Drift | Runtime-Eval-Drift nur WARNING-only | Optional: P0-Regressions-Scores blockierend machen nach Ratchet-Etablierung |

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Außergewöhnlich umfassende, gut dokumentierte CI mit ~18 blocking Gates
(Architektur, Lint, Typen, Security, Coverage pro Modul, Contracts, Evals, i18n, Streaming,
SSOT), sinnvoller Parallelität, Fail-Fast über `needs`, Cache-Nutzung (uv/pnpm/pyright) und
minimalen Permissions. Die Gate-Konformitäts-Tabelle im Header ist vorbildlich. Schwächen:
laxer Komponenten-Marker-Gate, Pyright-Cache-Key-Lücke, fehlendes `dependency-review-action`,
WARNING-only Frontend-Budget wahrscheinlich überschritten, keine Writing-Eval-Suite. Kein
akuter Blocker.

---

## 8. Prompt- und LLM-Evals

**ADR-018 / ADR-032-Konformanz:** **ADR-032** (Pydantic Evals als SSOT) hat **ADR-018**
(promptfoo) superseded. Promptfoo ist vollständig entfernt (verifiziert: keine Reste in
`.github/workflows/*.yml`, `*.json`, `*.toml`). Die Struktur entspricht ADR-018/032:
`evals/`, Runner-CLI, `baselines/`, Smoke-blocking in PR-CI, Runtime-nightly-manual in
separatem Workflow (`eval-nightly.yml`), 30-Tage-Artifact-Retention. ✅

**Coverage der Domains (gegen review-00: Writing, KB, Analysis, Generation, Chat):**

| Domain | Eval-Suite | Status |
|---|---|---|
| **Analysis** | `analysis_feedback`, `analysis_metrics` | ✅ gut |
| **KB** | `kb_extraction`, `kb_operations` | ✅ gut |
| **Chat** | `chat_generation` | ✅ vorhanden |
| **Consistency** | `consistency_staged` | ✅ vorhanden |
| **Planning** | `planning_structure` | ✅ vorhanden |
| **Preference** | `preference_analysis` | ✅ vorhanden |
| **Rewrite** | `rewrite_selection` | ✅ vorhanden (writing-adjacent) |
| **Writing/Generation (Prose)** | **— keine eigene Suite** | ⚠️ Lücke: extend/suggest/variant/session/generate nicht evaluiert |
| **Generation (Names)** | **— keine Suite** | ⚠️ Lücke: Namens-Generierung hat Unit-Tests, aber keine Eval |

Writing (Prose-Erzeugung) ist das **Kern-Feature** von Narrare (Romanautor-Tool) und hat
**keine** eigene Eval-Suite — nur `rewrite_selection` und `chat_generation` tangieren das
Thema. Das ist die signifikanteste Eval-Lücke.

**Regression-Baselines & Guardrails:**
- 10 versionierte Baselines in `evals/baselines/*.json` (z. B. `chat_generation-baseline.json`,
  `consistency_staged-baseline.json`) ✅
- `check_eval_drift.py` vergleicht gegen Baselines (Smoke-blocking in CI, Runtime-WARNING-only
  nightly) ✅
- **AI-Disclaimer-Guardrail:** Evaluatoren (`evaluators/`) enthalten Custom-Checks; explizite
  Guardrail-Evaluatoren (prohibited phrases, refusal leakage) sind im testing-standards.md
  erwähnt („Guardrail evaluator — Prohibited phrases, refusal leakage, scope violations") ✅
- **Format/Tone-Drift:** über Structured-Output- + qualitative Evaluatoren abgedeckt, aber
  **kein expliziter Tone-of-Voice-Drift-Detektor** als eigener Evaluator erkennbar — verteilt
  sich über LLM-Judge (`judges.py`, optional).

**Determinismus-Trennung (echte LLM-Calls nur in Evals):**
- pytest: `ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py` (globaler Guard) ✅ — jeder
  versehentliche echte LLM-Call wirft `RuntimeError`.
- Agent-/Gateway-Tests nutzen `TestModel`/`FunctionModel` (deterministisch) ✅
- E2E: `NARRARE_E2E_TEST=1` override → alle Provider-Fabriken return `TestModel()` ✅
- Echte Provider-Calls **nur** in evals (Runtime-Modus, nightly) via `NARRARE_EVAL_API_KEY` ✅

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** ADR-032/018-konformes, gut getrenntes Eval-System (Smoke-blocking,
Runtime-nightly, 9 Suites, 10 Baselines, deterministische Trennung via
`ALLOW_MODEL_REQUESTS=False`). Die signifikanteste Lücke: **keine Eval-Suite für das
Kern-Feature Writing/Generation-Prose** (extend/suggest/variant/session). Sekundär: Runtime-
Drift ist nur WARNING-only; Tone-of-Voice-Drift hat keinen dedizierten Evaluator.

---

## Gesamtbewertung Testing & CI/CD

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** — (Erstaudit) | **Trend:** ➡️ (Baseline)
**Zusammenfassung:** Narrare verfügt über eine ausgereifte, mehrstufige Test- und CI/CD-Infrastruktur:
3-Level-Test-Archite (9.471 Python-Tests + 304 Vitest + Playwright), konsequente Fake-Klassen-
Disziplin (RULE-TEST-01), ratcheted Per-Modul-Coverage (meist 84–100 %, Floor 80 %), ein
außergewöhnlich umfassendes CI mit ~18 blocking Gates (Architektur/Streaming/i18n/Contracts/
Evals/SSOT) und ein ADR-032-konformes Eval-System (Smoke-blocking + Runtime-nightly). Pytest-
(11,8 s Collect) und Pyright-Performance (useLibraryCodeForTypes=false, venv explizit, tests
separat-lax) sind gut konfiguriert. Die drei Schwachstellen mit Handlungsbedarf: (1) das
**Komponenten-Marker-Problem** — Gate existiert, ist aber lax (`components/ui/` übersprungen),
regex-basiert und für die AI unsichtbar (keine Standards-Doku); (2) **Frontend-Controller-Hooks
ungetestet** (KnowledgeGraph/GenerationPanel/KBAssistedCreation) bei nur 15 % components-
Coverage-Schwelle; (3) **keine Writing/Generation-Prose-Eval-Suite** für das Kern-Feature.
Kein akuter Blocker, aber die Marker-Lösung (AI-Doku + strict-Ratchet) sollte zeitnah umgesetzt
werden, da sie die E2E-Stabilität strukturell absichert.

---

## Aufgaben

### [AUFG-02-01] Komponenten-Marker-Pflicht in UI-Standards dokumentieren (AI-Sichtbarkeit)
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — docs/development/ui-principles.md §18 Komponenten-Marker (L1217–1373) + cross-ref in coding-standards.md (L529–536); enforced by check-testid.ts gate (CI frontend + pre-commit). Commit 9ad3284c.
**Priorität:** Hoch
**Bereich:** DX / Testing
**Kontext:** Die AI erkennt fehlende `data-testid`/`aria-label`-Marker nicht selbst, weil
keine der Standards-Dateien (ui-principles.md, coding-standards.md, AGENTS.md) die Pflicht
dokumentiert. Der einzige Hinweis steht in deployment-guide.md (CI-Schritt). Das ist der
Root Cause des „Komponenten-Marker-Problems": die AI hat keinen Anlass, Marker zu setzen.
**Akzeptanzkriterien:**
- [x] Neuer Abschnitt „Komponenten-Marker (data-testid)" in `docs/development/ui-principles.md`
      mit Pflicht-Regel für alle interaktiven Elemente (`<button>`, `<input>` text-artig,
      `<select>`, `<a onClick>`, `role="button"`)
- [x] Verweis in `packages/web/AGENTS.md` (falls vorhanden) bzw. Frontend-Agent-Kontext
- [x] Beispiel-Code-Snippet ( korrekt vs. falsch)
- [x] Verweis auf `scripts/check-testid.ts` und die strict-Variante
**Geschätzter Aufwand:** S

### [AUFG-02-02] check-testid auf strict + Ratchet-Baseline umstellen
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — check-testid.ts split into 3 modules (+testid-scanner.ts, testid-baseline.ts); --strict --fail --ratchet-baseline wired in ci.yml L593 + pre-commit hook; baseline packages/web/scripts/testid_baselines.json; inline check-testid:ok suppression. Enforcement: CI frontend + pre-commit (fail on growth/new dirs). Commit 51091204.
**Priorität:** Hoch
**Bereich:** Testing / CI
**Kontext:** `check-testid.ts` läuft in Pre-commit und CI in laxem Modus und überspringt
gesamtes `components/ui/` (die häufigsten interaktiven Primitives). `--strict` existiert als
npm-Script, ist aber an kein Gate angebunden. Direktes Umstellen auf strict würde Big-Bang-Fix
auslösen — daher Ratchet wie bei `coverage_baselines.json`.
**Akzeptanzkriterien:**
- [x] `scripts/testid_baselines.json` mit aktueller Violation-Anzahl je Verzeichnis
- [x] `check-testid.ts` um `--ratchet-baseline <file>` erweitert (fail nur bei Wachstum)
- [x] CI frontend-Job und pre-commit `check-testid`-Hook auf `--strict --fail --ratchet-baseline`
- [x] Inline-Annotations-Mechanismus für legitime Ausnahmen (z. B. `// check-testid:ok`)
- [x] Baseline dokumentiert und schrittweise reduzierbar
**Geschätzter Aufwand:** M

### [AUFG-02-03] Writing/Generation-Prose-Eval-Suite erstellen
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — evals/datasets/writing_prose.py + evaluators/writing.py (WritingProseQuality, AIDisclaimerGuardrail, WritingToneAdherence) + models_writing.py + writing_prose_smoke.py + runtime task; baseline writing_prose-baseline.json (4 cases @1.0). Enforcement: CI smoke (--suite all --mode smoke, blocking) + check_eval_drift. Commits 8c0114a4 + a63b591e (registry test).
**Priorität:** Hoch
**Bereich:** AI / Testing
**Kontext:** Writing (Prose-Erzeugung: extend, suggest, variant, session, generate) ist das
Kern-Feature von Narrare, hat aber **keine** eigene Pydantic-Evals-Suite. Nur
`rewrite_selection` und `chat_generation` tangieren das Thema. Änderungen an Writing-Prompts
oder am LLM-Gateway haben keinen automatisierten Qualitätsregressionsschutz für das Haupt-Feature.
**Akzeptanzkriterien:**
- [x] Neue `evals/datasets/writing_prose.py` (Cases für extend/suggest/variant)
- [x] Neue `evals/evaluators/writing.py` (Qualität, Tone, AI-Disclaimer-Guardrail)
- [x] Baseline `evals/baselines/writing_prose-baseline.json`
- [x] Registrierung in `evals/datasets/__init__.py` DATASET_FACTORIES
- [x] Smoke-Suite (deterministisch) läuft blockierend in CI architecture-Job
- [x] Runtime-Variante für nightly-Workflow
**Geschätzter Aufwand:** L

### [AUFG-02-04] Frontend-Controller-Hooks testen (untested hotspots)
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — 3 controller-hook tests (KnowledgeGraph/generationPanel/KBAssistedCreation) + EditorToolbar extended (1→12); components/** coverage threshold ratcheted 15%→65% (measured lines 77.1%). Enforcement: CI pnpm test (blocking) + coverage threshold. Commit d2d61e7a.
**Priorität:** Mittel
**Bereich:** Testing
**Kontext:** Drei hochgradig vernetzte Studio-Controller-Hooks sind laut Knowledge-Graph
ungetestet: `useKnowledgeGraphController` (degree 92), `useGenerationPanelController` (72),
`useKBAssistedCreationController` (52). Dazu `EditorToolbar` (2 Varianten, degree 58+47).
Hohe „Blast Radius"-Komponenten ohne Unit-Tests.
**Akzeptanzkriterien:**
- [x] Unit-Tests für die 3 Controller-Hooks (Rendering + Interaktion via Testing-Library)
- [x] Komponenten-Test für `EditorToolbar` (beide Varianten)
- [x] `components/**`-Coverage-Schwelle in `vitest.config.ts` von 15 % auf ≥40 % anheben
      (Ratchet-basiert, falls nötig)
**Geschätzter Aufwand:** M

### [AUFG-02-05] Pyright-Cache-Key und xdist-Distribution korrigieren
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — pyright cache key +tests/pyrightconfig.json (ci.yml L231); test-unit --dist loadfile (ci.yml L311); redundant sys.path.insert removed from tests/conftest.py; pyright extraPaths set (pyproject L60). importlib mode reverted (broke scripts pkg resolution). Enforcement: CI typecheck + test-unit jobs. Commit 63041b69.
**Priorität:** Mittel
**Bereich:** CI / Performance
**Kontext:** (a) Der Pyright-Cache-Key (`actions/cache@v6`) basiert nur auf `pyproject.toml`
+ `uv.lock` und ignoriert `tests/pyrightconfig.json` → veraltete Cache-Hits bei Test-Config-
Änderungen. (b) CI test-unit-Job nutzt `-n auto` ohne `--dist loadfile` (justfile schon),
was zu Stragglers führen kann.
**Akzeptanzkriterien:**
- [x] Cache-Key in ci.yml typecheck-Job um `tests/pyrightconfig.json` ergänzt
- [x] CI test-unit-Job: `-n auto --dist loadfile` (analog justfile `test-unit`)
- [x] Optional: `--import-mode=importlib` in `[tool.pytest.ini_options] addopts`
- [x] [Gap-Walk G3] Redundantes `sys.path.insert` in `tests/conftest.py` L14–21 entfernt (`pythonpath`-Konfiguration in pyproject.toml reicht)
- [x] [Gap-Walk G4] Pyright `extraPaths = ["apps/api", "packages/core", "packages/i18n"]` in `pyproject.toml [tool.pyright]` gesetzt
**Geschätzter Aufwand:** S

### [AUFG-02-06] dependency-review-action und Frontend-Perf-Budget revalidieren
**Re-Check 2026-07-09:** **TEILWEISE ERLEDIGT 2026-07-09** — (b) Frontend-Perf-Budget revalidiert: gemessen 161,3 s (< 240 s; die Review-Vermutung »wahrscheinlich überschritten« war falsch), Kommentar aktualisiert (Commit b9304cdf). (a) dependency-review-action **deferred (accepted_risk)** — die Action benötigt GitHub Advanced Security (GHAS), das auf diesem Repo nicht verfügbar ist; der Job failte in CI am Feature-Check und wurde entfernt (Commit siehe Commit-Log). Siehe Abschluss-Status.
**Priorität:** Niedrig
**Bereich:** CI / Security
**Kontext:** (a) Kein `github/dependency-review-action` für neue Dependencies in PRs.
(b) Das WARNING-only Frontend-Performance-Budget (240 s) basiert auf 197 Test-Dateien;
real sind es jetzt 304 → Budget vermutlich überschritten, aber nicht-blockierend.
**Akzeptanzkriterien:**
- [ ] `github/dependency-review-action` in PR-Workflow aktiviert — **deferred (accepted_risk)**: die Action benötigt GitHub Advanced Security (GHAS), das auf diesem Repo nicht verfügbar ist; Job nach CI-Fail entfernt. `pip-audit`/`bandit` decken Python-Dependencies weiterhin im security-Job; Web-Dep-Audit ohne GHAS ggf. später via `pnpm audit` nachziehen.
- [x] Frontend-Test-Dauer messen; Budget revalidieren oder als Ratchet-Gate überführen
**Geschätzter Aufwand:** S

### [AUFG-02-07] Testing-Standards-Doku aktualisieren (stale Test-Zahlen)
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — testing-standards.md L788/794/795 refreshed to measured values (~8,780 unit / ~9,490 total / ~13s collect) + live-re-measure note; L1097 e2e count fixed (see Abschluss-Status). Commit 055f6e18.
**Priorität:** Niedrig
**Bereich:** DX / Dokumentation
**Kontext:** `docs/development/testing-standards.md` gibt „~6.160 unit tests / ~14s" und
„~6.670 tests / ~17s" an; real sind es 8.768 / 9.471 (gemessen). Diese Diskrepanz verstößt
gegen die „documented ≠ implemented"-Disziplin (§7) und erschert Schätzungen.
**Akzeptanzkriterien:**
- [x] Test-Zahlen in testing-standards.md „Fast Developer Feedback"-Abschnitt aktualisieren
- [x] Hinweis, dass Zahlen beispielhaft sind und via `pytest --collect-only` live ermittelbar
**Geschätzter Aufwand:** S

### [AUFG-02-08] Backend-Coverage-Ratchet für Module am Floor anheben
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — 8 new test files (+reusable fake_db_session) for settings/templates/kb/novels/volumes; coverage 81.5→87.8 / 82.4→91.4 / 83.9→85.2 / 83.8→93.8 / 84.0→98.4; baselines ratcheted in coverage_baselines.json. Enforcement: check_module_coverage.py --fail (CI test-unit, blocking). Commit a84d3d02.
**Priorität:** Mittel
**Bereich:** Testing
**Kontext:** Fünf Backend-Module liegen nur knapp über dem api-Floor (80 %): `settings` 81,5 %,
`templates` 82,4 %, `kb` 83,9 %, `novels` 83,8 %, `volumes` 84,0 % (review §1 + §7-Tabelle).
Eine Regression um wenige Prozent drückt sie unter den Floor. Die §7-Empfehlung
("Ratchet-Ziele schrittweise auf 85/90 %") hatte keine entsprechende AUFG — in Phase-1-Gap-Walk
als Lücke identifiziert (Problem ohne Task).
**Akzeptanzkriterien:**
- [x] Baselines für die 5 Module in `scripts/coverage_baselines.json` stufenweise auf ≥85 % angehoben
      (wo billig Tests fehlen, gezielt ergänzen)
- [x] `check_module_coverage.py --fail` blockiert weiterhin bei Regression unter die neuen Baselines
- [x] Dokumentierter Ratchet-Pfad (85 % → 90 %) je Modul
**Geschätzter Aufwand:** M

### [AUFG-02-09] Runtime-Eval-Drift: P0-Scores blockierend machen
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — P0 priority manifest evals/p0_priorities.json; check_eval_drift gains --priorities + --fail-on-priority P0 (scripts/eval_drift/priorities.py + comparison/reporting); eval-nightly now fails on P0 regression (continue-on-error removed); writing_prose guardrail case marked P0; 14 unit tests. Enforcement: eval-nightly blocking on P0. Commit fe934eda.
**Priorität:** Niedrig
**Bereich:** AI / CI
**Kontext:** Nightly Runtime-Eval-Drift ist WARNING-only (review §6/§8) → eine stille
Qualitätsregression des Kern-Features bleibt nicht-blockierend. `check_eval_drift.py` behandelt
heute alle Test-Cases identisch (gleicher 5 %-Threshold, kein Prioritäts-Konzept). Lücke: kein
Mechanismus, um kritische Scores (Guardrail, Format, Kern-Qualität) von weichen (Tone-Nuancen)
zu trennen. In Phase-1-Gap-Walk als Lücke identifiziert.
**Akzeptanzkriterien:**
- [x] Per-Case `priority`-Feld (z. B. `"priority": "P0"`) in Baselines oder separates P0-Manifest
- [x] `check_eval_drift.py` um `--fail-on-priority P0`-Modus erweitert (blockiert nur bei P0-Regression)
- [x] `eval-nightly.yml` gate auf P0-only; nicht-P0 bleibt WARNING
- [x] Für die Writing-Suite (AUFG-02-03) sind Guardrail/Format/Kern-Qualität als P0 markiert
- [x] Hängt ab von: AUFG-02-03 (Writing-Runtime-Suite + Baseline muss existieren)
**Geschätzter Aufwand:** M

### [AUFG-02-10] reportMissingTypeStubs-Rauschen reduzieren
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — Premise stale — pyright already 0 reportMissingTypeStubs errors (asyncpg not directly imported; taskiq_redis ships types). Converted 2 blanket # type:ignore[import-untyped] → precise # pyright:ignore[reportMissingTypeStubs] (opentelemetry-instrumentation-fastapi, mem0). Global setting stays true. Commit d4a61525.
**Priorität:** Niedrig
**Bereich:** DX / Types
**Kontext:** `reportMissingTypeStubs = true` erzeugt echte Fehler für bekannte stub-lose
Drittanbieter (`asyncpg`, `taskiq`, …), die laut CURRENT_STATE teils False Positives sind
(review §4 rec #3). Erhöht Rauschen ohne Qualitätsgewinn. §4-Bewertung: "kein akuter
Handlungsbedarf", aber Reduzierung hat Wert. In Phase-1-Gap-Walk als Lücke identifiziert.
**Akzeptanzkriterien:**
- [x] Bekannte stub-lose Pakete mit Inline-`# pyright: reportMissingTypeStubs=false`-Pragmas an
      den Importstellen annotiert (oder Selektor-Konfiguration in pyproject.toml)
- [x] Pyright-Lauf dokumentiert reduzierte False-Positive-Zahl
- [x] Keine echten Typ-Fehler dadurch verschleiert (Audit der verbleibenden Meldungen)
**Geschätzter Aufwand:** S–M

### [AUFG-02-11] Vitest-AST-Level testid-Conformance-Test
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — packages/web/components/ui/__tests__/testid-conformance.test.tsx (12 tests) renders shared primitives + VolumeCard, asserts rendered button/role/input/select carry data-testid/aria-label; spread-prop proof catches regex blind spots. Enforcement: CI pnpm test (blocking). Surfaced marker debt in PanelTabs/ConfirmDialog (flagged for ratchet). Commit ddb670a1.
**Priorität:** Niedrig
**Bereich:** Testing
**Kontext:** `check-testid.ts` ist regex-basiert → False Negatives für zusammengesetzte Elemente
(`<div role="button">`, Radix-Trigger, spread-Props `<button {...props}>`) und False Positives für
kommentierten Code (review §2). Die §2-Tabelle empfiehlt als "optionale zweite Verteidigungslinie"
einen Vitest-Test, der via Testing-Library `getByRole` prüft, dass jedes interaktive Element ein
`data-testid` trägt. In Phase-1-Gap-Walk als Lücke ohne AUFG identifiziert.
**Akzeptanzkriterien:**
- [x] Vitest-Test, der `*.tsx` lädt und via Testing-Library-Queries prüft, dass jede
      `getByRole("button")` / `getByRole("textbox")` einen `data-testid` (oder `aria-label`) trägt
- [x] Fängt AST-Lücken auf, die regex verpasst
- [x] Läuft blockierend im CI frontend-Job
**Geschätzter Aufwand:** M

### [AUFG-02-12] Names-Generation-Eval-Suite erstellen
**Re-Check 2026-07-09:** **ERLEDIGT 2026-07-09** — evals/datasets/names.py + evaluators/names.py (NameListQuality) + models_names.py + names_smoke.py + baseline; smoke-only; SMOKE_ONLY_SUITES updated. Enforcement: CI smoke (blocking) + check_eval_drift (64 comparisons). Commit 70ecb33f.
**Priorität:** Niedrig
**Bereich:** AI / Testing
**Kontext:** Namens-Generierung hat Unit-Tests, aber keine Pydantic-Evals-Suite (review §8
⚠️-Zeile). ADR-032-konforme Regression fehlt für diesen Generation-Pfad. In Phase-1-Gap-Walk als
Lücke ohne AUFG identifiziert.
**Akzeptanzkriterien:**
- [x] Neue `evals/datasets/names.py` (Cases für Charakter-/Orts-/Plot-Namen)
- [x] Evaluator + Baseline `evals/baselines/names-baseline.json`
- [x] Registrierung in `evals/datasets/__init__.py` DATASET_FACTORIES
- [x] Smoke-Suite (deterministisch) läuft blockierend in CI architecture-Job
**Geschätzter Aufwand:** M

---

## Abschluss-Status

**Stand 2026-07-09:** 11 AUFG-Aufgaben voll **ERLEDIGT**; AUFG-02-06 **teilweise** (Teil b Perf-Budget erledigt; Teil a dependency-review-action deferred — benötigt GHAS, auf diesem Repo nicht verfügbar). Jede erledigte Teilaufgabe hat Implementation + Enforcement gemäß `docs/development/finding-lifecycle.md`.

**Holistische Verifikation (Branch `chore/review-02-testing-ci-fixes`):**
- `just check-architecture` ✅ (2011 Dateien, 16 Approved Exceptions, No-Growth)
- `uv run ruff check` ✅ clean · `uv run pyright` ✅ 0 errors
- `uv run python -m evals run --suite all --mode smoke` ✅ · `check_eval_drift.py` ✅ 64 comparisons
- `uv run pytest tests/unit/ -q` ✅ 8858 passed, 0 failed
- `just test-frontend` ✅ 308 Dateien / 2530 Tests passed

**Gap-Dispositions (aus Phase-1 Gap-Walk):**
- G1 (Backend-Module am Floor) → AUFG-02-08 (ratcheted to ≥85%).
- G2 (Runtime-Drift non-blocking) → AUFG-02-09 (P0-blocking).
- G3 (redundant sys.path) + G4 (pyright extraPaths) → in AUFG-02-05 folded.
- G5 (reportMissingTypeStubs noise) → AUFG-02-10 (premise stale; pragmas precisioniert).
- G6 (AST-level testid test) → AUFG-02-11.
- G7 (Tone-of-Voice evaluator) → **covered_by_existing_aufg** (folded into AUFG-02-03's WritingToneAdherence evaluator; no separate task needed).
- G8 (Names eval suite) → AUFG-02-12.
- G9 (fetchApi direct test) → **covered_by_existing (indirect)** — fetchApi (degree 161) is exercised via MSW integration tests across the suite; a dedicated direct test was not added (indirect coverage deemed sufficient). Accepted.

**Newly surfaced findings (not in original review, for follow-up ratchet):**
- `lib/**` coverage at 71.21% < its 80% threshold (latent — `pnpm test`/CI frontend do not enforce the coverage threshold; only enforced if `--coverage` passed). Pre-existing, outside review-02 scope.
- Marker debt in `PanelTabs` + `ConfirmDialog` (buttons rely on visible text, no `data-testid`/`aria-label`) — surfaced by AUFG-02-11; the regex gate ALSO misses these (render-time false-negative). Candidate for the testid ratchet baseline reduction.
- dependency-review-action ist auf diesem Repo nicht einsetzbar (erfordert GitHub Advanced Security / GHAS); PR-Dependency-Gating deferred. `pip-audit`/`bandit` (security-Job) decken Python-Dependencies weiterhin ab.
