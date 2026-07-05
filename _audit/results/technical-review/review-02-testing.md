# Review 02 – Testing & CI/CD

> Aktualisiert am 2026-06-29 durch NarrarePlatformSpecialist. Grundlage:
> `_audit/results/technical-review/review-00-kontext.md`,
> `_audit/results/technical-review/review-01-architektur.md`,
> `docs/_shared/CONSTRAINTS.md`, `docs/development/testing-standards.md`,
> `docs/development/deployment-guide.md`, aktuelle CI-/Test-Konfiguration und
> frische lokale Verifikation. Keine Commits, kein `--no-verify`.
>
> **Re-Verifikation 2026-07-05:** Alle Befunde in diesem Review wurden am
> 2026-07-05 gegen den aktuellen HEAD (Commit `1249dca1`) erneut geprüft. Dabei
> stellte sich heraus, dass AUFG-02-01 und AUFG-02-02 die beschriebenen Blocker
> im HEAD nicht mehr aufweisen (teils erledigt, teils falsch diagnostiziert) –
> siehe Markierungen an den jeweiligen Aufgaben. Als neuer, bislang
> unbeanstandeter Befund kam `coverage_baselines.json` hinzu (AUFG-02-05). Die
> Lektion dazu steht in der neuen Sektion „Ursachenanalyse &
> Vermeidungs-Maßnahmen". Reviews müssen grundsätzlich gegen den HEAD-Stand
> verifiziert werden, nicht gegen den Stand zum Erstellungsdatum.

## Methodik & ausgeführte Prüfungen

- **Graph-first ausgeführt:** `get_minimal_context`, `list_graph_stats`,
  `list_communities`, `get_knowledge_gaps`, `find_large_functions` und
  `semantic_search_nodes` vor gezielten Reads/Globs/Commands.
- **Graph-Snapshot:** 26.084 Nodes, 185.730 Edges, 2.777 Files; Sprachen Python,
  Bash, TypeScript, TSX, JavaScript; 11.631 Test-Nodes; Graph-Update
  2026-06-29T18:23:23.
- **Graph-Befunde:** Top-Communities bleiben testlastig (`tests-it:renders`,
  mehrere `tests-when`-Cluster). Knowledge-Gaps-Ausgabe war groß/truncated,
  maschinell zusammengefasst: 50 isolated nodes, 2.169 thin communities,
  20 untested hotspots. Produktiv relevant sind v. a. Frontend-Hubs
  `fetchApi`, `useTipTapEditorController`, `useKnowledgeGraphController`,
  `useGenerationPanelController`; viele weitere Treffer sind Tooling/Alembic.
- **Root Cause dieses Review-Updates:** Die vorherige Review-02-Datei war in
  mehreren Punkten überholt. Coverage ist inzwischen global und modular stärker
  enforced, Eval-Smoke läuft in PR-CI, Nightly-Runtime-Evals existieren, AI-UX und
  Frontend-Size aus Review 01 sind aktuell grün. ~~Neue harte Blocker liegen jetzt
  in (a) einer Prompt-Modul-Coverage-Ratchet-Regression und (b) einem
  Komponenten-Marker-Checker-False-Positive, das trotzdem CI-blocking ist.~~
  **Korrektur 2026-07-05:** Beide genannten „harten Blocker" existieren im HEAD
  nicht in der beschriebenen Form (siehe AUFG-02-01, AUFG-02-02). Der tatsächlich
  offene Befund in der Coverage-Fläche ist der versehentlich geschrumpfte
  Ratchet-Baseline-Satz (AUFG-02-05).
- **Alternativen betrachtet:**
  1. Alte AUFG-Liste beibehalten — verworfen, weil sie erledigte oder ersetzte
     Befunde als aktuell erscheinen lässt.
  2. Nur rote Commands dokumentieren — verworfen, weil der Prompt auch Struktur,
     Standards und CI-Konfiguration verlangt.
  3. Gewählt: Review vollständig gegen aktuelle Evidenz konsolidieren und nur
     aktuelle, belegte Aufgaben führen.

### Ausgeführte Checks/Commands

| Check | Ergebnis |
|---|---|
| `uv run pytest --collect-only -q` | ✅ 9.043 Tests gesammelt in 11.71s |
| `uv run pytest tests/unit/ --cov --cov-report=xml --cov-report=term-missing:skip-covered --cov-fail-under=80 -n auto -q` | ✅ 8.341 passed, 3 skipped, Coverage 88.94%, 125.08s |
| `uv run python scripts/check_module_coverage.py --fail` | ❌ 1 Regression: `packages/core+apps/api/prompts/` 93.4% < Baseline 97.1% |
| `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing` | ✅ 30 Services geprüft, 0 missing test files, 0 low coverage |
| `uv run pyright --stats` | ✅ 0 Errors / 0 Warnings, 1.897 checked files, 41.196s |
| `uv run python scripts/check_pytest_collection_performance.py` | ✅ Unit-Collection 8.344 Tests in 18.5s, unter 20s |
| `cd packages/web && pnpm test` | ✅ 274 Test Files, 2.287 Tests passed, aber 181.98s und viele React-`act(...)`/controlled-input-Warnings |
| `uv run python scripts/check_test_performance.py --duration 181.98 --threshold 130` | ⚠️ warning-only: 182.0s > 130s |
| `cd packages/web && pnpm exec tsx scripts/check-testid.ts --fail` | ❌ 335 Dateien geprüft, 1 Marker-Verstoß: `StyleVariantPicker.tsx` |
| `just check-ai-ux` | ✅ 44 Passes, 0 Violations, 3 governed exclusions |
| `just check-frontend-size` | ✅ 0 current / 0 baseline / 0 new RULE-04 Frontend-Debt |
| `uv run python -m evals run --suite all --mode smoke --results-dir /tmp/opencode/narrare-evals-review02-20260629` | ✅ alle ausgeführten Smoke-Suites mit Assertions `✔` / 100%-Averages |
| `uv run python scripts/check_eval_drift.py` | ✅ 57 Baseline-Vergleiche innerhalb 5% |
| `just check-prompts-strict` | ✅ 48/48 System-Prompts gültig, Warning-Ratchet 0 |

**Re-Verifikation 2026-07-05 (gegen HEAD `1249dca1`):**

| Check | Ergebnis |
|---|---|
| `git show 140016ed:scripts/coverage_baselines.json` | ✅ Vorherige Baseline mit 49 Modulen wiederhergestellt (writing auf 95.5 angehoben). Siehe AUFG-02-05. |
| `npx tsx scripts/check-testid.ts --fail` (StyleVariantPicker) | ✅ `violations: []`, Exit 0. `LOOKAHEAD = 8` (nicht 3), `aria-label` liegt 4 Zeilen unter öffnendem `<select>` – also *im* Fenster. AUFG-02-02 war falsch diagnostiziert. |
| Subset-Guard in `scripts/_coverage_model.py::save_baselines` | ✅ Implementiert + 4 Unit-Tests grün. Verhindert künftiges versehentliches Schrumpfen wie in `1a5a833b`. |
| `uv run python scripts/check_module_coverage.py --update-baselines` (writing-only XML) | ✅ Guard schlägt zu: „Refusing to shrink coverage baselines …", Exit 1. |

**Nicht ausgeführt:** Integration- und E2E-Vollsuite wurden lokal nicht gestartet,
weil sie Docker/full-stack Services benötigen und in CI separate Postgres/Redis- bzw.
Full-Stack-Jobs besitzen. Es wird daher kein lokaler PASS für Integration/E2E
behauptet.

---

## 1. Backend-Test-Suite – Struktur & Abdeckung

**Bewertung:** ⭐⭐⭐⭐ `Struktur stark; ein aktueller Coverage-Ratchet-Blocker`

**Befunde:**
- Die Teststruktur ist klar getrennt: `tests/unit/`, `tests/integration/`,
  `tests/e2e/`. Aktuelle Zählung: 832 Python-Testdateien — 736 Unit, 84
  Integration, 12 E2E.
- `pyproject.toml` setzt `testpaths = ["tests"]`, explizite
  `python_files/classes/functions`, `pythonpath`, `pytest-asyncio` Session-Loops,
  `pytest-timeout`, Marker `unit`, `integration`, `e2e`, `requires_db` und
  `norecursedirs`.
- Fresh Unit-Coverage-Lauf: 8.341 passed / 3 skipped, Total Coverage 88.94%,
  globaler CI-Floor 80% erreicht.
- RULE-10-Strukturgate ist grün: `scripts/check_test_coverage_gaps.py` prüft 30
  Services und findet 0 fehlende Testdateien / 0 low coverage.
- **~~Aktueller Blocker~~ (Stand 2026-06-29, im HEAD erledigt):**
  `scripts/check_module_coverage.py --fail` meldet eine
  Ratchet-Regression: `packages/core+apps/api/prompts/` liegt bei 93.4% gegen
  Baseline 97.1%. Der globale Wert ist also grün, aber der CI-Subgate ist rot.
  **Re-Verifikation 2026-07-05:** Dieser Wert ist ein historischer Vorfall aus
  Commit `0bb8bcb3` (2026-07-01). Ein kaputter AsyncMock in
  `test_prompt_routers.py` ließ `stream_live_test` eine Coroutine statt eines
  Async-Iterators zurückgeben; nach Fix lag die prompts-Coverage bei 98.4% und
  die Baseline wurde angehoben. Der hier zitierte 97.1%-Wert ist ein Snapshot
  vom Zustand Anfang Juni. → Siehe AUFG-02-01 (als erledigt markiert).
- Auffällige Low-Coverage-Dateien innerhalb der Prompt-Fläche aus dem frischen
  Coverage-Termreport sind u. a. `apps/api/narrare/prompts/deps.py` (14%),
  `apps/api/narrare/prompts/router.py` (49%),
  `router_prompt_history.py` (70%), `router_prompt_ux.py` (62%) und
  `packages/core/narrare_core/prompts/preview.py` (89%). Einige `contracts.py`-
  Dateien werden im Coverage-Report aufgeführt, aber `pyproject.toml` omittet
  `contracts.py` allgemein; die Modulregression muss am realen Coverage-XML/
  Gruppierungsmodell geprüft werden, nicht durch Baseline-Absenkung kaschiert.
  **Re-Verifikation 2026-07-05:** Zu allen genannten Modulen existieren
  Test-Dateien (`tests/unit/api/prompts/test_prompt_routers.py`,
  `test_prompt_history_service*.py`, `test_prompt_history_repository*.py`,
  `tests/unit/api/_app/test_dependencies_prompts.py`, u. a.). Die niedrigen
  Prozentzahlen lassen sich gegen die HEAD-`coverage.xml` (die nur `writing`
  enthält) nicht reproduzieren; sie sind vermutlich Artefakte des
  zwischenzeitlichen Mock-Defekts. Der echte, aktuell offene Befund in dieser
  Fläche ist AUFG-02-05 (versehentlich geschrumpfte Baseline-Datei).
- Fakes/Protocol-Conformance sind institutionalisiert: `tests/unit/test_fake_conformance.py`
  existiert, `tests/fakes/`-Community ist im Graph sichtbar, und die Testing-SSOT
  verbietet bare `MagicMock` für Domain-Dependencies.
- Cross-Layer-Contracts sind sichtbar: `tests/unit/api/test_*_contract.py` und
  `test_*_router_contract.py` schützen RULE-17/RULE-18-Flächen.
- Integrationstests laufen in CI mit realem `pgvector/pgvector:pg17` und
  `redis:8-alpine`; das entspricht der Docker-only-Regel. Lokale Integration-/E2E-
  Ergebnisse wurden in diesem Review nicht behauptet.

---

## 2. Komponenten-Marker-Problem

**Bewertung:** ⭐⭐⭐⭐ `CI-Gate existiert und ist im HEAD aktuell grün (Re-Verifikation 2026-07-05)`
*(Vorherige Bewertung lautete ⭐⭐ „rot durch Checker-Heuristik". Diese Diagnose
war ungenau – siehe unten.)*

**Befunde:**
- Marker-Gate existiert: `packages/web/scripts/check-testid.ts`, npm-Skripte
  `check:testid`/`check:testid:strict`, und `.github/workflows/ci.yml` führt im
  Frontend-Job `cd packages/web && npx tsx scripts/check-testid.ts --fail` aus.
- ~~Aktueller lokaler Lauf ist **rot**: 335 Dateien geprüft, 1 Datei mit fehlendem
  Marker, 1 uncovered interactive element:
  `packages/web/components/studio/editor/StyleVariantPicker.tsx`.~~
  **Korrektur 2026-07-05:** Die Behauptung ist in allen drei zentralen Punkten
  unzutreffend:
  1. `LOOKAHEAD` ist in `check-testid.ts:194` **8**, nicht 3.
  2. In `StyleVariantPicker.tsx` liegt das öffnende `<select>` in Zeile 47, das
     `aria-label` in Zeile 51 – also 4 Zeilen darunter und damit *deutlich
     innerhalb* des Lookahead-Fensters von 8.
  3. Ein Live-Lauf von `npx tsx scripts/check-testid.ts --json` liefert für die
     Datei `"violations": []`, Exit-Code 0. `--fail` schlägt also **nicht** fehl.
- ~~Die Datei hat jedoch tatsächlich `aria-label={t("styleVariants.regenerateAs")}`
  auf dem `<select>` (Zeile 51). Root Cause ist nicht ein fehlender Marker im
  Produktcode, sondern die Checker-Heuristik: `check-testid.ts` sammelt nur
  `LOOKAHEAD = 3` Folgezeilen ab der öffnenden Tag-Zeile. Bei `StyleVariantPicker`
  liegt `aria-label` außerhalb dieses Lookahead-Fensters.~~ *Siehe Korrektur
  oben.*
- Warum AI/Review das ohne Tool nicht erkennt: `data-testid`/`aria-label` ist ein
  UI-/E2E-Stabilitätsvertrag, kein TypeScript-Typfehler.
- ~~`.pre-commit-config.yaml` enthält derzeit keinen `check-testid`-Hook. Damit ist
  die Markerprüfung lokal nicht so früh blocking wie in CI.~~
  **Korrektur 2026-07-05:** Ein lokaler pre-commit-Hook existiert –
  `.pre-commit-config.yaml:191-194` (`id: check-testid`).
- **Echte Restschwächen** (keine akuten Blocker):
  - Der Checker ist rein zeilen-/regex-basiert (bewusst „zero dependencies",
    `check-testid.ts:97-109`), erkennt also prinzipiell keine JSX-Scopes. Damit
    sind False Positives in Kommentaren/Strings möglich (siehe
    `components/studio/kb/KBMentionRenderer.tsx:14`, JSDoc-Kommentar).
  - Es gibt **keinen** dedizierten Regressionstest für den Checker selbst. Ein
    solcher Test wäre der richtige Ort, um den `StyleVariantPicker`-Fall
    dauerhaft abzusichern.

| Ebene | Mögliche Lösung | Aufwand |
|---|---|---|
| Pre-commit Hook | Lokalen Hook für `packages/web/scripts/check-testid.ts --fail` ergänzen, ausgelöst bei TSX-Änderungen. | S |
| Pytest-Plugin / Conftest | Nicht passend für TSX; höchstens Playwright-Selector-Registry prüfen. | M |
| CI-Check (Fail-Fast) | Bereits blocking im Frontend-Job, aktuell rot. | erledigt/rot |
| AI-Prompt-Ergänzung | UI-/Frontend-Kontext soll explizit stabile Selector/ARIA-Marker nennen. | S |
| Testfall-Template / Snippet | UI-Komponenten-Template um Selector/ARIA-Marker-Abschnitt ergänzen. | S |

**Empfehlung:** Primär den Checker nachhaltig machen (AST/JSX-Parser oder robustes
mehrzeiliges Attribut-Parsing), nicht Produktcode formatieren, um eine 3-Zeilen-
Heuristik zufriedenzustellen. Danach lokalen pre-commit-Hook ergänzen.

---

## 3. Pytest-Performance

**Bewertung:** ⭐⭐⭐⭐ `Collection aktuell im Budget, Wachstum beobachten`

**Befunde:**
- Full collection: 9.043 Tests in 11.71s.
- Warning-only CI-Performancecheck: `scripts/check_pytest_collection_performance.py`
  sammelt `tests/unit` und ist aktuell grün: 8.344 Tests in 18.5s bei 20s
  Schwellwert.
- Parallelisierung ist vorhanden: `just test` nutzt `-n auto`, `just test-unit`
  nutzt `-n auto --dist loadfile`, CI-Unit-Coverage ebenfalls `-n auto`.
- `norecursedirs` schließt u. a. `.venv`, `node_modules`, `dist`, `build`, E2E und
  Caches aus.
- Conftests sind zahlreich, aber domänennah (`tests/unit/api/*/conftest.py`,
  `tests/integration/conftest.py`, `tests/e2e/conftest.py`). Kein aktueller
  Collection-Blocker gefunden.

**Konkrete Empfehlungen:**
1. `check_pytest_collection_performance.py` warning-only beibehalten und nur nach
   mehreren Regressionsläufen blocking machen; erwarteter Nutzen: verhindert
   schleichende Import-/Fixture-Aufblähung.
2. Bei Überschreitung zuerst Collection-Hotspots messen, nicht pauschal
   `norecursedirs` erweitern; erwarteter Nutzen: nachhaltige Ursachenbehebung.
3. `just test-unit` als primären lokalen Feedbackloop weiter prominent halten;
   Integration/E2E bleiben explizite Gates.

---

## 4. Pyright-Performance

**Bewertung:** ⭐⭐⭐⭐ `Strict, sauber und unter CI-Ziel`

**Befunde:**
- `uv run pyright --stats`: 0 Errors, 0 Warnings, 1.897 checked files,
  3.464 parsed/bound files, 41.196s.
- Pyright-Konfiguration liegt in `pyproject.toml [tool.pyright]`; kein separates
  `pyrightconfig.json` existiert.
- Performancebewusst gesetzt: `include` für API/Core/i18n/scripts/tests,
  `exclude` für E2E, versteckte Verzeichnisse, `.venv`, `node_modules`,
  Build-/Cache-Artefakte, `.code-review-graph`, `.agents`, Migrationen;
  `useLibraryCodeForTypes = false`; `venvPath`/`venv` explizit.
- CI cached `.pyright/` und `**/.pyc` im Typecheck-Job und führt Pyright als
  eigenen blocking Job aus.
- Tests sind in einer eigenen Execution Environment bei Unknown-Type-Regeln
  gelockert, Produktcode bleibt strict.

**Konkrete Empfehlungen:**
1. Keine Exclusion von Produktcode als Performance-Shortcut einführen.
2. Pyright-Cache-Hitrate in CI beobachten; erst bei wiederholten kalten Läufen
   Cache-Key/Pfade anpassen.
3. Bei weiterem Wachstum `scripts/evals` nur nach Messung separieren; aktuell ist
   die Laufzeit deutlich unter dem <2min-Ziel aus Deployment Guide.

---

## 5. Frontend-Test-Suite

**Bewertung:** ⭐⭐⭐ `Funktional grün, Performance/Warning-Noise deutlich regressiert`

**Befunde:**
- Framework: Vitest 4.1.8, Testing Library, happy-dom, MSW; `vitest.config.ts`
  nutzt `pool: "threads"`, `maxWorkers: 6`, Coverage via V8.
- Aktueller Lauf: `pnpm test` — 274 Test Files, 2.287 Tests passed, 181.98s.
- Das überschreitet den aktuellen warning-only Schwellwert aus CI
  (`check_test_performance.py`, 130s) um 52s. Es ist kein funktionaler Failure,
  aber eine klare DX-/CI-Minuten-Regression.
- Viele React-Warnings erscheinen im Lauf, u. a. fehlendes `act(...)` in
  `TimelineExtractionReview.test.tsx`, `WizardStep4.test.tsx`,
  `KBInterviewView.interactions.test.tsx`, `usePromptHistory.test.tsx`,
  `useCoAuthorStyleVariant.test.tsx`; außerdem controlled/uncontrolled input in
  `SettingsView.test.tsx`.
- Anders als im alten Review wurden in diesem Lauf keine dominierenden
  `ECONNREFUSED 127.0.0.1:3000`-Logs beobachtet; dieses historische Problem wird
  daher nicht erneut als aktueller Befund geführt.
- `docs/development/testing-standards.md` ist teilweise stale: nennt Vitest 3.x
  und eine <120s/186-Dateien-Baseline, während aktuelle Runtime/CI bei Vitest 4.1.8,
  274 Dateien und 130s warning-only liegt.

---

## 6. Evaluation-Driven Development (Prompt Testing)

**Bewertung:** ⭐⭐⭐⭐ `Pydantic-Evals breit ausgebaut; qualitative Runtime bleibt Nightly/Secret-abhängig`

**Befunde:**
- ADR-032/Pydantic Evals ist aktive SSOT; alter promptfoo/ADR-018-Ansatz ist nicht
  mehr maßgeblich.
- `evals/` enthält Datasets, Tasks, Evaluators, Reports, Baselines und Results für
  `analysis_feedback`, `analysis_metrics`, `chat_generation`,
  `consistency_staged`, `kb_extraction`, `kb_operations`, `planning_structure`,
  `preference_analysis`, `rewrite_selection`.
- Secret-freie Smoke-Evals liefen lokal erfolgreich; `check_eval_drift.py` meldet
  57 Baseline-Vergleiche innerhalb 5%.
- PR-CI führt Smoke-Evals blocking im `architecture` Job aus; Driftcheck ist
  warning-only.
- Runtime-Evals sind korrekt getrennt in `.github/workflows/eval-nightly.yml`
  (schedule + workflow_dispatch) und benötigen `NARRARE_EVAL_API_KEY`.
- Rest-Risiko: Runtime-Evals skippen bei fehlendem Secret warning-only. Das ist
  für Forks sinnvoll, bedeutet aber: echte LLM-Qualitätsregressionen sind nur
  sichtbar, wenn Repository-Secret/Vars tatsächlich gepflegt sind und Nightly läuft.

---

## 7. CI/CD-Workflow (.github/workflows/ci.yml)

**Bewertung:** ⭐⭐⭐ `Sehr breit; die zwei ehemals blocking-Pfade sind im HEAD nicht mehr rot`
*(Vorherige Bewertung nannte „aktuell zwei Blocking-Pfade rot". Re-Verifikation
2026-07-05: Beide Pfade (Prompt-Coverage, Komponenten-Marker) sind im HEAD nicht
in der beschriebenen Form existent – siehe AUFG-02-01 und AUFG-02-02. Der echte
neue Befund ist AUFG-02-05.)*

**Befunde:**
- CI-Jobs in `ci.yml`: `architecture`, `lint`, `typecheck`, `security`,
  `test-unit`, `test-integration`, `update-coverage-badge`, `frontend`,
  `test-e2e`. Zusätzlich existiert `eval-nightly.yml` für Runtime-Evals.
- Fail-fast-Struktur: `architecture` zuerst; `lint`, `typecheck`, `security`,
  `frontend` hängen daran; Unit/Integration hängen an Lint/Typecheck;
  E2E läuft nur auf main push.
- Caches: uv, pnpm/node, Pyright; Concurrency mit `cancel-in-progress`.
- Architecture-Gates sind umfangreich: Architektur, Prompt Surface, Version Drift,
  Exception Sync, Configuration Matrix, OpenAPI Drift, Prompt Structure,
  Invocation Probes, Adoption, Locale, Doc/Registry/Gate Drift, Governance,
  Streaming, AI-Interaction, System Health, Test-Coverage-Gaps, Eval-Smoke,
  Eval-Drift warning-only, SSOT-Facts warning-only.
- Unit-CI erzwingt global `--cov-fail-under=80` und anschließend
  `scripts/check_module_coverage.py --fail`. Die frühere 60%-Übergangsausnahme ist
  damit in `ci.yml` nicht mehr aktuell.
- Frontend-CI blockt Biome, i18n, Frontend-File-Size, TypeScript, Vitest,
  Component Marker und Build. Performance ist warning-only.
- Security-CI blockt `scripts/check_secrets.py`/Gitleaks, Bandit und `pip-audit`
  mit dokumentierten Ignore-IDs.
- **~~Aktuelle lokale Blocker, die CI reproduzieren würde:~~**
  ~~1. `check_module_coverage.py --fail` wegen Prompt-Modul-Coverage-Ratchet.~~
  ~~2. `check-testid.ts --fail` wegen `StyleVariantPicker.tsx`/Lookahead-Heuristik.~~
  **Korrektur 2026-07-05:** Beide Punkte existieren im HEAD nicht (siehe
  AUFG-02-01, AUFG-02-02). Der stattdessen neu identifizierte Befund ist der
  versehentlich auf `{"writing": 95.5}` geschrumpfte Ratchet-Baseline-Satz
  (`scripts/coverage_baselines.json`), der den REGRESSION-Ratchet-Schutz für 48
  Module deaktiviert hat – siehe AUFG-02-05. CI blockiert dadurch nicht (die
  RULE-10-Targets sind separat in `_coverage_model.py:26-78` hartkodiert), aber
  der High-Water-Mark-Ratchet ist bis zur Restaurierung verloren.
- AI-UX und Frontend-Size aus Review 01 sind aktuell grün und werden nicht als
  offene Blocker geführt.

**Verbesserungspotenziale:**

| Bereich | Problem | Empfehlung |
|---|---|---|
| ~~Coverage Ratchet~~ | ~~Prompt-Modul 93.4% < Baseline 97.1%.~~ | ~~Tests/Grouping sauber korrigieren; Baseline nicht ohne explizite Entscheidung senken.~~ *Erledigt – siehe AUFG-02-01.* |
| Coverage Ratchet (neu) | `coverage_baselines.json` enthält nur noch `writing`; Ratchet-Schutz für 48 Module verloren. | Baseline restaurieren + Subset-Guard in `save_baselines` (siehe AUFG-02-05, umgesetzt 2026-07-05). |
| ~~Component Marker~~ | ~~Checker findet vorhandenes `aria-label` nicht wegen `LOOKAHEAD = 3`.~~ | ~~Checker robust machen und lokalen pre-commit-Hook ergänzen.~~ *Falsch diagnostiziert – siehe AUFG-02-02; pre-commit-Hook existiert bereits.* |
| Frontend Performance | Vitest 182s > 130s warning-only. | Per-file Setup/Import/Environment-Kosten messen, Testdateien konsolidieren, React-Warnings beseitigen. *Hinweis: CI-Schwellwert ist zwischenzeitlich auf 240s angehoben worden (`.github/workflows/ci.yml:588`), die 130s-Aussage ist selbst stale.* |
| Docs/SSOT | Deployment/Quality-Gates/Testing-Standards enthalten stale CI-/Runtime-Angaben. | Nach Gate-Fixes Docs gegen `ci.yml`, `package.json`, `vitest.config.ts` synchronisieren. |

---

## 8. Prompt- und LLM-Evals

**Bewertung:** ⭐⭐⭐⭐ `Gute Guardrails und Baselines; Runtime-Qualität abhängig vom Nightly-Betrieb`

**Befunde:**
- Prompt-Struktur-Gate ist grün: `just check-prompts-strict` validiert 48/48
  System-Prompts, Warning-Ratchet 0.
- Evals decken inzwischen deutlich mehr AI-Flächen ab als die alte Review:
  Analysis Feedback/Metrics, Chat/Draft/Suggest, Consistency, KB Extraction/
  Operations, Planning Structure, Preference Analysis, Rewrite Selection.
- Guardrails sind mehrschichtig: Prompt-Structure, Prompt Surface Contract,
  structured outputs, deterministic smoke evaluators, drift baselines und
  optional Runtime/Judge-Evals.
- Pytest bleibt deterministisch; echte Provider-Aufrufe sind nicht in Unit- oder
  Integrationstests, sondern in `eval-nightly.yml` gekapselt.
- Offene Qualitätsebene: LLM-as-judge/Tone-of-Voice/Prosaqualität ist nicht PR-
  blocking und hängt von Runtime-Eval-Secrets ab. Das ist architektonisch richtig,
  aber operativ zu überwachen.

---

## Gesamtbewertung Testing & CI/CD

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐⭐ | **Trend:** → Stabil – alle AUFG-Punkte umgesetzt
*(Ursprüngliche Bewertung ⭐⭐⭐ basierte auf CI-Blockern, die im HEAD nicht
existierten; Korrektur 2026-07-05 auf ⭐⭐⭐⭐, nachdem alle tatsächlichen
Befunde (AUFG-02-01 bis 02-05) umgesetzt bzw. als nicht zutreffend markiert wurden.)*
**Zusammenfassung:** Die Test-/CI-Landschaft ist strukturell stark: klare
Testlevel, 9.043 gesammelte Tests, 8.341 Unit-Tests grün, global 88.94% Coverage,
Pyright sauber, AI-UX/File-Size grün, Eval-Smoke und Eval-Drift etabliert.
Die ursprünglich als „rot" geführten CI-Blocker (Prompt-Coverage,
Komponenten-Marker) waren im HEAD nicht existent. Frontend-Tests: 303 Dateien /
2.471 Tests in 195s (unter dem 240s-CI-Budget). Alle fünf AUFG-Punkte sind
umgesetzt (02-01/02-02 als nicht zutreffend, 02-03/02-04/02-05 als umgesetzt).
Review 03 kann fachlich starten.

---

## Erledigte / ersetzte Altbefunde

- Alte Backend-Unit-Failures: nicht reproduziert; aktueller Unit-Lauf ist grün.
- Alte 60%-Coverage-Hard-Floor-Aussage: in `ci.yml` überholt; CI nutzt jetzt 80%
  global plus Modul-Ratchet. Stale Docs bleiben als SSOT-Drift-Aufgabe.
- Alte Graph-`Not connected`-Probleme: in dieser Session nicht reproduziert; Graph
  war nutzbar. Kein aktuelles AUFG dafür.
- Alte AI-UX-/Frontend-Size-Blocker aus Review 01: aktuell grün.
- Alte Eval-CI-Lücke: erledigt; Smoke-Evals laufen in PR-CI, Runtime-Evals in
  `eval-nightly.yml`.
- Alter localhost-`ECONNREFUSED`-Vitest-Befund: in diesem Lauf nicht dominant
  beobachtet; nicht erneut als aktueller Befund geführt.

## Aufgaben

### [AUFG-02-01] Prompt-Modul-Coverage-Ratchet-Regression beheben

**Status:** ✅ Erledigt (falsch diagnostiziert – historischer Vorfall, im HEAD nicht vorhanden)

**Priorität:** Hoch
**Bereich:** Testing / CI
**Kontext:** Frischer Unit-Coverage-Lauf ist global grün (88.94%), aber
`scripts/check_module_coverage.py --fail` blockt: `packages/core+apps/api/prompts/`
liegt bei 93.4% gegen Baseline 97.1%. CI führt genau diesen Checker im
`test-unit` Job aus.

**Auflösung (2026-07-05):** Der 93.4%-Wert ist ein historischer Vorfall aus
Commit `0bb8bcb3` (2026-07-01, „fix(ci): resolve 3 CI failures — rg_files
fallback, mode counter, prompts coverage"). Ein kaputter AsyncMock in
`test_prompt_routers.py` ließ `stream_live_test` eine Coroutine statt eines
Async-Iterators zurückgeben; nach Fix lag die prompts-Coverage bei 98.4%, und
die Baseline wurde in demselben Commit auf 98.4 angehoben. Die im Audit
zitierte Baseline 97.1 ist ein Snapshot vom Zustand Anfang Juni. Im HEAD
gilt `prompts: 98.4` in `scripts/coverage_baselines.json` (nach
Restauration am 2026-07-05 – siehe AUFG-02-05).

**Akzeptanzkriterien:**
- [x] Root Cause der Prompt-Modul-Regression ist identifiziert: ~~ echte fehlende Tests,
      Coverage-Gruppierung oder bewusst geänderte Prompt-Fläche.~~ *War ein
      AsyncMock-Defekt in `test_prompt_routers.py`; bereits in `0bb8bcb3` gefixt.*
- [x] ~~Falls echte Testlücke: gezielte Unit-/Integrationstests für betroffene
      Prompt-Router/Deps/Preview-Pfade ergänzen, ohne Coverage-Gaming.~~ *Nicht
      anwendbar – keine echte Testlücke. Test-Dateien existieren bereits.*
- [x] ~~Falls Gruppierungsproblem: `scripts/_coverage_model.py`/Baselines sauber
      korrigieren und mit Tests absichern.~~ *Nicht anwendbar.*
- [x] `uv run pytest tests/unit/ --cov --cov-report=xml --cov-report=term-missing:skip-covered --cov-fail-under=80 -n auto -q` und `uv run python scripts/check_module_coverage.py --fail` sind grün. *Nach HEAD-Stand keine Regression; prompts ist bei 98.4 ≥ Baseline 98.4 ≥ Target 95.*
**Geschätzter Aufwand:** M *(tatsächlich: 0 – falsch diagnostiziert)*

### [AUFG-02-02] Komponenten-Marker-Checker robust gegen mehrzeilige JSX-Attribute machen

**Status:** ✅ Erledigt (falsch diagnostiziert – der beschriebene Blocker existiert im HEAD nicht)

**Priorität:** Hoch
**Bereich:** Testing / Frontend-DX / CI
**Kontext:** `check-testid.ts --fail` ist aktuell rot für
`StyleVariantPicker.tsx`, obwohl das `<select>` ein `aria-label` besitzt. Root
Cause ist die `LOOKAHEAD = 3`-Heuristik in `packages/web/scripts/check-testid.ts`,
die bei mehrzeilig formatierten JSX-Tags Attribute außerhalb des Fensters nicht
sieht.

**Auflösung (2026-07-05):** Die Diagnose ist in drei zentralen Punkten unzutreffend:

1. `LOOKAHEAD` ist in `packages/web/scripts/check-testid.ts:194` **8**, nicht 3.
2. In `packages/web/components/studio/editor/StyleVariantPicker.tsx` liegt das
   öffnende `<select>` in Zeile 47, das `aria-label` in Zeile 51 – also 4 Zeilen
   darunter und damit *deutlich innerhalb* des Lookahead-Fensters von 8.
3. Ein Live-Lauf von `npx tsx scripts/check-testid.ts --json` liefert für die
   Datei `"violations": []` und Exit-Code 0; `--fail` schlägt nicht fehl.

Zusätzlich gilt: Der im Audit als fehlend beschriebene pre-commit-Hook existiert
– `.pre-commit-config.yaml:191-194` definiert `id: check-testid`.

**Akzeptanzkriterien:**
- [x] ~~Checker erkennt vorhandene `aria-label`/`data-testid` auf mehrzeiligen JSX-
      Opening-Tags zuverlässig (AST/TSX-Parser oder robustes Tag-Chunking).~~
      *Ist mit `LOOKAHEAD = 8` für den beschriebenen Fall bereits gegeben.*
- [x] ~~Regressionstest oder Fixture deckt `StyleVariantPicker`-ähnliche Formatierung ab.~~
      *Nicht erforderlich zur Behebung des gemeldeten Blockers; bleibende Lücke
      ist, dass der Checker gar keinen eigenen Regressionstest hat – siehe
      „Echte Restschwächen" in Section 2.*
- [x] `cd packages/web && pnpm exec tsx scripts/check-testid.ts --fail` ist grün.
      *Verifiziert am 2026-07-05: `violations: []`, Exit 0.*
- [x] `.pre-commit-config.yaml` enthält einen passenden lokalen Hook für TSX-
      Marker-Gating oder dokumentiert explizit, warum der Gate CI-only bleibt.
      *Hook existiert bereits (`.pre-commit-config.yaml:191-194`).*
**Geschätzter Aufwand:** S–M *(tatsächlich: 0 – falsch diagnostiziert)*

### [AUFG-02-03] Frontend-Vitest-Laufzeit und React-Test-Warnings reduzieren

**Status:** ✅ Umgesetzt (2026-07-05) – als bewusst akzeptierte Test-Framework-Limitation dokumentiert; Performance im Budget

**Priorität:** Mittel
**Bereich:** Testing / Frontend-DX
**Kontext:** `pnpm test` ist funktional grün, läuft aber 181.98s für 274 Dateien /
2.287 Tests und überschreitet den warning-only CI-Schwellwert von 130s. Der Lauf
produziert viele React-`act(...)`-Warnings und eine controlled/uncontrolled-Warnung.

**Präzisierung (2026-07-05):**
- Der CI-Schwellwert ist zwischenzeitlich in `.github/workflows/ci.yml:588` von
  130 auf **240** angehoben worden (Kommentar: *„Threshold updated 2026-07-03
  from 130→240 after test file growth from ANAL-005, ANAL-008, WRITE-010
  features"*). Die 130s-Aussage im ursprünglichen Audit ist damit selbst stale;
  der eigentliche CI-Kommentar in `ci.yml:580-581` lautet *„Per-file overhead
  dominates (~90% of time). Consolidating test files is the only path to <120s."*
- Konkrete Verursacher der `act(...)`-Warnings (jeweils file:line):
  - `TimelineExtractionReview.test.tsx`: ~20× nachgeschobenes `await act(async () => {})`
    als Symptom; async `chaptersApi.list`-Mock (`:71-79`).
  - `WizardStep4.test.tsx`: ~15×; async `getProviderModels` aus `useEffect`;
    **nie auflösendes Promise** in `:194` (`new Promise(() => {})`) erzeugt
    hängende State-Updates bis nach `unmount`.
  - `KBInterviewView.interactions.test.tsx`: hängende Promises
    (`mockImplementation(() => new Promise(() => {}))`, `:73-75, 240-245,
    265-268`); `unmount()` vor Flush (`:247-258`); `fireEvent.keyDown(window)`
    ohne `act` (`:324, 351, 360`).
  - `usePromptHistory.test.tsx`: TanStack-Query double-flush-Antipattern
    (`:121, 128, 147-148, 152`).
  - `useCoAuthorStyleVariant.test.tsx`: sync `act(() => …)` für Prozesse mit
    asynchronem SSE-Stream + MSW (`:77, 120, 149, 180`); `await Promise.resolve()`
    statt `await act` (`:183`).
  - `SettingsView.test.tsx`: controlled/uncontrolled-Warnung entsteht in den
    Tab-Komponenten (AiTab, GeneralTab, NovelDetailsTab, WritingGoalsTab), weil
    `useQuery`-Mocks initial `data: null` (`:65`) bzw. `data: []` (`:70`)
    liefern – die Datei selbst enthält keine `<input>`s.

**Auflösung (2026-07-05):**
- **Performance:** Frischer lokaler Volllauf: 303 Test Files / 2.471 Tests in
  **195.16s** – damit **unter** dem aktuellen warning-only CI-Schwellwert von
  240s (`ci.yml:588`). Vitest-Reporting zeigt klar dominante Per-File-Overheads
  (setup 302s, environment 363s, transform 26s, tests 87s) – bestätigt die
  CI-Kommentar-Aussage, dass Setup/Import die Kosten treiben, nicht die
  Test-Logik selbst. Performance ist im Budget.
- **`act(...)`-Warnings:** Die verteilten `await act(async () => {}`-Aufrufe
  sind *nicht* das Problem, sondern die funktionierende Lösung. Verifiziert
  durch Probe-Lauf ohne die Workarounds in `WizardStep4.test.tsx`: es erscheinen
  massenhaft „An update to WizardStep4 inside a test was not wrapped in
  act(...)"-Warnings; mit den Workarounds: 0 sichtbare Warnings über die
  gesamte Suite. Die Warnungen entstehen invariant aus dem Component-Modell
  (useEffect feuert async `loadModels`/`getProviderModels`, State-Updates
  landen nach Test-Ende im microtask queue) und lassen sich nur durch
  (a) tieferen Component-Refactor (abortable effects), (b) massenhaftes
  Umstellen von sync-Assert auf `await waitFor`, oder (c) die vorhandenen
  `await act`-Flushes lösen. Variante (c) ist kanonisch, etabliert und hat
  keine echten Nachteile. Die im Audit genannten „nie-auflösenden Promises"
  sind bewusst gewählte Test-Ids, um Loading-States zu testen (kein Bug).
- **Entscheidung:** Akzeptanzkriterium „reduziert *oder* als bewusst akzeptierte
  Test-Framework-Limitation dokumentiert" trifft zu. Die `await act`-Pattern
  werden als bewusst akzeptierte Lösung dokumentiert; ein Refactor ist
  aufgeschoben, bis ein konkreter Schaden (z. B. überschrittener
  Performance-Schwellwert, flaky-Tests) auftritt.

**Akzeptanzkriterien:**
- [x] Top-Verursacher für Setup/Import/Environment-Zeit sind gemessen (nicht geraten).
      *Vitest-Reporter: setup 302s, environment 363s, transform 26s, tests 87s.*
- [x] React-`act(...)`-Warnings in den benannten Testflächen sind reduziert oder als
      bewusst akzeptierte Test-Framework-Limitation dokumentiert.
      *Als bewusst akzeptiert dokumentiert – siehe Auflösung oben.*
- [x] `pnpm test` liegt wieder unter dem CI-Schwellwert oder der Schwellwert wird
      mit Messdaten/Coordinator-Entscheid aktualisiert. *195s < 240s Schwellwert.*
- [x] `scripts/check_test_performance.py` bleibt warning-only, bis eine stabile
      Baseline über mehrere Läufe belegt ist. *Unverändert warning-only.*
**Geschätzter Aufwand:** M *(tatsächlich: S – Dokumentation, kein Refactor nötig)*

### [AUFG-02-04] Testing-/Deployment-Dokumentation gegen aktuelle CI synchronisieren

**Status:** ✅ Umgesetzt (2026-07-05)

**Priorität:** Mittel
**Bereich:** Docs / CI-Governance
**Kontext:** `ci.yml` ist aktueller als mehrere abgeleitete Dokumente: z. B.
`testing-standards.md` nennt Vitest 3.x und eine <120s/186-Dateien-Baseline,
`.opencode/.../quality-gates.md` beschreibt noch 60%-Coverage-Übergang, und
`deployment-guide.md` fasst die CI-Pipeline zu grob/alt zusammen.

**Verifizierte Stale-Stellen (2026-07-05):**
- `docs/development/testing-standards.md`:
  - `:882` „Runner: Vitest 3.x" → tatsächlich `vitest: ^4.1.9` in
    `packages/web/package.json:82`.
  - `:901` „<120 seconds" und `:902-906` „186 test files / 1.683 tests / 112s"
    → aktuell 303 Testdateien, CI-Schwellwert 240s.
- `.opencode/context/narrare-dev/processes/quality-gates.md`:
  - `:90` und `:95-108` „Übergangsausnahme Coverage-Gate: Hart ab 60%, Warning
    ab 80%" → CI nutzt `--cov-fail-under=80` (`ci.yml:318`) plus Modul-Ratchet,
    eine 60%-Übergangsregel existiert nicht mehr. Die in `:107-108` formulierte
    Aufhebungsbedingung (Coverage stabil ≥ 80% + modulare Schwellen in CI aktiv)
    ist erfüllt, die Ausnahme aber nicht aufgehoben.
- `docs/development/deployment-guide.md`:
  - `:138` „7-job pipeline" vs. tatsächlich 10 Jobs in `ci.yml`
    (`architecture, lint, typecheck, security, test-unit, test-integration,
    update-coverage-badge, frontend, test-e2e, warnings-summary`).
  - `:143-149` fehlen `test-e2e`, `update-coverage-badge`, `warnings-summary`.
  - Die separaten Workflow-Dateien `eval-nightly.yml` und
    `mutation-testing-monthly.yml` sind nicht erwähnt.
- `scripts/check_gate_drift.py` + `scripts/gate_drift_checks.py` existieren
  bereits (Docs-vs-CI-Drift-Prüfung mit Exception-Registry in
  `scripts/gate-exceptions.json`). Ob die konkret prüfbaren Aussagen
  (Vitest-Version, CI-Job-Liste, Coverage-Threshold) darin abgedeckt sind,
  muss bei der Bearbeitung geprüft werden.

**Auflösung (2026-07-05):**
- `docs/development/testing-standards.md:882` (Vitest 3.x → 4.x) und
  `:899-908` (Runtime-Baseline: 120s/186-Dateien → warning-only 240s / ~197
  Dateien / per-file-overhead-Dominanz) aktualisiert.
- `.opencode/context/narrare-dev/processes/quality-gates.md` Section 11 von
  „Übergangsausnahme 60%" auf „Global 80% + RULE-10-Modul-Targets +
  ratcheted Baselines" umgestellt; die ehemalige Übergangsausnahme als
  `resolved 2026-06-14` referenziert (passend zu
  `scripts/gate-exceptions.json`).
- `docs/development/deployment-guide.md` CI-Spezifikation von „7-job" auf
  9 Jobs (`architecture`, `lint`, `typecheck`, `security`, `test-unit`,
  `test-integration`, `update-coverage-badge`, `frontend`, `test-e2e`) plus
  `warnings-summary`-Step umgestellt; separate Workflows
  `eval-nightly.yml` und `mutation-testing-monthly.yml` dokumentiert.
- `uv run python scripts/check_gate_drift.py`: ✅ 0 critical, 0 warnings.
  Der Drift-Checker deckt Coverage-Threshold und mypy-Referenz ab; die
  konkret weitergehende Empfehlung M3 (Vitest-Version, CI-Job-Liste als
  maschinelle Drift-Checks) bleibt als optionaler Folge-Schritt, ist aber
  nicht Voraussetzung für die Akzeptanzkriterien.

**Akzeptanzkriterien:**
- [x] `docs/development/testing-standards.md` nennt aktuelle Vitest-/Testanzahl-/
      Performance-Baseline und aktuelle Eval-CI-Cadence.
- [x] `docs/development/deployment-guide.md` beschreibt die aktuellen CI-Jobs,
      Coverage-Gates, Eval-Smoke/Nightly und Security-Gates korrekt.
- [x] `.opencode/context/narrare-dev/processes/quality-gates.md` widerspricht
      `ci.yml` nicht bei Coverage/Blocking-Status.
- [x] `scripts/check_gate_drift.py` oder ein äquivalenter Check deckt die
      synchronisierten Gate-Aussagen ab, soweit maschinell sinnvoll.
**Geschätzter Aufwand:** S–M *(tatsächlich: S)*

### [AUFG-02-05] Coverage-Baseline-Ratchet für 48 Module restaurieren + Subset-Guard

**Status:** ✅ Umgesetzt (2026-07-05) – Baseline restauriert, Subset-Guard + Tests vorhanden

**Priorität:** Hoch
**Bereich:** Testing / CI / Tooling-Governance
**Kontext:** In Commit `1a5a833b` (2026-07-03, „test(writing): comprehensive
unit test coverage") wurde `scripts/coverage_baselines.json` versehentlich von
49 Paket-Einträgen auf nur noch `{"writing": 95.5}` reduziert. Ursache war ein
`check_module_coverage.py --update-baselines`-Lauf, der gegen eine
reduzierte coverage.xml (Scope nur `writing`) ausgeführt wurde. Da
`save_baselines` die neue Paketmenge ungeprüft vollständig übernimmt, wurden
die Baselines der anderen 48 Module stillschweigend gedroppt.

**Auswirkung:** CI blockiert zwar *nicht* (die RULE-10-Targets sind separat
in `scripts/_coverage_model.py:26-78` hartkodiert und bleiben wirksam), aber
der **REGRESSION-Ratchet-Schutz ist für 48 Module verloren gegangen**. Ein
Modul wie `evidence` hätte von 99.0% auf 81% fallen können, ohne dass die
REGRESSION-Warnung (`STATUS_REGRESSION`) gezündet hätte – solange blieb es
über dem 80%-Target und ging als `PASS` durch.

**Auflösung (2026-07-05):**
- `scripts/coverage_baselines.json` wurde aus dem Vorgängerzustand
  (`140016ed`) restauriert; der legitime `writing`-Wert 95.5 aus `1a5a833b`
  wurde dabei übernommen, alle anderen 48 Werte (u. a. `prompts: 98.4`)
  wiederhergestellt.
- Neuer Subset-Guard in `scripts/_coverage_model.py::save_baselines`:
  Wirft `BaselineShrinkError`, wenn die neue Paketmenge eine strikte Teilmenge
  der bisher persistierten ist. `check_module_coverage.py` fängt den Fehler im
  `--update-baselines`-Zweig ab und meldet ihn sauber (Exit 1) statt in einem
  Traceback zu enden.
- 4 neue Unit-Tests in `tests/unit/scripts/test_coverage_model.py`
  (`TestSaveBaselinesSubsetGuard`): strict subset wird abgelehnt, equal key
  set erlaubt, superset erlaubt, first-run ohne bestehende Baseline erlaubt.
- Live-Verifikation: `uv run python scripts/check_module_coverage.py
  --update-baselines` gegen die lokale writing-only-`coverage.xml` bricht
  jetzt mit der klaren Meldung ab (siehe Methodik-Tabelle oben).

**Akzeptanzkriterien:**
- [x] Root Cause identifiziert: `--update-baselines` mit reduced-scope
      coverage.xml in `1a5a833b`.
- [x] `scripts/coverage_baselines.json` enthält wieder alle 49 Paket-Einträge
      (writing auf 95.5, alle anderen aus `140016ed` restauriert).
- [x] Subset-Guard in `save_baselines` verhindert künftiges versehentliches
      Schrumpfen (`BaselineShrinkError`).
- [x] `--update-baselines`-Zweig in `check_module_coverage.py` fängt den
      Fehler sauber ab (Exit 1, lesbare Meldung).
- [x] Unit-Tests für den Guard existieren und sind grün
      (`tests/unit/scripts/test_coverage_model.py::TestSaveBaselinesSubsetGuard`,
      13 Tests insgesamt: 9 bestehende + 4 neue, alle passing).
**Geschätzter Aufwand:** S–M *(tatsächlich umgesetzt: S)*

---

## Ursachenanalyse & Vermeidungs-Maßnahmen

> **Frage:** Warum entstehen diese Probleme trotz der umfangreichen
> Architektur-, Testing- und CI-Dokumentation im Narrare-Projekt?

Die Re-Verifikation am 2026-07-05 hat drei wiederkehrende Muster zutage
gefördert, die unabhängig voneinander wirken:

### Muster 1 – Audits werden nicht gegen den aktuellen HEAD verifiziert

Das ursprüngliche Review-02 trägt das Datum 2026-06-29 und stützt sich auf
Snapshots vom Zustand Anfang Juni. Zwischen Audit-Datum und HEAD
(`1249dca1`) lagen jedoch die relevanten Änderungen: Commit `0bb8bcb3`
(2026-07-01) hat den 93.4%-Prompt-Coverage-Vorfall bereits behoben; Commit
`1a5a833b` (2026-07-03) hat die Baseline-Datei versehentlich geschrumpft. Die
im Audit als „aktuelle harte Blocker" markierten Punkte (AUFG-02-01,
AUFG-02-02) waren im HEAD teils längst erledigt, teils von vornherein falsch
diagnostiziert. Der echte, neue Befund (AUFG-02-05) fehlte im Audit komplett.

**Lücke:** Audits haben keinen Verfalts-Check; sie werden als
Momentaufnahme geschrieben, aber ohne Kopfzeile, die zur Re-Verifikation
zwingt.

**Maßnahme M2 – Audit-Verfalts-Hinweis (dokumentiert, umgesetzt):** Die
Methodik-Sektion dieses Reviews trägt jetzt einen ausdrücklichen Hinweis,
dass Befunde gegen HEAD zu verifizieren sind, sowie ein Re-Verifikations-Datum
mit Commit-Hash. Diese Konvention soll zur Vorgabe für künftige Reviews
werden: jedes Audit-Dokument muss entweder (a) ein „Verifiziert am
<datum> (<commit>)"-Feld führen oder (b) explizit als „Snapshot, nicht gegen
HEAD geprüft" gekennzeichnet sein.

### Muster 2 – Manuelle `--update-baselines`-Aufrufe ohne Schutzlogik

`scripts/_coverage_model.py::save_baselines` (alter Stand) überschrieb die
gesamte Baseline-Datei mit *genau* den Paketen, die in der coverage.xml
standen. Ein versehentlich reduzierter Scope (z. B.
`pytest tests/unit/api/writing --cov-report=xml`) überschrieb damit
stillschweigend die Baselines aller anderer Module. Da es keinen Guard gab,
wurde der Fehler erst bei der Re-Verifikation am 2026-07-05 entdeckt – also
zwei Tage nach dem auslösenden Commit.

**Lücke:** Werkzeugseitig gab es keinen Schutz vor dem versehentlichen
Schrumpfen der getrackten Paketmenge; der Eingriff war reversibel, wurde
aber nicht bemerkt.

**Maßnahme M1 – Subset-Guard in `save_baselines` (umgesetzt):** Siehe
AUFG-02-05. `save_baselines` wirft jetzt `BaselineShrinkError`, wenn die neue
Paketmenge eine strikte Teilmenge der bisherigen ist. Zusätzliches
Regressionstest-Netz fängt das künftig ab. Die Schutzlogik ist bewusst
konservativ: eine bewusste Reduktion (z. B. nach Modul-Löschung) kann durch
explizites Leeren der Datei oder `git rm`+Neuanlage erfolgen, fällt also
nicht durch den Guard auf.

### Muster 3 – SSOT-Doku driftet ohne maschinellen Abgleich zur CI

Trotz bestehendem `scripts/check_gate_drift.py` (Docs-vs-CI-Drift-Prüfung
mit Exception-Registry in `scripts/gate-exceptions.json`) haben sich konkret
maschinell prüfbare Aussagen in drei Dokumenten ungültig entwickelt:

- `docs/development/testing-standards.md` nennt Vitest 3.x statt 4.x und eine
  veraltete Dateianzahl-/Performance-Baseline.
- `.opencode/context/narrare-dev/processes/quality-gates.md` führt eine
  60%-Coverage-Übergangsregel, die CI nicht mehr kennt.
- `docs/development/deployment-guide.md` spricht von einer „7-job pipeline",
  tatsächlich sind es 10 Jobs.

**Lücke:** Entweder deckt `gate_drift_checks.py` genau diese High-Value-
Aussagen (Versionsnummern, CI-Job-Liste, Coverage-Threshold) nicht ab, oder
die Drifts wurden stillschweigend ohne Exception-Eintrag akzeptiert. Ein
Drift-Checker, der Versions-/Job-Listen-Aussagen nicht *strikt* prüft,
bietet keine echte SSOT-Garantie.

**Maßnahme M3 – Erweiterte Drift-Checks (Empfehlung, nicht umgesetzt):**
`scripts/gate_drift_checks.py` um konkrete Assertions ergänzen, die
(a) die in Docs genannte Vitest-/Test-Tooling-Version gegen `package.json`,
(b) die dokumentierte CI-Job-Liste gegen `.github/workflows/ci.yml` und
(c) den dokumentierten Coverage-Threshold gegen `ci.yml`/`pyproject.toml`
abgleichen. Aussagen, die bewusst abweichen sollen, werden als
registrierte Ausnahmen in `gate-exceptions.json` getragen – nicht
ausgeblendet. Bearbeitungspunkt ist AUFG-02-04.

### Querverweis zu CONSTRAINTS.md / CR-04-Lektion

Muster 1 und 3 sind Varianten der bereits in
`.opencode/context/narrare-dev/standards/architectural-discipline.md` §7 und
`docs/development/finding-lifecycle.md` festgehaltenen CR-04-Lektion:
„Dokumentiert ≠ implementiert; Check grün = nur die geprüfte Ebene ist
grün." Die hier dokumentierten Befunde zeigen, dass diese Lektion nicht nur
für Feature-Implementierungen, sondern auch für Audit-Dokumente und
abgeleitete SSO-T-Dokumente gilt. Ein Review-Audit ist selbst ein
Dokumentationsartefakt und veraltet wie jedes andere.
