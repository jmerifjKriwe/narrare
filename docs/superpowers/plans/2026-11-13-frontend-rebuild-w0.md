# Frontend Rebuild — W0 (Demolition and Scaffold) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the entire current frontend — UI code, web unit tests, E2E suites — keep the technical plumbing and every gate green, and leave the app booting to one interim welcome placeholder under the setup capability.

**Architecture:** The v2 capability structure stays: the shell (`web/`) keeps plumbing only (build config, i18n engine, API client, tokens), every capability's `web/` folder is deleted except `setup`, which shrinks to a placeholder page owning `/` and `/setup`. The capability-facts generator learns that a capability without `web/` has no UI facts; the E2E affected-resolver learns that a repo with no suites owes none.

**Tech Stack:** unchanged — Vite + React + TanStack Router + Tailwind v4, vitest, pytest + Playwright, `just` gates.

**Spec:** `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md` (waves, decisions, issue mechanism). The plan argues from it; executors read both.

## Global Constraints

- One capability is one folder; the shell holds no hand-written route list — routes come from `app/capabilities/*/web/routes.tsx` through `just generate`.
- English in code, tests, docs and issues; user-visible text in en/de/fr catalogs (sorted, same keys) — German copy uses **du**.
- No UI is invented locally: the W0 placeholder is explicitly the approved interim state, not a design.
- Nothing is committed before its task's gates are green; conventional commits, hidden types only (`chore`, `refactor`, `test`, `ci`) — no `User-visible:` line anywhere in W0. Every commit ends with `git commit --trailer 'Assisted-by: OpenCode (<model>)'`.
- `--no-verify` and force push are forbidden.
- Work happens on branch `chore/w0-frontend-demolition`; one PR for the wave; the PR title is plain language, not conventional.
- Backend (`app/` outside `*/web/` and `*/e2e/`) is not touched.

## Review Focus

1. **affected.py with zero suites**: a change touching the shared surface `web/` must resolve to zero suites with a printed reason, not exit 3 — pinned by new cases in `app/kernel/tests/test_affected.py` (Task 6).
2. **Generator with UI-less capabilities**: `just generate` must not emit nav/INDEX rows whose title keys live in deleted catalogs — pinned by `just check-generated` (Task 3).
3. **The router still boots with exactly one capability route**: production build and a dev-server smoke on `/` pin it (Task 4).
4. **The vitest suite stays non-empty and keeps the token gates**: `just test-frontend` must run the plumbing tests including the moved `tokens.test.ts` (Task 5).
5. **Issue triage must not close backend bugs**: the close list is reviewed line-by-line against the triage rule before any `gh issue close` runs (Task 9).

---

### Task 1: Archive the six new Stitch screens

**Files:**
- Create: `docs/design/stitch/screens/library/welcome-atelier.{html,webp}`, `setup-step1-basis-vorlage.{html,webp}`, `setup-step2-dramaturgie-struktur.{html,webp}`, `setup-step3-ki-regeln-tonalitaet.{html,webp}`, `setup-step4-bereitstellung-start.{html,webp}`, `shelf-filter-open.{html,webp}`
- Modify: `docs/design/stitch/README.md` (screen table)
- Delete: `docs/design/stitch_narrare.zip`

**Interfaces:**
- Consumes: the zip the owner placed at `docs/design/stitch_narrare.zip` (already extracted read-only to `/tmp/opencode/stitch_export/stitch_narrare/`).
- Produces: the archived drafts W1 harmonizes; W2 ports. Names above are the plan's canonical slugs.

- [ ] **Step 1: Copy each screen's `code.html` → `<slug>.html` and `screen.png` → `<slug>.webp`** (convert with `cwebp -q 82` like the existing archives; if `cwebp` is missing, keep `.png` and note it in the README row).

- [ ] **Step 2: Add six rows to the README screen table** (area `Library and entry`, original German labels from the folder names, heights from `identify`).

- [ ] **Step 3: Verify:** `unzip -l` gone, six folders present, README table mentions all six.

- [ ] **Step 4: Commit**

```bash
git add docs/design/stitch/
git commit -m "chore(docs): archive the six new Stitch onboarding drafts"
```

### Task 2: Close the orphaned fidelity work

**Files:** none in-repo (GitHub + git housekeeping).

- [ ] **Step 1:** `gh pr close 808 --comment "Superseded by the frontend rebuild from the Stitch drafts (see docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md)."` and delete its branch.
- [ ] **Step 2:** Remove the worktrees `narrare-w3` (feat/literary-modernism-w3) and the opencode `shelf-fidelity` worktree, then `git branch -D feat/literary-modernism-w3 feat/shelf-fidelity` (branches exist only off-remote now).
- [ ] **Step 3: Verify:** `gh pr view 808 --json state` → CLOSED; `git worktree list` shows only the main checkout and unrelated issue worktrees.

### Task 3: Demolish capability web UIs; teach the generator UI-less capabilities

**Files:**
- Delete: `app/capabilities/{chat,knowledge,planning,prompts,settings,writing}/web/` entirely
- Modify: `scripts/generate_capabilities.py` (nav/INDEX/views skip capabilities without `web/`), regenerated views under `app/generated/`, `web/lib/generated/`, `docs/user/INDEX.md`, `docs/user/help-coverage.md`

**Interfaces:**
- Produces: generator semantics — *a capability without a `web/` directory contributes no nav row, no route import, no INDEX row, no catalog import, no dock/command/settings/help entries.* `capability.yaml` files stay untouched.

- [ ] **Step 1:** Delete the six capability `web/` folders.
- [ ] **Step 2:** Run `just generate`; fix `generate_capabilities.py` where a view now fails or would emit a row whose title key no longer resolves (nav view, INDEX, help-coverage, docks, commands, settingsPages, routes, workspace leaf). The rule is the Interfaces line above; `setup` keeps its rows.
- [ ] **Step 3: Verify:** `just generate && just check-generated` — but note `check-generated` needs the network (`pnpm dlx`); locally `git diff --exit-code -- app/generated web/lib/generated docs/user/INDEX.md docs/user/help-coverage.md` after `just generate`.
- [ ] **Step 4: Verify:** `just typecheck` (web side still sees only generated leftovers + plumbing).
- [ ] **Step 5: Commit** `chore(web): remove capability UIs, generator learns UI-less capabilities`

### Task 4: Interim setup placeholder owning `/` and `/setup`

**Files:**
- Rewrite: `app/capabilities/setup/web/routes.tsx` (routes for `/` and `/setup`), `app/capabilities/setup/web/SetupPage.tsx` (placeholder)
- Modify: `app/capabilities/setup/web/i18n/{en,de,fr}.json` (interim keys only)
- Delete: `app/capabilities/setup/web/SetupPage.test.tsx`

**Interfaces:**
- Produces: route paths `/` and `/setup` rendering one placeholder (`setup.interimTitle`, `setup.interimBody` — honest interim copy naming the rebuild); no chrome, no forms. Render-only, no unit test owed (TESTING.md); the setup E2E returns in W2.

- [ ] **Step 1:** Replace the three files above; keep the page announcing the rebuild in plain du-tone German/English/French, neutral tokens only.
- [ ] **Step 2:** `just generate` (routes table now: setup only) and verify `git diff` clean after regeneration.
- [ ] **Step 3: Verify:** `just build` succeeds; `just dev-api & just dev-web &` then `curl -s localhost:3100/ | grep -i narrare` renders; stop both.
- [ ] **Step 4: Commit** `chore(web): interim setup placeholder owns the root route`

### Task 5: Demolish the shell UI; keep and move the plumbing gates

**Files:**
- Delete: `web/components/`, `web/routes/__root.test.tsx`, `web/routes/settings-area.test.tsx`, `web/lib/{save,save.test,stream,commands,commands.test,search,palette,shortcuts,shortcuts.test,dirty,dirty.test,announce,proposal,area,area.test,exportAge,exportAge.test}.{ts,tsx}` (importers are all deleted code — verified by `rg`)
- Move: `web/ui/tokens.test.ts` → `web/lib/tokens.test.ts` (imports are relative, `new URL("..")` keeps pointing at `web/`)
- Delete: the rest of `web/ui/`
- Rewrite: `web/routes/__root.tsx` (providers, locale/theme adoption, pageTitle, globals.css import, `Outlet`, minimal error component — no TopBar/IconRail/Palette)
- Keep: `web/main.tsx`, `web/router.tsx`, `web/globals.css`, `web/index.html`, `web/lib/{i18n,locale,formality,theme,query,pageTitle,format,words,time,platform}*` and `web/lib/api/`, `web/scripts/`

**Interfaces:**
- Produces: the shell's kept surface — `router.tsx` unchanged (mounts generated routes), `__root` without chrome. `web/lib` keeps exactly the files whose importers survive; anything else is reachable again from git history when a port needs it.

- [ ] **Step 1:** Apply the delete/move/rewrite list.
- [ ] **Step 2: Verify:** `just typecheck`, `just lint`, `just test-frontend` — the run must list the plumbing tests including `web/lib/tokens.test.ts` (Review Focus 4).
- [ ] **Step 3: Verify:** `just dev-web` renders `/` placeholder (Task 4) — then stop.
- [ ] **Step 4: Commit** `refactor(web): shell keeps plumbing, chrome is demolished`

### Task 6: Demolish E2E; affected-resolver learns the zero-suites interim

**Files:**
- Delete: `app/capabilities/*/e2e/` (all seven, including showcase specs and conftests)
- Modify: `scripts/affected.py`, `app/kernel/tests/test_affected.py`, `TESTING.md`, `docs/design/stitch/SCREENSHOT-COMPARISON.md`

**Interfaces:**
- Produces: resolver semantics — *when the repo holds no capability e2e directory, every answer — including "all suites" and the shared-surface and harness-smoke resolutions — is the empty set with a printed reason naming the rebuild interim; exit 3 stays reserved for suites owed but unnameable.* The first rebuilt suite (W2, setup) needs no further resolver change.

- [ ] **Step 1: Write the failing tests** in `app/kernel/tests/test_affected.py`: (a) shared-surface change (`web/`) with zero e2e dirs → empty set, exit 0, reason mentions the interim; (b) harness/CI-definition change → empty set (no smoke suite exists); (c) `--paths all` with zero dirs → empty set, exit 0.
- [ ] **Step 2: Run** `just test-file app/kernel/tests/test_affected.py` — expect the new cases FAIL (current code exits 3).
- [ ] **Step 3:** Delete the e2e directories; implement the resolver rule in `scripts/affected.py` (the existence check is over `app/capabilities/*/e2e`, one glob, no per-capability table).
- [ ] **Step 4: Run** `just test-file app/kernel/tests/test_affected.py` — PASS; then `just test-e2e` → prints the no-suite reason, exit 0.
- [ ] **Step 5:** Update `TESTING.md` (E2E section: suites were removed with the UI in W0, each rebuilt screen ships its suite, fake-provider rule unchanged) and `SCREENSHOT-COMPARISON.md` (showcase suspended until the screens return).
- [ ] **Step 6: Commit** `test(e2e): suites leave with the UI; resolver names the zero-suites interim`

### Task 7: Shared i18n catalog cleanup

**Files:**
- Modify: `i18n/{en,de,fr}.json`, `i18n/overlays/formality/{de,fr}.json`

- [ ] **Step 1:** For every shared key, `rg "\"<key>\"" web app --glob '!web/lib/i18n*'` — remove keys (and their overlay variants) with no remaining consumer; keep parity: same key set in all three catalogs (the vitest i18n tests enforce this).
- [ ] **Step 2: Verify:** `just test-frontend` green; `just generate` produces no diff.
- [ ] **Step 3: Commit** `chore(i18n): shared catalogs lose the demolished UI's keys`

### Task 8: Pause the screenshots workflow

**Files:**
- Modify: `.github/workflows/screenshots.yml`

- [ ] **Step 1:** Remove the `schedule:` and `push:` triggers (keep `workflow_dispatch`), with a comment: paused by the frontend rebuild W0 — re-enable when the shelf and workspace screens are rebuilt (the script drives the real UI).
- [ ] **Step 2: Verify:** `python3 scripts/affected.py harness --json` still exits 0 (CI-definition change, zero suites).
- [ ] **Step 3: Commit** `ci(screenshots): pause the weekly capture during the rebuild`

### Task 9: Close the frontend/E2E issue batch

**Files:**
- Modify: `docs/superpowers/follow-ups.md` (the wave's row)

- [ ] **Step 1: Build the preselect:** `gh issue list --state open --limit 300 --json number,title,labels` → all `area: web`; every issue whose title names an e2e/web test (incl. `kind: test-gap`, `kind: flake` with such subjects); `follow-up-index` issues.
- [ ] **Step 2: Triage each** against the rule: close what lives in deleted code; keep backend logic bugs (deadlocks, export backup strand, cached passage search), kernel/tooling/ci/docs issues, and findings about kept plumbing (e.g. #727 root-level build files). Produce the final list as a checked table in the PR body.
- [ ] **Step 3: Close** each with: `Closed by the frontend rebuild (docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md): the code this lived in is removed. Re-open if the rebuilt screen reintroduces it.` — an index closes with its last child.
- [ ] **Step 4:** Add the wave's row to `docs/superpowers/follow-ups.md`; commit `chore(follow-ups): W0 rebuild wave closes the frontend and E2E batch`.

### Task 10: Wave gate, branch, PR

- [ ] **Step 1:** `just verify` (check, backend tests, frontend plumbing tests, production build, e2e no-op) — read the output.
- [ ] **Step 2:** Push the branch, open the PR: title in plain language (e.g. "Remove the current frontend ahead of the Stitch-based rebuild"), body links the spec, the plan, the issue-closing table, and states the app's interim behaviour.
- [ ] **Step 3:** After CI: the `e2e-suites` job must report the owed-nothing skip, `frontend` and `check-generated` green. Merge only after review per AGENTS.md.

---

## After W0 (not this plan)

W1 — Stitch harmonization rounds via MCP (merge round, states, dark, FR, du-tone, landing round), ending in the owner's checkpoint in Stitch. W2's plan is written against those final drafts: welcome + wizard port, setup backend fields, setup E2E — one wave, one PR.
