# UI Command-Fokus, Re-shoot-all — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every screenshot in `assets/screenshots/` shows the current UI: 5-icon rail (inkl. Planen), current gallery state (Target drafts + built specimens incl. storyboard section).

**Architecture:** Docs-only slice. No product code changes except two pre-triaged gallery nits (see Task 0) that live in files this slice touches anyway.

**Tech Stack:** `scripts/screenshots.py` (boots an ephemeral stack; use ports 8100/3200 if 8000/3100 are held by a sibling worktree), PNG assets, vitest.

**Spec:** Norm docs stay untouched. This slice executes the standing re-shoot follow-up recorded in the storyboard final review ("deliberate re-shoot-all next slice").

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr (no new user-visible strings expected; if one becomes necessary, add all three locales — a missing key is a build error).
- No product code changes. Gallery copy/test only (Task 0), screenshots only (Task 1).
- A re-shot PNG is kept only if the diff vs HEAD is a real content change (new rail icon, new specimen, changed UI) — pure rendering noise gets reverted (`git checkout -- <file>`), per established precedent.
- Every shot must be *read* (image viewed), not just produced: verify 5-icon rail, correct content, dark variant differs, no expanded rail over the gallery.
- Gates: `just check` · `pnpm --dir=web vitest run <path>` · `just test-e2e settings` (gallery E2E) · web build. A gate counts only when its output was read.
- E2E contexts use locale de-DE (script default; do not change).

## Review Focus

1. **A reverted PNG that actually carried a real change** — every revert must be justified in the report with what was compared (e.g. rail icons identical, only antialiasing differs). (Task 1.)
2. **A kept PNG that is only noise** — every kept rewrite must name its real content change. (Task 1.)
3. **Gallery copy drift** — the clarifying line must describe the specimen truthfully (specimen = built state, shot may differ in sync wording). (Task 0.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test) | Two pre-triaged nits only: (a) one clarifying line that the specimen's sync wording ("On track") may differ from the live shot ("Planned") without being a bug; (b) widen the ENTWURF-freedom assertion scope from the section div to the gallery section containing both drafts. |
| `assets/screenshots/*.png` | Full re-shoot; revert pure-noise rewrites. |
| `scripts/screenshots.py` | Change only if the script itself is broken for the re-shoot; otherwise untouched. |

---

### Task 0: Gallery copy/test nits (pre-triaged follow-ups)

- [ ] **Step 1: Failing tests first** — extend the ENTWURF-freedom assertion to the gallery section containing both drafts (RED: old scope passes vacuously — demonstrate by noting which element the old selector hits), and assert the clarifying line's presence if the test pins copy.
- [ ] **Step 2: Implement** — (a) one clarifying line in the storyboard specimen block: sync wording may differ from live shots without being a bug; (b) widen the ENTWURF assertion scope. No other gallery changes.
- [ ] **Step 3: Run** — `pnpm --dir=web vitest run ../app/capabilities/settings/web/DesignGallery.test.tsx` (path relative to web/), `pnpm --dir=web typecheck`, `just check`. Expected: PASS.
- [ ] **Step 4: Commit** — `docs(gallery): name the specimen-vs-shot sync wording` + `User-visible: none — gallery documentation only.` — check the commit-message hook accepts this; if the hook demands a real user-visible sentence, use the hook's exact rule from AGENTS.md (docs(chore?) — re-read the hook error and comply literally; development documentation uses a hidden type).

### Task 1: Full re-shoot + reads + commit

- [ ] **Step 1: Re-shoot** — run the script per its own usage (`--help` or justfile target if one exists; otherwise `python3 scripts/screenshots.py` from repo root with the ephemeral stack). Record ports used and any stack workaround.
- [ ] **Step 2: Triage every rewrite** — for each rewritten PNG, decide keep (name the real content change) vs revert (noise only). Document the decision per file in the report.
- [ ] **Step 3: Read** — view every kept PNG: 5-icon rail everywhere, correct per-shot content, dark variants differ from light, no expanded rail over the gallery, no truncated headline text in shelf/workspace shots.
- [ ] **Step 4: Run gates** — `just check`, frontend suite for the touched area, `just test-e2e settings`, web build. Expected: PASS.
- [ ] **Step 5: Commit** — `docs(screenshots): re-shoot all frames on the current shell` + a real `User-visible:` sentence (screenshots show the current UI incl. Planen rail) + `Assisted-by: OpenCode (<model>)` trailer. Report, no code.

---

## Self-Review

**Spec coverage.** Re-shoot-all follow-up from the storyboard final review → Task 1. Gallery nits from Task 2 deferred list → Task 0. Nothing else in scope.

**Type consistency.** No product code touched; test file paths relative to `web/`.

**Review Focus.** Three lines, each with its owning task + evidence. No silent reverts, no unexplained keeps.

**Proportion.** Two small tasks; the plan stays shorter than the work it describes is impossible here — kept minimal on purpose.
