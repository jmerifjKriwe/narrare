# E2E Full Functional Suite — Design Spec

Date: 2026-10-11 · Status: DRAFT (pending PO review)
Input: [2026-10-11 E2E UI audit](../reports/2026-10-11-e2e-ui-audit.md) · PO decisions 2026-10-11

## 1. Goal & non-goals

**Goal.** A complete, manually-triggered functional E2E suite that drives the real
UI (browser) against the real full stack (API + DB + frontend) with **all AI
functions deterministically mocked** — independent from unit and integration
tests, and not run automatically (no per-PR CI; the existing `main`/nightly
`test-e2e` CI job continues to run whatever the suite contains at that time).

**Non-goals.**
- No new pure-FE TS specs (`packages/web/tests/e2e/frontend` stays untouched).
- No CI expansion (no new jobs; runtime growth of the existing nightly job is
  accepted up to a budget, see §7 — flagged as PO decision point).
- No visual-regression testing (existing VRT suite stays as-is).
- Bug fixing itself is specced/planned separately (fix slices consume audit
  findings; this spec covers the suite, with the interleaving rule in §8).

## 2. Basis (PO decision 2026-10-11)

Extend the existing **pytest-playwright suite** (`tests/e2e/`) and its canonical
runner `just e2e` → `scripts/run_e2e.sh` (CI-faithful: `narrare_test` DB on
:5433, migrate + seed, `ENVIRONMENT=test`, CSRF off, cleanup trap). Single entry
point; subsets via `pytest -k`/`-m`; no second runner.

## 3. AI mocking architecture (audit finding E04 drives this)

Two complementary layers, both already precedented in the repo:

1. **Factory layer — `NARRARE_E2E_TEST=1` → `pydantic_ai.TestModel`** (unchanged;
   proves the full prompt→agent→stream pipeline; sufficient for tolerance-loose
   surfaces: chat, WS turns, ghost text, dialogue coach, name generator).
2. **Browser layer — scripted per-capability responses via `page.route()`**
   (existing `tests/e2e/mocks/llm_responses.py` pattern), extended into a
   **catalog**: one deterministic valid response per AI surface that has
   validator-strict outputs (generation SSE chunks, coreference, character
   voices, beta reader, consistency, extraction, wiki, improve, scene
   draft/refine). Catalog entries are versioned fixtures; a conftest helper
   `mock_llm(page, capability, fixture=…)` installs them. Where an SSE endpoint
   is hit, the mock emits a realistic event sequence incl. an error-fixture
   variant for failure-path tests.

The suite never makes real LLM calls (asserted by the TestModel banner + zero
outbound network to provider hosts).

## 4. Suite structure

```
tests/e2e/
├── conftest.py              # existing; grows the shared fixture layer
├── helpers/                 # NEW: consolidated helper package
│   ├── audit_user.py        # register-through-UI (first-run) + login session
│   ├── novel_factory.py     # wizard completion (blank/demo/import starter), volume/chapter setup
│   ├── llm_mocks.py         # mock_llm(page, capability) + catalog loading
│   └── probes.py            # a11y dump, console/network capture assertions
├── mocks/llm_responses.py   # existing, grows into the catalog (fixtures live beside it)
└── test_<area>.py           # one spec per feature area (see §5)
```

Existing 12 spec files remain; new specs follow the same style (`-m e2e`,
`--timeout=300` handled by the runner).

## 5. Coverage matrix (spec ← audit findings)

Priority = broken/dormant surfaces first (they need regression pins the most);
working surfaces get happy-path pins. "Gate" = fix slice that must land before
the spec is meaningfully writable (spec may still be written first in
red/skip-marked form where useful).

| Spec (new) | Features | Audit gates (findings) | Scope |
|---|---|---|---|
| test_ai_writing.py | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | generate modes happy+empty-422+stream-death paths; extend/co-author/rewrite/unblock happy + apply/reject; ghost text accept/dismiss; WS session full flow |
| test_kb_management.py | KB-001/008/009 | B04 B06 M01 N14 N15 N16 | CRUD incl. detail view, graph render/interactions, merge flow, suggestions surface, extract single incl. storm-regression pin |
| test_kb_ai.py | KB-002/003/004/005/007 + corpus | B03 B05 B06 | session interview, improve, consistency check, bulk + corpus estimate/status/results happy + cancel |
| test_wiki.py | WIKI-001 | M11 | first-generation path, refresh, staleness lifecycle, chapter summary panel |
| test_analysis.py | ANAL-001..005/007/008/009 | B07 E03 N11 N12 N13 | per-analyzer happy path via mocks; beta-reader min-words boundary; readability honest-skip pin; voice family panels |
| test_import_export.py | SETUP-003, export | N18 | preview/adjustments/commit (already strong — pin it), export formats incl. download |
| test_stats_budget.py | STATS-001/002 | M02 | analytics render + goals + cost dashboard + budget modes incl. banner trigger via mock |
| test_volumes_scenes.py | WRITE-011, PLAN-001 | M09 M10 | volume CRUD/assign/reorder (+prefill pin), scenes CRUD + storyboard stages |
| test_series_scratchpad.py | SERIES-001..004, NOTES-001 | N02 | series lifecycle incl. join/canon, scratchpad CRUD |
| test_settings_auth.py | SETUP-004, auth, i18n | M03 M04 M05 M07 M08 N04 N05 N06 | provider config UI, token limits, error-mapping locale pins, language switch, auth roundtrip + refresh race |
| test_onboarding.py | SETUP-001/002, ONBOARD-001 | N17 | wizard variants A/B, demo load incl. prefill, tour steps |

Regression-first rule: every **BLOCKER/MAJOR** finding from the audit gets a
pinning test in the spec that covers its surface — written against the FIXED
behavior (red before the fix slice, green after), or as a
`xfail(strict=True)` documentation pin when the fix is deferred.

## 6. Interleaving with fix slices (PO policy: document → fix separately)

- Fix slices are routed per layer (Backend for B03/B05/B06/B07/M02/M03/M04,
  Frontend for B01/B02/B04/B08/B09/M01/M05–M07/M09–M11 + N-items) through the
  normal spec→plan pipeline; the audit report is their input list.
- The suite plan orders tasks so that **gated specs land right after their
  gate fix**, keeping every task green on completion (no long-lived skips).
- Ordering proposal (PO may reshuffle): Fix-wave 1 (B01–B09 unblocks the AI
  surface) → suite tasks per §5 → fix-wave 2 (M-items) interleaved.

## 7. Runtime & CI budget

- Full-suite local target: **≤ 25 min** on this machine (`E2E_FRONTEND_MODE=dev`;
  CI-faithful `build` runs may exceed — acceptable for nightly).
- The existing CI `test-e2e` job (main/nightly only) runs the whole suite as-is.
  **PO decision point:** cap nightly runtime by splitting into
  `test-e2e-core` (current 12 files) + `test-e2e-full` (nightly only) via
  markers if runtime grows beyond ~45 min in CI. Default: single suite, revisit
  when measured.

## 8. Environment levers the suite relies on (from audit E01–E04)

- `run_e2e.sh` must keep exporting `AUTH_JWT_SECRET` (FE proxy verify) — already
  inherited; add an explicit comment + assertion (a smoke spec fails fast if the
  proxy bounces to /login — pin for E01).
- WS tests run on the runner's own origin: on :3000 default no extra env needed;
  the suite adds a **red pin for N08** (origin check ignores test mode) instead
  of working around it.
- Sentiment graceful-degradation (E03) becomes a spec: without `--extra nlp`
  the endpoint must answer 503/422 machine-readable, not 500.

## 9. Docs & gates

- `docs/development/testing-standards.md`: new E2E section (scope, runner, mock
  catalog contract, when to add specs).
- Coverage matrix (§5) checked into `docs/development/e2e-coverage.md` and kept
  in sync per suite task (doc gate per task).
- CHANGELOG entry per release slice; feature docs updated only where behavior
  notes change (not per spec).

## 10. Risks

- Mock catalog drift vs real API schemas → mitigated by schema-typed fixtures
  (pydantic models reused from app code in fixtures) + a conftest check that
  every catalog entry validates.
- Headless DnD limitations (storyboard kanban, volume assign) → where
  unverifiable headless, assert the wire contract via API-side effects of the
  UI's own dispatch path, or mark `skipif` with rationale (documented).
- Playwright browser cache drift (chromium-1243 vs pinned 1228 seen in audit) →
  runner preflight gains a browser-presence check with clear remediation.
