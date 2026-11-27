# Screenshot Font Determinism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining system-font dependencies from screenshot captures so local and CI renders do not open no-op screenshot PRs.

**Architecture:** Self-host IBM Plex Mono for the existing `--font-mono` token and replace the visible `⌘` glyph with a repo-owned SVG icon. Capture asserts the bundled fonts are loaded and used, then all 25 masters are rebaselined once. The workflow keeps its strict byte-level diff, so real pixel changes still open a PR.

**Tech Stack:** React, TypeScript, Tailwind/CSS, Playwright, Python, Pillow, Fontsource WOFF2 assets.

**Spec:** `docs/superpowers/specs/2026-11-27-screenshot-font-determinism-design.md`

## Global Constraints

- No perceptual tolerance, coordinate mask or PNG re-encoding that can hide real UI changes.
- No new route, API, schema or user-visible surface.
- Fonts are bundled under `web/public/fonts/` with their OFL license.
- Visible `⌘` is an SVG; accessible shortcut labels keep their existing text.
- All generated masters are real-stack 1600×1000 captures, below 1 MB.
- Two independent local captures must be byte-identical before commit.
- No merge without owner approval.

## Review Focus

- A bundled weight is missing or fails to load: asset test pins all four WOFF2 files and the capture asserts `document.fonts.check` for 400/500/600/700.
- A literal `⌘` survives in rendered keycaps: TopBar/InspectorDock tests assert an SVG command icon and no visible U+2318 text.
- A mono surface still resolves to a system-only stack: CSS contract pins `--font-mono` to IBM Plex Mono and the capture guard rejects computed mono families without it.
- Fonts load after the screenshot: capture waits for `document.fonts.ready` and the bundled-weight checks before every shot.
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
- Modify: `scripts/screenshots.py` capture-time font guard and caveat
- Test: `web/components/TopBar.test.tsx`, `app/capabilities/writing/web/InspectorDock.test.tsx`, `app/kernel/tests/test_screenshot_assets.py`
- Regenerate: `assets/screenshots/*.png` (25 masters)

**Interfaces:**
- Produces: `IconName` value `command`.
- Produces: CSS token `--font-mono` whose first family is `"IBM Plex Mono"`.
- Produces: `_assert_pinned_fonts(page) -> None` in `scripts/screenshots.py`, called from `_shot` after `document.fonts.ready`.
- Consumes: pinned Fontsource 5.3.0 files at `https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-<weight>-normal.woff2` and the package `LICENSE`.

- [x] **Step 1: Add failing asset and component tests**

Add an asset contract asserting the four WOFF2 files and OFL license exist and `--font-mono` names IBM Plex Mono before any system fallback. Extend TopBar and InspectorDock tests so their keycaps contain a command SVG, contain no U+2318 text node and still expose the existing accessible shortcut labels. Add a workflow contract asserting the strict `git diff --cached --quiet` gate remains and no pixel-tolerance/alignment helper is introduced.

- [x] **Step 2: Run the focused tests and verify red**

Run the TopBar, InspectorDock and screenshot asset tests. Expected: the new assertions fail because the font assets/token and command icon do not exist yet.

- [x] **Step 3: Add the pinned font assets and license**

Download the four 400/500/600/700 Latin WOFF2 files and `LICENSE` from Fontsource 5.3.0. Save the license as `web/public/fonts/IBMPlexMono-OFL.txt`. Do not add an npm dependency or mutable `latest` URL.

- [x] **Step 4: Wire the bundled mono family and command SVG**

Add `@font-face` declarations for IBM Plex Mono and make `--font-mono` start with `"IBM Plex Mono"`. Add a 16×16 single-stroke `command` icon to `web/ui/icons.tsx`. Replace the visible `⌘` in TopBar and InspectorDock with `<Icon name="command" size={10} />` inside inline-flex keycaps; retain `aria-label` shortcut text and the bundled mono `K`/`J`.

- [x] **Step 5: Add the capture-time font guard**

Implement `_assert_pinned_fonts(page) -> None` and call it in `_shot` after `document.fonts.ready`. It asserts bundled mono weights 400/500/600/700 are available, every rendered `.font-mono`/computed-mono element includes `"IBM Plex Mono"`, and `document.body.innerText` contains no U+2318. Replace the old system-font caveat in the module docstring with the new invariant.

- [x] **Step 6: Run focused tests and verify green**

Run the TopBar, InspectorDock and screenshot asset tests plus `just check`. Expected: all pass; no Playwright import is introduced into filesystem-only asset tests.

- [x] **Step 7: Rebaseline and prove local determinism**

Run two independent full captures. Compare all 25 PNGs and `docs/screenshots/README.md`; expected byte-identical runs. Inspect keycaps, badges and representative prose/planning frames, verify dimensions/size limits, and commit the regenerated masters with the source changes. The index should remain byte-identical because captions did not change.

- [x] **Step 8: Run the full gate**

Run `just verify`. Expected: backend, web, build and all current E2E suites pass. Record the final counts.

- [x] **Step 9: Commit**

Commit `fix(web): use bundled fonts for keycaps and badges` with a real `User-visible:` line and Assisted-by trailer. Include the design, plan, font assets, source/tests and regenerated masters. Do not add a `Closes` keyword for the already closed #1010.

- [ ] **Step 10: Review, push and prove CI silence**

Independent reviewer checks the font source/license, SVG accessibility, capture guard, tests and all 25 masters. After approval, push the branch and observe its `Screenshots` workflow. Expected: the run succeeds and opens no `chore/screenshots-*` PR. A new screenshot PR means the fix is not complete.
