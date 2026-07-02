# Review 02 – Testing & CI/CD

> Aktualisiert am 2026-06-29 durch NarrarePlatformSpecialist. Grundlage:
> `_audit/results/technical-review/review-00-kontext.md`,
> `_audit/results/technical-review/review-01-architektur.md`,
> `docs/_shared/CONSTRAINTS.md`, `docs/development/testing-standards.md`,
> `docs/development/deployment-guide.md`, aktuelle CI-/Test-Konfiguration und
> frische lokale Verifikation. Keine Commits, kein `--no-verify`.

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
  Frontend-Size aus Review 01 sind aktuell grün. Neue harte Blocker liegen jetzt
  in (a) einer Prompt-Modul-Coverage-Ratchet-Regression und (b) einem
  Komponenten-Marker-Checker-False-Positive, das trotzdem CI-blocking ist.
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
- **Aktueller Blocker:** `scripts/check_module_coverage.py --fail` meldet eine
  Ratchet-Regression: `packages/core+apps/api/prompts/` liegt bei 93.4% gegen
  Baseline 97.1%. Der globale Wert ist also grün, aber der CI-Subgate ist rot.
- Auffällige Low-Coverage-Dateien innerhalb der Prompt-Fläche aus dem frischen
  Coverage-Termreport sind u. a. `apps/api/narrare/prompts/deps.py` (14%),
  `apps/api/narrare/prompts/router.py` (49%),
  `router_prompt_history.py` (70%), `router_prompt_ux.py` (62%) und
  `packages/core/narrare_core/prompts/preview.py` (89%). Einige `contracts.py`-
  Dateien werden im Coverage-Report aufgeführt, aber `pyproject.toml` omittet
  `contracts.py` allgemein; die Modulregression muss am realen Coverage-XML/
  Gruppierungsmodell geprüft werden, nicht durch Baseline-Absenkung kaschiert.
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

**Bewertung:** ⭐⭐ `CI-Gate existiert, ist aktuell aber rot durch Checker-Heuristik`

**Befunde:**
- Marker-Gate existiert: `packages/web/scripts/check-testid.ts`, npm-Skripte
  `check:testid`/`check:testid:strict`, und `.github/workflows/ci.yml` führt im
  Frontend-Job `cd packages/web && npx tsx scripts/check-testid.ts --fail` aus.
- Aktueller lokaler Lauf ist **rot**: 335 Dateien geprüft, 1 Datei mit fehlendem
  Marker, 1 uncovered interactive element:
  `packages/web/components/studio/editor/StyleVariantPicker.tsx`.
- Die Datei hat jedoch tatsächlich `aria-label={t("styleVariants.regenerateAs")}`
  auf dem `<select>` (Zeile 51). Root Cause ist nicht ein fehlender Marker im
  Produktcode, sondern die Checker-Heuristik: `check-testid.ts` sammelt nur
  `LOOKAHEAD = 3` Folgezeilen ab der öffnenden Tag-Zeile. Bei `StyleVariantPicker`
  liegt `aria-label` außerhalb dieses Lookahead-Fensters.
- Warum AI/Review das ohne Tool nicht erkennt: `data-testid`/`aria-label` ist ein
  UI-/E2E-Stabilitätsvertrag, kein TypeScript-Typfehler. Zudem ist die aktuelle
  Verletzung ein Formatter-/Heuristik-Problem, nicht ein semantisch fehlendes
  Attribut.
- `.pre-commit-config.yaml` enthält derzeit keinen `check-testid`-Hook. Damit ist
  die Markerprüfung lokal nicht so früh blocking wie in CI.

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

**Bewertung:** ⭐⭐⭐ `Sehr breit, aber aktuell zwei Blocking-Pfade rot`

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
- **Aktuelle lokale Blocker, die CI reproduzieren würde:**
  1. `check_module_coverage.py --fail` wegen Prompt-Modul-Coverage-Ratchet.
  2. `check-testid.ts --fail` wegen `StyleVariantPicker.tsx`/Lookahead-Heuristik.
- AI-UX und Frontend-Size aus Review 01 sind aktuell grün und werden nicht als
  offene Blocker geführt.

**Verbesserungspotenziale:**

| Bereich | Problem | Empfehlung |
|---|---|---|
| Coverage Ratchet | Prompt-Modul 93.4% < Baseline 97.1%. | Tests/Grouping sauber korrigieren; Baseline nicht ohne explizite Entscheidung senken. |
| Component Marker | Checker findet vorhandenes `aria-label` nicht wegen `LOOKAHEAD = 3`. | Checker robust machen und lokalen pre-commit-Hook ergänzen. |
| Frontend Performance | Vitest 182s > 130s warning-only. | Per-file Setup/Import/Environment-Kosten messen, Testdateien konsolidieren, React-Warnings beseitigen. |
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

**Bewertung:** ⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐⭐ | **Trend:** ↘️ Schlechter, wegen aktueller CI-Blocker
**Zusammenfassung:** Die Test-/CI-Landschaft ist strukturell stark: klare
Testlevel, 9.043 gesammelte Tests, 8.341 Unit-Tests grün, global 88.94% Coverage,
Pyright sauber, AI-UX/File-Size grün, Eval-Smoke und Eval-Drift etabliert. Trotzdem
ist der aktuelle Merge-Zustand nicht grün: der Modul-Coverage-Ratchet für Prompts
regressiert und das Komponenten-Marker-Gate ist durch eine Checker-Heuristik rot.
Zusätzlich ist die Frontend-Testlaufzeit mit 181.98s deutlich über dem warning-only
Budget und erzeugt viele React-Test-Warnings. Review 03 kann fachlich starten, muss
diese CI-Blocker aber als offene Qualitätsrisiken mitnehmen.

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
**Priorität:** Hoch
**Bereich:** Testing / CI
**Kontext:** Frischer Unit-Coverage-Lauf ist global grün (88.94%), aber
`scripts/check_module_coverage.py --fail` blockt: `packages/core+apps/api/prompts/`
liegt bei 93.4% gegen Baseline 97.1%. CI führt genau diesen Checker im
`test-unit` Job aus.
**Akzeptanzkriterien:**
- [ ] Root Cause der Prompt-Modul-Regression ist identifiziert: echte fehlende Tests,
      Coverage-Gruppierung oder bewusst geänderte Prompt-Fläche.
- [ ] Falls echte Testlücke: gezielte Unit-/Integrationstests für betroffene
      Prompt-Router/Deps/Preview-Pfade ergänzen, ohne Coverage-Gaming.
- [ ] Falls Gruppierungsproblem: `scripts/_coverage_model.py`/Baselines sauber
      korrigieren und mit Tests absichern.
- [ ] `uv run pytest tests/unit/ --cov --cov-report=xml --cov-report=term-missing:skip-covered --cov-fail-under=80 -n auto -q` und `uv run python scripts/check_module_coverage.py --fail` sind grün.
**Geschätzter Aufwand:** M

### [AUFG-02-02] Komponenten-Marker-Checker robust gegen mehrzeilige JSX-Attribute machen
**Priorität:** Hoch
**Bereich:** Testing / Frontend-DX / CI
**Kontext:** `check-testid.ts --fail` ist aktuell rot für
`StyleVariantPicker.tsx`, obwohl das `<select>` ein `aria-label` besitzt. Root
Cause ist die `LOOKAHEAD = 3`-Heuristik in `packages/web/scripts/check-testid.ts`,
die bei mehrzeilig formatierten JSX-Tags Attribute außerhalb des Fensters nicht
sieht.
**Akzeptanzkriterien:**
- [ ] Checker erkennt vorhandene `aria-label`/`data-testid` auf mehrzeiligen JSX-
      Opening-Tags zuverlässig (AST/TSX-Parser oder robustes Tag-Chunking).
- [ ] Regressionstest oder Fixture deckt `StyleVariantPicker`-ähnliche Formatierung ab.
- [ ] `cd packages/web && pnpm exec tsx scripts/check-testid.ts --fail` ist grün.
- [ ] `.pre-commit-config.yaml` enthält einen passenden lokalen Hook für TSX-
      Marker-Gating oder dokumentiert explizit, warum der Gate CI-only bleibt.
**Geschätzter Aufwand:** S–M

### [AUFG-02-03] Frontend-Vitest-Laufzeit und React-Test-Warnings reduzieren
**Priorität:** Mittel
**Bereich:** Testing / Frontend-DX
**Kontext:** `pnpm test` ist funktional grün, läuft aber 181.98s für 274 Dateien /
2.287 Tests und überschreitet den warning-only CI-Schwellwert von 130s. Der Lauf
produziert viele React-`act(...)`-Warnings und eine controlled/uncontrolled-Warnung.
**Akzeptanzkriterien:**
- [ ] Top-Verursacher für Setup/Import/Environment-Zeit sind gemessen (nicht geraten).
- [ ] React-`act(...)`-Warnings in den benannten Testflächen sind reduziert oder als
      bewusst akzeptierte Test-Framework-Limitation dokumentiert.
- [ ] `pnpm test` liegt wieder unter dem CI-Schwellwert oder der Schwellwert wird
      mit Messdaten/Coordinator-Entscheid aktualisiert.
- [ ] `scripts/check_test_performance.py` bleibt warning-only, bis eine stabile
      Baseline über mehrere Läufe belegt ist.
**Geschätzter Aufwand:** M

### [AUFG-02-04] Testing-/Deployment-Dokumentation gegen aktuelle CI synchronisieren
**Priorität:** Mittel
**Bereich:** Docs / CI-Governance
**Kontext:** `ci.yml` ist aktueller als mehrere abgeleitete Dokumente: z. B.
`testing-standards.md` nennt Vitest 3.x und eine <120s/186-Dateien-Baseline,
`.opencode/.../quality-gates.md` beschreibt noch 60%-Coverage-Übergang, und
`deployment-guide.md` fasst die CI-Pipeline zu grob/alt zusammen.
**Akzeptanzkriterien:**
- [ ] `docs/development/testing-standards.md` nennt aktuelle Vitest-/Testanzahl-/
      Performance-Baseline und aktuelle Eval-CI-Cadence.
- [ ] `docs/development/deployment-guide.md` beschreibt die aktuellen CI-Jobs,
      Coverage-Gates, Eval-Smoke/Nightly und Security-Gates korrekt.
- [ ] `.opencode/context/narrare-dev/processes/quality-gates.md` widerspricht
      `ci.yml` nicht bei Coverage/Blocking-Status.
- [ ] `scripts/check_gate_drift.py` oder ein äquivalenter Check deckt die
      synchronisierten Gate-Aussagen ab, soweit maschinell sinnvoll.
**Geschätzter Aufwand:** S–M
