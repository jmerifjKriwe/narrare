# Screenshot Font Determinism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining system-font dependencies from screenshot captures so local and CI renders do not open no-op screenshot PRs.

**Architecture:** Self-host IBM Plex Mono for the existing `--font-mono` token and replace the visible `⌘` glyph with a repo-owned SVG icon. All 25 masters are rebaselined once; the strict CI Screenshots run proves that environment-only glyph differences are gone. The workflow keeps its strict byte-level diff, so real pixel changes still open a PR.

**Tech Stack:** React, TypeScript, Tailwind/CSS, Playwright, Python, Fontsource WOFF2 assets.

**Spec:** `docs/superpowers/specs/2026-11-27-screenshot-font-determinism-design.md`

## Global Constraints

- No perceptual tolerance, coordinate mask or PNG re-encoding that can hide real UI changes.
- No browser-side font guard or meta E2E test; verify through bundled fonts and the CI Screenshots run.
- No literal emoji or system-font symbol in captured UI; prompt pills use repo SVG icons.
- No new route, API, schema or user-visible surface.
- Fonts are bundled under `web/public/fonts/` with their OFL license.
- Visible `⌘` is an SVG; the accessible shortcut notation is retained — TopBar's name is `Suchen K (⌘K)`, so its visible text is a literal substring of the name (WCAG label-in-name).
- All generated masters are real-stack 1600×1000 captures, below 1 MB.
- Two independent local captures must be byte-identical before commit.
- No merge without owner approval.

## Review Focus

- A bundled weight is missing: asset test pins all four WOFF2 files; the CSS contract pins all four `@font-face` weights.
- A literal `⌘` survives in rendered keycaps: TopBar/InspectorDock tests assert an SVG command icon and no visible U+2318 text.
- A mono surface still resolves to a system-only stack: CSS contract pins `--font-mono` to IBM Plex Mono as the first family.
- Fonts load after the screenshot: capture keeps the existing `document.fonts.ready` wait; a missing font shows up as a CI screenshot diff, not a second E2E suite.
- A real UI change is accidentally suppressed: no tolerance or alignment helper is introduced; the workflow's strict staged diff remains unchanged.
- Local and CI still rasterize differently: after push, the branch's Screenshots workflow must finish without opening a new screenshot PR.

---

### Task 1: Bundle deterministic screenshot fonts and rebaseline masters

**Files:**
- Create: `web/public/fonts/ibm-plex-mono-latin-400-normal.woff2`
- Create: `web/public/fonts/ibm-plex-mono-latin-500-normal.woff2`
- Create: `web/public/fonts/ibm-plex-mono-latin-600-normal.woff2`
- Create: `web/public/fonts/ibm-plex-mono-latin-700-normal.woff2`
- Create: `web/public/fonts/IBMPlexMono-OFL.txt`
- Modify: `web/globals.css` font tokens and `@font-face` declarations
- Modify: `web/ui/icons.tsx` command icon
- Modify: `web/components/TopBar.tsx`, `app/capabilities/writing/web/InspectorDock.tsx`
- Modify: `scripts/screenshots.py` system-font caveat only; keep `document.fonts.ready`
- Test: `web/components/TopBar.test.tsx`, `app/capabilities/writing/web/InspectorDock.test.tsx`, `app/kernel/tests/test_screenshot_assets.py`
- Regenerate: `assets/screenshots/*.png` (25 masters)

**Interfaces:**
- Produces: `IconName` value `command`.
- Produces: CSS token `--font-mono` whose first family is `"IBM Plex Mono"`.
- Produces: no new capture-time guard interface; existing `document.fonts.ready` wait remains.
- Consumes: pinned Fontsource 5.3.0 files at `https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-<weight>-normal.woff2` and the package `LICENSE`.

- [x] **Step 1: Add failing asset and component tests**

Add an asset contract asserting the four WOFF2 files and OFL license exist and `--font-mono` names IBM Plex Mono before any system fallback. Extend TopBar and InspectorDock tests so their keycaps contain a command SVG, contain no U+2318 text node and expose the accessible shortcut notation — TopBar's name is `Suchen K (⌘K)`, with its visible text a literal substring. Add a workflow contract asserting the strict `git diff --cached --quiet` gate remains and no pixel-tolerance/alignment helper is introduced.

- [x] **Step 2: Run the focused tests and verify red**

Run the TopBar, InspectorDock and screenshot asset tests. Expected: the new assertions fail because the font assets/token and command icon do not exist yet.

- [x] **Step 3: Add the pinned font assets and license**

Download the four 400/500/600/700 Latin WOFF2 files and `LICENSE` from Fontsource 5.3.0. Save the license as `web/public/fonts/IBMPlexMono-OFL.txt`. Do not add an npm dependency or mutable `latest` URL.

- [x] **Step 4: Wire the bundled mono family and command SVG**

Add `@font-face` declarations for IBM Plex Mono and make `--font-mono` start with `"IBM Plex Mono"`. Add a 16×16 single-stroke `command` icon to `web/ui/icons.tsx`. Replace the visible `⌘` in TopBar and InspectorDock with `<Icon name="command" size={10} />` inside inline-flex keycaps; keep the shortcut in the accessible name (`Suchen K (⌘K)` on TopBar) and the bundled mono `K`/`J`.

- [x] **Step 5: Keep the existing font-ready wait; no browser guard**

Keep `document.fonts.ready` in `_shot`. Replace the old system-font caveat in the module docstring with the honest statement that fonts are bundled and the CI Screenshots run is the verification. Do not add `_assert_pinned_fonts`, a meta E2E test or a browser-side validator.

- [x] **Step 6: Run focused tests and verify green**

Run the TopBar, InspectorDock and screenshot asset tests plus `just check`. Expected: all pass; no Playwright import is introduced into filesystem-only asset tests.

- [x] **Step 7: Rebaseline and prove local determinism**

Run two independent full captures. Compare all 25 PNGs and `docs/screenshots/README.md`; expected byte-identical runs. Inspect keycaps, badges and representative prose/planning frames, verify dimensions/size limits, and commit the regenerated masters with the source changes. The index should remain byte-identical because captions did not change.

- [x] **Step 8: Run the full gate**

Run `just verify` once on the final reviewed head. Expected: backend, web, build and all current app E2E suites pass. Record the final counts. Fix rounds use focused tests only.

- [x] **Step 9: Commit**

Commit `fix(web): use bundled fonts for keycaps and badges` with a real `User-visible:` line and Assisted-by trailer. Include the design, plan, font assets, source/tests and regenerated masters. Do not add a `Closes` keyword for the already closed #1010.

- [ ] **Step 10: Review, push and prove CI silence**

Independent reviewer checks the font source/license, SVG accessibility, CSS token, tests and all 25 masters. The `Screenshots` workflow runs only on `workflow_dispatch`, the Sunday schedule and `push` to `main`, so pushing the branch starts nothing. The proof is a manual dispatch, `gh workflow run screenshots.yml --ref fix/screenshot-render-noise`, which must succeed and open no new `chore/screenshots-*` PR; otherwise the proof is the post-merge `main` run. A new screenshot PR means the fix is not complete.

### Task 2: Replace remaining system-emoji glyphs (post-PR #1042 finding)

**Files:**
- Modify: `app/capabilities/writing/web/PromptBar.tsx`
- Test: `app/capabilities/writing/web/PromptBar.test.tsx`, `app/kernel/tests/test_screenshot_assets.py`
- Modify: design/plan glyph rule
- Regenerate: affected masters from new captures; close PR #1042 as superseded

**Interfaces:**
- Produces: prompt pills render repo `insights`, `chat` and `search` icons with `aria-hidden`; localized labels unchanged.

- [x] **Step 1: Add failing component and source contracts**

Assert the three prompt pills render repo SVG icons and contain no literal emoji. Add a narrow captured-UI source contract for emoji literals outside docs/scripts.

- [x] **Step 2: Replace the emoji with repo icons**

Use `insights` for the tension peak, `chat` for dialogue and `search` for detail; keep labels and pill behavior unchanged.

- [x] **Step 3: Recapture and prove determinism**

Run two independent full captures; expect only 20/21/22/23/35/36 to change. Prove byte-identical runs and an unchanged index.

- [x] **Step 4: Run focused gates and commit**

Run PromptBar tests, screenshot asset tests and `just check`; do not run full E2E in this task. Commit `fix(writing): draw prompt pills with repo icons` with User-visible and Assisted-by. No `Closes` for #1042.

- [ ] **Step 5: Close superseded PR**

After push, close PR #1042 with a comment naming the replacement commit and the pixel evidence.

