# W0-3 — Nightly CI Failure Streak Diagnosis (Frontend + E2E)

> **Task:** W0-3 of `docs/superpowers/specs/2026-10-16-ci-r1-event-driven-redesign.md` (§10, Wave 0)
> **Date:** 2026-10-16 · **Author:** Platform layer (log-based diagnosis, read-only)
> **Method:** `gh api` run/job/log analysis of all `schedule` runs 2026-10-08..10-16, PR run
> cross-checks, commit/PR timeline reconstruction. No code or workflow changes made.

---

## 1. Run table (schedule event, ci.yml, 2026-10-08 → 2026-10-16)

| Run | Date (UTC) | Head | Result | Failed job | Exact failing tests / error |
|---|---|---|---|---|---|
| 37912007524 | 10-09 | `64b9ea72` | ✅ success | — | — |
| 38039478235 | 10-10 | `9482c220` | ❌ failure | Architecture Constraints | `uv sync`: **CPython 3.15.0** picked → `psycopg-binary==3.3.4 … doesn't have a source distribution or wheel for the current platform` (only `cp314` wheels) → exit 2; all test jobs skipped |
| 38127689277 | 10-11 | `0a9174c0` | ✅ success | — | — |
| 38231495215 | 10-12 | `3c5459ce` (#251) | ❌ failure | E2E (1/29 failed) | `test_settings_persistence.py::TestSettingsPersistence::test_settings_general_tab_renders` — `Locator.click: Timeout 30000ms` |
| 38378197806 | 10-13 | `981c6edb` (#252) | ✅ success | — | — |
| 38531844492 | 10-14 | `82293cc6` (#253) | ❌ failure | E2E (1 error/37) | `test_environment_smoke.py::test_proxy_keeps_authenticated_user_out_of_login` **ERROR at setup** (`authenticated_page` fixture): `Page.goto: Timeout 30000ms` |
| 38700481557 | 10-15 | `3b8f8714` (#256) | ❌ failure | Frontend + E2E (4F+1E/51) | **Frontend:** vitest `KBEnhanceReview.test.tsx > shows before/after comparison after enhancement completes` — `TestingLibraryElementError: Unable to find an element with the text: Description` (1/3916). **E2E:** 3× `test_ai_writing_selection.py` `Page.reload: Timeout 30000ms` + `test_ai_writing.py::TestGenerateErrorPaths::test_empty_form…` reload timeout + env-smoke setup `goto` timeout again |
| 38867487325 | 10-16 | `a59268f9` (#257) | ❌ failure | E2E (1/51 failed) | `test_ai_writing.py::TestGhostText::test_ghost_text_tab_accept_inserts_suggestion` — `.ghost-text-suggestion` not visible in 30s; **zero `/suggest` API calls** during the test window (frontend never fired the request) |

Bottom line vs. the briefing: the streak is **not** "Frontend + E2E together since Oct 10".
It is: 1× environment drift (Oct 10, Architecture), 1× pre-existing E2E flake (Oct 12),
3× E2E timeouts on the newly expanded suite (Oct 14/15/16), and exactly **one** Frontend
failure (Oct 15, a single flaky vitest test). Oct 16 (this morning) also failed — E2E only.

## 2. Failure clusters

### Cluster A — E2E timeouts on the nightly (Oct 12, 14, 15, 16 — the recurring one)

**Signatures:** Playwright `Timeout 30000ms` of four flavors — `Locator.click`,
`Page.goto` (fixture setup), `Page.reload`, `Locator.wait_for` — **on a different spec
every night**; every failed spec passes on at least one other nightly:

- `test_settings_general_tab_renders` failed Oct 12 → green Oct 13.
- env-smoke errored Oct 14 + 15 → **passed** Oct 16.
- `test_empty_form_shows_localized_validation…` + selection specs failed Oct 15 → **passed** Oct 16 (seen passing at 07:40:07).
- `TestGhostText::tab_accept` failed Oct 16 → **passed** Oct 15.

Oct 15 additionally shows server-side distress: API log dump contains
`Started server process [3366]` (a mid-run API restart), Next proxy
`Failed to proxy …/api/v1/auth/refresh Error: read ECONNRESET`, and an
`AUTHENTICATION_ERROR` login at 07:49:15 — matching the fixture-setup goto timeout.
Suite runtime grew 205s (Oct 12, 29 tests) → 376s (Oct 15, 51 tests).

**Root cause chain (≥2× why):**
1. *Why do new E2E specs fail on main?* Because the nightly is their **first-ever
   execution**: the `E2E Tests` job is skipped on every `pull_request` run (verified on
   the PR runs of #253 and #256 — `E2E Tests: skipped`; it exists only on
   schedule/workflow_dispatch). #253 (+`test_environment_smoke.py`, foundation helpers,
   mock catalog) and #256 (+`test_ai_writing*.py`, +14 WRITE-00x specs, WS specs) merged
   with **zero E2E verification anywhere**.
2. *Why do they time out instead of failing deterministically?* Because the failures are
   latency flakes under first-exposure load: 30s per-action timeouts against a production
   standalone Next server + a single uvicorn process, with the suite ~80% heavier than a
   week ago; the same specs pass on other nights once the page/server is warm and fast.
   The ghost-text case is client-side: no `/suggest` request was ever issued in its 30s
   window (typing/hydration race), so there was nothing for the (healthy, 4–7ms mocked)
   API to answer.
3. *Why does this keep failing nightly?* Because with no branch protection (GitHub Free,
   per spec §1) nothing blocks merging unverified specs, and the nightly's base-SHA
   red/green bookkeeping doesn't exist yet (that is Wave 1's gate).

### Cluster B — Frontend job, Oct 15 only (single occurrence)

**Signature:** `vitest run --coverage`: `Test Files 1 failed | 458 passed`,
`KBEnhanceReview.test.tsx > shows before/after comparison after enhancement completes` →
`TestingLibraryElementError: Unable to find an element with the text: Description`.
biome, i18n validation, file-size check, type-check all **passed**; there is **no VRT /
Playwright / build step in the Frontend job** (the briefing's VRT hypothesis is void —
the job is biome+i18n+size+type-check+vitest). The file was last modified 2026-08-10
(`7f722f48`, itself a flake-hardening commit) and the job was green again Oct 16 on a
docs-only delta → **transient flake**, not a regression from #256 (which did not touch it).
The `ECONNREFUSED/ETIMEDOUT :3000` flood in the same log is MSW unhandled-request noise
from other vitest files, non-fatal.

### Cluster C — Architecture job, Oct 10 only (world drift)

**Signature:** `uv` resolved **CPython 3.15.0** (`.python-version` = `3.14` is a
minor-only hint; `requires-python = ">=3.14"` permits 3.15; ci.yml sets no
`UV_PYTHON`/`python-version` pin for setup-uv) → `psycopg-binary==3.3.4` has no cp315
wheels → `uv sync --frozen` exit 2. Self-healed Oct 11. Not #256-related (predates it by
5 days). Likely same family as the W0-1 push-cluster; push failures sampled are
heterogeneous (release-please, TS error) — left to W0-1 to cluster.

### Cluster D — non-fatal background noise (flagged, not a job-killer)

Recurring `ForeignKeyViolationError` on `writing_activity_events.chapter_id_fkey`
(`writing_stats_record_failed`, handled → warning level): the async writing-stats
recorder inserts events for chapters that test teardown has already deleted. Never
failed a job, but pollutes logs and indicates a real recorder/teardown race in
`apps/api/narrare/analytics/writing_stats_recorder.py`.

## 3. Hypothesis verdict: **REFUTED (as stated), PARTIAL in spirit**

- **Refuted factually:** PR #256 merged **2026-10-15T05:59Z**, not ~Oct 9-10. Failures
  began Oct 12 (three days *before* #256) and Oct 10's failure is uv/CPython world drift.
  Neither Oct 12 (old spec, `3c5459ce`) nor Oct 14 (env-smoke from **#253**) involved
  #256 code. #256's squash SHA was never covered by a green E2E run anywhere — but its
  specs are flaky-timeout, not deterministically broken (they passed Oct 16).
- **Partial in spirit:** the *intensity* of the streak (3 consecutive nights, growing
  failure counts) does track the Phase-B E2E wave — #253 (foundation, Oct 13) and #256
  (specs, Oct 15) — because both landed never-executed specs straight onto the nightly
  through the PR-skips-E2E gate hole.

## 4. Proposed fix scope (for W0-4; NOT implemented here)

| Cluster | Fix | Files | Est. LOC | Regression-test meaningfulness |
|---|---|---|---|---|
| A (gate hole) | Run `E2E Tests` on `pull_request` for e2e/backend/frontend path filters (mirrors spec §5.1 `e2e = backend ∨ frontend`); keeps nightly as second net | `.github/workflows/ci.yml` | ~15–25 | High — closes the "specs merge never-run" hole permanently |
| A (spec robustness) | Hydration-safe waits before typing/clicks in new specs (wait for `.ProseMirror` + stable selection), first-load goto budget ≥ page 'networkidle' fallback in `authenticated_page` fixture, optional per-test retry=1 for nightly-only suite | `tests/e2e/foundation.py`, `tests/e2e/helpers/editor_ai.py`, `tests/e2e/test_ai_writing.py`, `tests/e2e/test_ai_writing_selection.py` | ~40–80 | High — converts known flake classes (precedent: `168945f4` "harden all reload navigations against dev-proxy stalls") into green |
| B | Stabilize the KBEnhanceReview before/after assertion (wait-for + role-based query instead of text node match) | `packages/web/components/studio/kb/__tests__/KBEnhanceReview.test.tsx` | ~10–20 | Medium — single flake observed; file has flake history |
| C | Pin interpreter: `UV_PYTHON: "3.14"` (env) or setup-uv `python-version: 3.14` for every `uv sync` job | `.github/workflows/ci.yml` | ~5–15 | Medium — converts one-off world drift into an impossible state |
| D (flag, separate task) | Guard `record_delta` against torn-down chapters (existence check / FK-safe skip) | `apps/api/narrare/analytics/writing_stats_recorder.py` | ~10 | Low urgency — noise reduction only |

**W0-4 gate feasibility:** clusters A+C fixes are prerequisites for "3 consecutive green
full nightlies"; B must land too (any single vitest failure fails the Frontend job).

## 5. Key log evidence (excerpts)

```
# Oct 10 — Architecture (world drift):
error: Distribution `psycopg-binary==3.3.4 @ registry+https://pypi.org/simple` can't be
installed because it doesn't have a source distribution or wheel for the current platform
hint: You're using CPython 3.15 (`cp315`), but `psycopg-binary` (v3.3.4) only has wheels
with the following Python ABI tag: `cp314`

# Oct 12 — E2E (old-spec flake):
FAILED tests/e2e/test_settings_persistence.py::TestSettingsPersistence::test_settings_general_tab_renders[chromium]
  - playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.
  =================== 1 failed, 28 passed in 204.97s ===================

# Oct 14 — E2E (new-in-#253 spec, fixture setup):
ERROR at setup of TestEnvironmentSmoke.test_proxy_keeps_authenticated_user_out_of_login
  - playwright._impl._errors.TimeoutError: Page.goto: Timeout 30000ms exceeded.
  ============== 35 passed, 1 xfailed, 1 error in 223.06s ==============

# Oct 15 — E2E + Frontend:
FAILED tests/e2e/test_ai_writing_selection.py::TestCoAuthor::…  Page.reload: Timeout 30000ms
========= 4 failed, 45 passed, 1 xfailed, 1 error in 376.04s =========
INFO:     Started server process [3366]          # API restart mid-run
Failed to proxy http://localhost:8000/api/v1/auth/refresh Error: read ECONNRESET
Test Files  1 failed | 458 passed (459)   # Frontend: KBEnhanceReview, vitest only
TestingLibraryElementError: Unable to find an element with the text: Description.

# Oct 16 — E2E ghost text (no request ever fired):
FAILED tests/e2e/test_ai_writing.py::TestGhostText::test_ghost_text_tab_accept_inserts_suggestion[chromium]
  - waiting for locator(".ghost-text-suggestion").first to be visible
# API log in same window: /suggest 200 OK in 31–35ms (mocked, 4–7ms model time)
# for the *passing* sibling test; zero /suggest calls during the failing one.
```

PR-run verification (gate hole): `E2E Tests: skipped` on PR run 38686827698 (#256) and
38433774787 (#253); E2E exists only on schedule/dispatch.
