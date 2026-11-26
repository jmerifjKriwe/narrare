# README Screenshot Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every finding #977–#991 on `chore/readme-screenshots`, with no follow-up debt remaining at merge.

**Architecture:** Product fixes stay in their owning capabilities; documentation truth stays in the hand-maintained inventory/design docs; screenshot publication and workflow logic stay in the capture/tooling seam. Every affected master is regenerated from the real stack after the product fixes land.

**Tech Stack:** Python 3.14, pytest, PIL, Playwright, TypeScript/React, Vitest, GitHub Actions, actionlint, zizmor, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-26-readme-screenshot-followups-design.md`.

## Global Constraints

- Issues #977–#991 are claimed with `status: in-progress`; each must close from its fixing commit.
- No new capability, route, API, schema or migration unless a finding proves it unavoidable.
- English in code, tests and developer documentation; user-visible text remains localized in en/de/fr catalogs.
- UI/frontend work is implemented and reviewed by subagents with explicit model names.
- No force push, no rewrite of pushed history, `--no-verify`, skipped flake or deferred minor finding. Local unpushed commits may be rebuilt into coherent task commits.
- Frames remain real-stack 1600×1000 PNGs below 1 MB; two independent captures must match byte-for-byte.
- The workflow remains advisory and loop-safe.
- Every task gets an independent review; the final branch gets a whole-branch review and `just verify`.

## Review Focus

1. **A docs claim changes without a resolving test** — #977/#980 need state evidence and relative-link resolution, not only edited prose.
2. **A determinism test repeats the implementation's own random key** — #978 must compare identical names under different UUIDs and reversed input order.
3. **English UI content is still German or time-stale** — #984/#986/#989 need catalog/metadata tests, not visual inspection alone.
4. **Publication succeeds but rollback loses the last good copy** — #983/#987 need filesystem-only tests for separate filesystems, restore failure and backup retention.
5. **The workflow retriggers or skips on a large path list** — #982 needs executable decide-logic tests for bot merge, UI changes, docs-only pushes and large diffs.

---

## Task 1: Correct documentation truth and relative links (#977, #980)

**Files:**
- Modify: `docs/features/INDEX.md:64,112`
- Modify: `docs/design/stitch/README.md:7,9`
- Test: `app/kernel/tests/test_screenshot_assets.py`

**Interfaces:**
- Produces no runtime interface.
- Adds `test_all_relative_stitch_markdown_links_resolve` or equivalent in the existing screenshot asset test module.

- [x] **Step 1: Add a failing link-resolution test**

Parse every relative Markdown link in `docs/design/stitch/README.md`; resolve it against the file's parent and assert the target exists. Exclude anchors and absolute URLs. Run `just test-file app/kernel/tests/test_screenshot_assets.py` and confirm the two `../superpowers/specs/...` links fail.

- [x] **Step 2: Correct the links and inventory state**

Change the two links to `../../superpowers/specs/...`. Change `Structure view (PLAN-003)` from `live` to `backend`; leave its phase and description unchanged. Correct the AI-continuation inventory wording at line 64 from "at the caret" to "below the prose", matching the product and README.

- [x] **Step 3: Run the focused tests**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: PASS.

- [x] **Step 4: Review and commit**

Reviewer verifies the route/API evidence and link targets. Commit `docs(readme): correct the feature inventory and Stitch spec links` with `Closes #977`, `Closes #980`, a real `User-visible:` line and the Assisted-by trailer.

## Task 2: Make lore-graph layout deterministic across fresh UUIDs (#978)

**Files:**
- Modify: `app/capabilities/knowledge/web/graphLayout.ts`
- Modify: `app/capabilities/knowledge/web/LoreGraphPage.tsx`
- Test: `app/capabilities/knowledge/web/graphLayout.test.ts`
- Test: `app/capabilities/knowledge/web/LoreGraphPage.test.tsx`
- Test: `app/capabilities/knowledge/e2e/test_graph_e2e.py`
- Modify: `scripts/screenshots.py` graph seed/comments
- Modify: `scripts/screenshot_manifest.py` graph captions
- Regenerate: `assets/screenshots/39-graph.png`, `40-graph-dark.png`, `docs/screenshots/README.md`

**Interfaces:**
- `LayoutEntity` gains `name: string`.
- `layoutGraph(entities, relations, width, height)` sorts nodes by case-folded `name`, then `id` only as a duplicate-name tiebreaker.
- `graphSignature(...)` uses the same canonical name/id key.
- Parallel relation arcs use a content key (`from`, `to`, `type`, `note`) before falling back to `id`.

- [x] **Step 1: Write failing unit tests**

Add tests proving identical positions for the same names under different UUID-shaped IDs, reversed input order, case-folded name ordering, duplicate-name ID tiebreaking, and signature changes on rename. Run the focused Vitest file and confirm the current UUID ordering fails.

- [x] **Step 2: Implement canonical ordering**

Change `layoutGraph` and `graphSignature` to the name-first key. Update `LoreGraphPage` parallel-arc ordering to the content key. Keep the fixed physics iterations unchanged.

- [x] **Step 3: Add component/E2E proof**

Add a component test comparing node positions by visible name under different IDs. Add an E2E case that seeds two novels with identical names/prose in different creation order and compares node positions keyed by card text.

- [x] **Step 4: Restore the multi-node graph master**

Replace the one-node graph seed with the existing three-node/two-edge canon (`Mira`, `Kavic`, `Vulcan`). Update comments/captions. Run two independent captures and compare hashes; regenerate canonical `39`/`40` and the index.

- [x] **Step 5: Run focused gates**

Run: `pnpm --dir web test -- graphLayout` (or the repository's exact focused Vitest command), `just test-e2e-file app/capabilities/knowledge/e2e/test_graph_e2e.py`, both screenshot test files and `just check`.
Expected: PASS.

- [x] **Step 6: Review and commit**

Reviewer checks the ordering contract, duplicate/parallel-edge behavior and real multi-node frames. Commit `fix(knowledge): order graph layout by stable entity names` with `Closes #978`, a real `User-visible:` line and the Assisted-by trailer. Include regenerated masters in the same commit.

## Task 3: Remove setup and prompt content drift (#984, #986, #989)

**Files:**
- Modify: `app/capabilities/setup/web/i18n/{en,de,fr}.json:225`
- Modify: `app/capabilities/setup/web/WelcomePage.tsx:84`, `WizardHeader.tsx:89`
- Test: `app/capabilities/setup/web/WelcomePage.test.tsx`, a wizard header/step test
- Modify: `app/capabilities/writing/prompts.py:105-113`
- Test: `app/kernel/tests/test_prompts_smoke.py`, `app/capabilities/prompts/tests/test_prompts_api.py`, `test_prompts_preview_live.py`
- Modify: `app/kernel/interchange/demos/im-stillen-wald/metadata.json`
- Modify: `app/kernel/interchange/demos.py`, `scripts/generate_capabilities.py`
- Modify: `app/capabilities/setup/web/WelcomePage.tsx`, `steps/BasisStep.tsx`
- Test: `app/capabilities/setup/tests/test_demo_manifest.py`, `app/kernel/tests/test_interchange_demos.py`, setup E2E
- Regenerate: `web/lib/generated/demos.ts`, affected welcome/prompt masters and index

**Interfaces:**
- Catalog values become `Writing year {year}` / `Schreibjahr {year}` / `Année d'écriture {year}`; both callers pass `new Date().getFullYear()`.
- `sample_variables()` returns English/language-neutral values for all eight writing variables; marker structure and variable names stay unchanged.
- `DemoInfo` and generated demo metadata gain `title_en`/`titleEn`; English UI uses it for display only, while archive POST keeps the original archive title and language.

- [ ] **Step 1: Write failing tests**

Pin the English welcome year with `vi.setSystemTime(new Date("2026-06-01T00:00:00Z"))` and assert `Writing year 2026`; assert the wizard header uses the same key. Add a regression that writing sample values contain no German markers (`äöüß`, `Nebel`, `Wanderin`, `zögern`). Add an English welcome test expecting the localized `titleEn`, while the German face keeps the archive title and the POST still binds the original title.

- [ ] **Step 2: Implement the content fixes**

Use the existing localization/generation patterns. Do not hand-edit generated files without regenerating their source.

- [ ] **Step 3: Regenerate affected captures**

Run two independent captures and compare hashes. Regenerate `24-welcome-setup.png` and `30-prompts.png` if their pixels changed; regenerate the index.

- [ ] **Step 4: Run focused gates**

Run the setup, prompt and web test files touched, both screenshot test files and `just check`.
Expected: PASS.

- [ ] **Step 5: Review and commit**

Reviewer checks all three locales and generated-source consistency. Commit `fix(web): remove stale and mixed-language showcase content` with `Closes #984`, `Closes #986`, `Closes #989`, a real `User-visible:` line and the Assisted-by trailer.

## Task 4: Give settings subpages a route-aware breadcrumb (#981)

**Files:**
- Modify: `web/components/TopBar.tsx:302-306`
- Test: `web/components/TopBar.test.tsx:141-152,308-320`
- Modify: `web/components/TopBar.tsx:86`, `web/components/IconRail.tsx:593` for matching `aria-current`
- Regenerate `29-ai-rules.png`, `30-prompts.png` if pixels change

**Interfaces:**
- `settingsFace = !bookFace && pathname.startsWith("/settings")`; all three settings routes show `Atelier / Einstellungen` (or the active locale's Settings label), never the bookshelf crumb.

- [ ] **Step 1: Write failing component tests**

Assert the settings breadcrumb for hub, AI rules and prompts routes. Run the focused settings tests and confirm the two subpages fail.

- [ ] **Step 2: Implement route-aware crumbs**

Reuse the existing shell/breadcrumb abstraction; do not add a second navigation system.

- [ ] **Step 3: Regenerate captures and run gates**

Run two independent captures, regenerate `29`/`30` if changed, then run focused settings tests, both screenshot test files and `just check`.

- [ ] **Step 4: Review and commit**

Reviewer checks all settings routes and mobile/narrow behavior. Commit `fix(settings): show the settings location in subpage breadcrumbs` with `Closes #981`, a real `User-visible:` line and the Assisted-by trailer.

## Task 5: Decouple and harden screenshot publication (#983, #987, #988)

**Files:**
- Create: `scripts/screenshots_publish.py`
- Modify: `scripts/screenshots.py`
- Modify: `app/kernel/tests/test_screenshot_assets.py`
- Modify: `app/kernel/tests/test_screenshot_manifest.py` if wording constants move
- Modify: `.gitignore` for `assets/.screenshots-*` staging and backup directories

**Interfaces:**
- `publish(masters: Path, index: Path, staged_masters: Path, staged_index: Path) -> None` lives in `scripts/screenshots_publish.py`.
- Asset tests import `scripts.screenshots_publish`, not `scripts.screenshots`.
- `_write_index_temp`, `_move`, `_remove` and `_publish` move to the new module; monkeypatch targets follow it.
- Each output gets a backup root in its own parent before any index temp is staged. Same-filesystem swaps use `os.replace`; source and destination therefore stay on one device.
- Backups default to kept until a successful publish or confirmed complete restore. Errors name preserved backup paths; successful rollback removes backups only after both outputs are restored.
- Documentation tests use marker sets/structured assertions or centralized accepted-wording constants with rationale.
- README and collection disclosures derive from one structured source so a newly added stand-in surface cannot be omitted from one page.

- [ ] **Step 1: Write failing filesystem tests**

Add tests proving asset tests do not import Playwright, masters and index with injected different device IDs publish without a cross-device rename, index-swap failure restores both outputs, restore-abort/failure preserves the relevant backups, successful rollback removes backups only after both restores, backup-root failure leaks no staged index, and an index-temp write failure cleans up. Use temporary directories and injected move/swap/device seams; do not rely on timing or assume two temp roots are different filesystems.

- [ ] **Step 2: Extract publication helpers**

Move staging, backup, swap, rollback and cleanup into `scripts/screenshots_publish.py`. Keep capture/browser concerns in `scripts/screenshots.py`.

- [ ] **Step 3: Implement cross-filesystem publication**

Create one backup root beside each output before staging the index. Use `os.replace` only between paths on the same filesystem. Preserve backups until publication or restore is fully successful; never delete the last good copy on an aborted rollback. Ignore both `assets/.screenshots-backup-*` and `assets/.screenshots-<random>` staging directories.

- [ ] **Step 4: Replace literal-wording guards**

Replace the stale-settings literal with a scoped semantic check for settings text containing phase/roadmap/planned/not-yet language. Replace the Stitch paragraph's exact sentence with required marker sets (`design evidence`, `product captures`, `running application`) plus forbidden provenance/inversion markers. Derive the README disclosure from the same structured stand-in list as the collection index, and test that both contain every surface. Centralize only markers that genuinely carry meaning, with comments. Keep resolve-based link tests and image/caption equality strong.

- [ ] **Step 5: Run focused gates**

Run both screenshot test files and `just check`.
Expected: PASS.

- [ ] **Step 6: Review and commit**

Reviewer traces each failure path and confirms no Playwright import remains in the asset test. Commit `refactor(tooling): make screenshot publication filesystem-safe` with `Closes #983`, `Closes #987`, `Closes #988` and the Assisted-by trailer.

## Task 6: Harden screenshot workflow decisions and pending PRs (#982, #990)

**Files:**
- Create: `scripts/screenshots_decide.py`
- Create: `scripts/screenshots_pr.py`
- Modify: `.github/workflows/screenshots.yml`
- Create: `app/kernel/tests/test_screenshot_decide.py`
- Create: `app/kernel/tests/test_screenshot_pr.py`
- Modify: `CONTRIBUTING.md` only if behavior wording changes

**Interfaces:**
- `decide(event: str, before: str, sha: str, root: Path) -> tuple[bool, str]` runs git reads, consumes complete output without `grep -q`, and ignores merge-commit bodies for footer scanning.
- `pending_screenshot_pr(repository: str, token: str) -> int | None` queries open `chore/screenshots-*` PRs against `main`.
- The workflow writes `run=true|false` and the reason through the decide CLI, then defers when a screenshot update PR is already open.
- Existing manual/schedule/override behavior remains intact.

- [ ] **Step 1: Write failing decide and pending-PR tests**

Test `decide` against throwaway git repositories: docs-only push, UI push, manifest push, regenerate/skip footers on normal commits, hostile footer only in a merge commit/PR title, first push, schedule/manual, and a path list larger than 64 KiB. Test `pending_screenshot_pr` with a fake `gh` executable for no PR, one pending PR and multiple pending PRs.

- [ ] **Step 2: Implement robust decision logic**

Move the shell decision into `scripts/screenshots_decide.py`. Use full-consumption checks (no `grep -q` producer pipeline) and `git log --no-merges` so editable merge-commit/PR-title text cannot create a footer. Keep the workflow CLI/output contract.

- [ ] **Step 3: Defer duplicate pending updates**

Implement `scripts/screenshots_pr.py` and call it after a real staged diff is found but before branch creation. If a screenshot update PR is already open, log its number and exit successfully without creating another branch or PR. Do not force-update the existing branch.

- [ ] **Step 4: Run workflow and repository gates**

Run the focused decide and pending-PR tests, actionlint, zizmor, both screenshot test files and `just check`.
Expected: PASS.

- [ ] **Step 5: Review and commit**

Reviewer traces all cases against the real YAML and fake `gh` responses. Commit `ci(screenshots): make regeneration decisions robust` with `Closes #982`, `Closes #990` and the Assisted-by trailer.

## Task 7: Improve framing and remove unbuilt-copy focus (#979, #985)

**Files:**
- Modify: `app/capabilities/knowledge/web/i18n/{en,de,fr}.json:148` (`knowledge.dossiers.laterWaveNote`)
- Modify: `app/capabilities/writing/web/i18n/{en,de,fr}.json:138` (`writing.shelf.comingSoon`)
- Modify: `app/capabilities/planning/web/i18n/{en,de,fr}.json:143` (`planning.timeline.chapterSequenceNote`)
- Test: `DossiersPage.test.tsx`, `ShelfPage.test.tsx`, `ShelfBanner.test.tsx`, `TimelinePage.test.tsx`
- Modify: `scripts/screenshots.py` framing/scroll for `27`, `28`, `30`, `37`, `38`, `41`, `43`
- Regenerate affected masters and `docs/screenshots/README.md`

**Interfaces:**
- Placeholder copy becomes value-neutral, future-facing text in all three locales; no capture-state masking is allowed because these notes are data-independent.
- `30` shows the fifth prompt card without a sliver or intentionally captures the editor region.
- `28`/`37`/`38` do not crop meaningful content at the fold.
- `27`/`41`/`43` use the frame area intentionally rather than leaving a large empty lower half.
- The existing expanded stand-in disclosure remains unchanged and covered by its screenshot tests.

- [ ] **Step 1: Capture and inspect the affected frames**

Run a temporary capture and inspect `25`, `27`, `28`, `30`, `37`, `38`, `41`, `43`. Use the known seams: scroll `settings-page` until `#settings-daily-goal` is fully visible; scroll `main#main` until the last shelf card and subtitle are visible in both themes; scroll `prompts-page` until the fifth `prompt-card` is fully visible or intentionally show four complete cards plus the editor; extend causality to three chapters with one open gap; seed six placed timeline events plus three unordered notes; seed 6–9 storyboard chapters and open the first card so the drill-in shows real scenes.

- [ ] **Step 2: Write failing assertions where practical**

Pin source document/event/chapter counts, last-card and fifth-card bounding boxes inside the viewport, exactly one open causality gap, and the new copy in en/de/fr. For purely visual balance, require two-run hash equality plus reviewer visual inspection.

- [ ] **Step 3: Implement the smallest honest fix**

Adjust real seed counts/scroll/framing first. Change product copy only when no honest live capture state avoids the placeholder. No CSS masking, mocks or DB shortcuts.

- [ ] **Step 4: Regenerate and prove determinism**

Run two independent captures, compare hashes/index, regenerate canonical masters and index. Run both screenshot test files, any touched product tests and `just check`.

- [ ] **Step 5: Review and commit**

Reviewer inspects every affected PNG and the product copy. Commit `fix(web): remove placeholder focus from product captures` with `Closes #979`, `Closes #985`, a real `User-visible:` line and the Assisted-by trailer.

## Task 8: Final verification and close-out

- [ ] **Step 1: Run `just verify` on the final head**

Expected: PASS. Read the output; record current backend/web/E2E counts.

- [ ] **Step 2: Run actionlint and zizmor**

Expected: PASS with no new findings.

- [ ] **Step 3: Whole-branch review**

Dispatch a fresh reviewer on `zai-coding-plan/glm-5.4` over the complete branch from `12186926e`. Include this plan, the follow-up design and all closing commits.

- [ ] **Step 4: Close remaining issues**

Each fixing commit must carry its `Closes #...`. Remove `status: in-progress` from any issue that remains open after merge; no follow-up may remain open.

- [ ] **Step 5: Push and update PR #976**

PR body lists #977–#991 with closing commit SHAs, final gate output and the whole-branch verdict. Stop before merge and wait for owner approval.
