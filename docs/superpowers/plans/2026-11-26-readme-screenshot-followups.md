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
- Modify: `ROADMAP.md:86-89,103` for the Structure-phase review correction
- Test: `app/kernel/tests/test_screenshot_assets.py`
- Test: `app/kernel/tests/test_feature_inventory.py` for the Structure-phase regression

**Interfaces:**
- Produces no runtime interface.
- Adds `test_all_relative_stitch_markdown_links_resolve` or equivalent in the existing screenshot asset test module.

- [x] **Step 1: Add a failing link-resolution test**

Parse every relative Markdown link in `docs/design/stitch/README.md`; resolve it against the file's parent and assert the target exists. Exclude anchors and absolute URLs. Run `just test-file app/kernel/tests/test_screenshot_assets.py` and confirm the two `../superpowers/specs/...` links fail.

- [x] **Step 2: Correct the links and inventory state**

Change the two links to `../../superpowers/specs/...`. Change `Structure view (PLAN-003)` from `live` to `backend` and from Phase 0 to Phase 1: the API remains, but the missing productive surface belongs to the unfinished rebuild phase. Correct the AI-continuation inventory wording at line 64 from "at the caret" to "below the prose", matching the product and README.

- [x] **Step 3: Run the focused tests**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: PASS.

- [x] **Step 4: Review and commit**

Reviewer verifies the route/API evidence and link targets. Commit `docs(readme): correct the feature inventory and Stitch spec links` with `Closes #977`, `Closes #980`, a real `User-visible:` line and the Assisted-by trailer.

- [x] **Step 5: Close the Structure-phase review finding**

Add a failing structured inventory test for the Structure view's `backend | 1` row and its placement in the Roadmap's Phase 1 section. Change the row's phase to `1`; change the Roadmap's “two loose doors” to “three loose doors”, describe the Structure view as an existing API with no surface/E2E leg, and update the exit sentence to “three loose doors”. Run `just test-file app/kernel/tests/test_feature_inventory.py` and `just check`. Reviewer verifies the Inventory legend, Roadmap phase boundaries and no new surface claim. Commit `chore(docs): assign the missing structure view to phase one` with the Assisted-by trailer. No E2E leg is required for this documentation-only correction.

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
- Modify: `app/capabilities/setup/web/steps/StructureStep.tsx`, `steps/ProvisioningStep.tsx`, `web/wizardState.ts` for complete English display coverage
- Modify: `app/kernel/interchange/format.py` docstring and `docs/superpowers/specs/2026-10-28-wp3-markdown-demo-export-design.md` for the display-only metadata contract
- Test: `app/capabilities/setup/tests/test_demo_manifest.py`, `app/kernel/tests/test_interchange_demos.py`, `app/kernel/tests/test_interchange_format.py`, setup E2E
- Regenerate: `web/lib/generated/demos.ts`, affected welcome/prompt masters and index

**Interfaces:**
- Catalog values become `Writing year {year}` / `Schreibjahr {year}` / `Année d'écriture {year}`; both callers pass `new Date().getFullYear()`.
- `sample_variables()` returns English/language-neutral values for all eight writing variables; marker structure and variable names stay unchanged.
- `DemoInfo` and generated demo metadata gain `title_en`/`titleEn`; English UI uses it for display only, while archive POST keeps the original archive title and language.

- [x] **Step 1: Write failing tests**

Pin the English welcome year with `vi.setSystemTime(new Date("2026-06-01T00:00:00Z"))` and assert `Writing year 2026`; assert the wizard header uses the same key. Add a regression that writing sample values contain no German markers (`äöüß`, `Nebel`, `Wanderin`, `zögern`). Add an English welcome test expecting the localized `titleEn`, while the German face keeps the archive title and the POST still binds the original title.

- [x] **Step 2: Implement the content fixes**

Use the existing localization/generation patterns. Do not hand-edit generated files without regenerating their source.

- [x] **Step 3: Regenerate affected captures**

Run two independent captures and compare hashes. Regenerate `24-welcome-setup.png` and `30-prompts.png` if their pixels changed; regenerate the index.

- [x] **Step 4: Run focused gates**

Run the setup, prompt and web test files touched, both screenshot test files and `just check`.
Expected: PASS.

- [x] **Step 5: Review and commit**

Reviewer checks all three locales and generated-source consistency. Commit `fix(web): remove stale and mixed-language showcase content` with `Closes #984`, `Closes #986`, `Closes #989`, a real `User-visible:` line and the Assisted-by trailer.

- [x] **Step 6: Close the setup-title review findings**

Add failing English-face assertions for the Structure and Provisioning display sites and a Python test for present-but-empty `title_en` fallback. Use `demoDisplayTitle(demo, locale)` at every display site while keeping the provisioning POST on `archive.title`; type the helper locale as `Locale`; use `metadata.get("title_en") or title`; document `title_en` as optional display-only metadata that is not imported into the novel. Run the setup/interchange tests, existing setup E2E, screenshot suites and `just check`. Run one fresh full capture and prove the committed masters/index remain identical. Commit `fix(setup): keep the localized demo title through provisioning` with the Assisted-by trailer and no duplicate `Closes` keywords.

- [x] **Step 7: Keep malformed display metadata from blocking archive imports**

Add a failing parametrized format test for `title_en` values `42`, `true`, `[1, 2]`, `{"x": 1}` and `"x" * 201`: parsing must succeed, novel title/chapters/entities remain intact, non-string values read as `None`, and the overlong string is preserved rather than refused. Replace the strict `title_en` parse with a lenient string-or-`None` read and remove its `_MAX_LENGTHS` cap; keep all persisted metadata strict. Document the compatibility rule in `format.py` and the WP3 demo/export spec. Run the interchange format/engine/demo tests, setup tests and `just check`. Commit `fix(interchange): ignore unusable display titles during import` with a real `User-visible:` line, the Assisted-by trailer and no duplicate `Closes` keywords.

- [x] **Step 8: Localize every registered prompt sample (#986)**

Write a registry-wide regression that flattens every registered factory's sample values and rejects the remaining German tokens. Translate the chat question/passage/interview transcript/roster and the knowledge extraction/consistency samples to English or language-neutral values without changing keys, marker lines or variable structure. Update all goldens and live-preview assertions, including the fake-embedding passage token. Run prompt/knowledge/chat tests, prompt API/live tests, screenshot suites and `just check`; run two independent captures and regenerate only `30-prompts.png` if changed. Commit `fix(prompts): localize every bundled sample` with a real `User-visible:` line and the Assisted-by trailer; do not repeat `Closes #986`.

## Task 4: Give settings subpages a route-aware breadcrumb (#981)

**Files:**
- Modify: `web/components/TopBar.tsx:302-306`
- Test: `web/components/TopBar.test.tsx:141-152,308-320`
- Modify: `web/components/TopBar.tsx:86`, `web/components/IconRail.tsx:186,593` for matching `aria-current`
- Test: `app/capabilities/settings/e2e/test_ai_rules_e2e.py` for the direct-subroute breadcrumb
- Regenerate `29-ai-rules.png`, `30-prompts.png` if pixels change

**Interfaces:**
- `settingsFace = !bookFace && pathname.startsWith("/settings")`; all three settings routes show `Atelier / Einstellungen` (or the active locale's Settings label), never the bookshelf crumb.

- [x] **Step 1: Write failing component tests**

Assert the settings breadcrumb for hub, AI rules and prompts routes. Run the focused settings tests and confirm the two subpages fail.

- [x] **Step 2: Implement route-aware crumbs**

Reuse the existing shell/breadcrumb abstraction; do not add a second navigation system.

- [x] **Step 3: Regenerate captures and run gates**

Run two independent captures, regenerate `29`/`30` if changed, then run focused settings tests, both screenshot test files and `just check`.

- [x] **Step 4: Review and commit**

Reviewer checks all settings routes and mobile/narrow behavior. Commit `fix(settings): show the settings location in subpage breadcrumbs` with `Closes #981`, a real `User-visible:` line and the Assisted-by trailer.

- [x] **Step 5: Close the E2E and rail-consistency review findings**

Run the existing settings, AI-rules and prompts E2E legs. In `test_ai_rules_e2e.py`, assert the direct subroute's topbar shows Atelier / Einstellungen and not the bookshelf crumb. Replace IconRail's parsed-pathname `settingsActive` with the component's established route-ID selector, enumerating `/settings`, `/settings/ai-regeln` and `/settings/prompts`; leave TopBar's approved pathname predicate unchanged. Run focused TopBar/IconRail tests, the three E2E legs, both screenshot test files and `just check`. Prove one fresh capture remains identical because this is behavior-preserving on canonical pixels. Commit `refactor(settings): keep rail area matching on route ids` with the Assisted-by trailer and no duplicate `Closes` keyword.

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

- [x] **Step 1: Write failing filesystem tests**

Add tests proving asset tests do not import Playwright, masters and index with injected different device IDs publish without a cross-device rename, index-swap failure restores both outputs, restore-abort/failure preserves the relevant backups, successful rollback removes backups only after both restores, backup-root failure leaks no staged index, and an index-temp write failure cleans up. Use temporary directories and injected move/swap/device seams; do not rely on timing or assume two temp roots are different filesystems.

- [x] **Step 2: Extract publication helpers**

Move staging, backup, swap, rollback and cleanup into `scripts/screenshots_publish.py`. Keep capture/browser concerns in `scripts/screenshots.py`.

- [x] **Step 3: Implement cross-filesystem publication**

Create one backup root beside each output before staging the index. Use `os.replace` only between paths on the same filesystem. Preserve backups until publication or restore is fully successful; never delete the last good copy on an aborted rollback. Ignore both `assets/.screenshots-backup-*` and `assets/.screenshots-<random>` staging directories.

- [x] **Step 4: Replace literal-wording guards**

Replace the stale-settings literal with a scoped semantic check for settings text containing phase/roadmap/planned/not-yet language. Replace the Stitch paragraph's exact sentence with required marker sets (`design evidence`, `product captures`, `running application`) plus forbidden provenance/inversion markers. Derive the README disclosure from the same structured stand-in list as the collection index, and test that both contain every surface. Centralize only markers that genuinely carry meaning, with comments. Keep resolve-based link tests and image/caption equality strong.

- [x] **Step 5: Run focused gates**

Run both screenshot test files and `just check`.
Expected: PASS.

- [x] **Step 6: Review and commit**

Reviewer traces each failure path and confirms no Playwright import remains in the asset test. Commit `refactor(tooling): make screenshot publication filesystem-safe` with `Closes #983`, `Closes #987`, `Closes #988` and the Assisted-by trailer.

- [x] **Step 7: Close the publication recovery review findings**

Ignore `docs/screenshots/.README.md-backup-*` beside the existing assets recovery ignore, and document that custom output parents are outside repository ignore coverage. Preflight that an existing output shares its parent's device; fail with a clear error before creating backups or moving data when a mount point breaks that assumption. Make index-temp unlink best-effort so cleanup failure cannot replace the publication/rollback error or skip the remaining recovery cleanup. Let `KeyboardInterrupt` propagate instead of recording it as an ordinary step failure, while preserving recovery roots. Remove the tautological derived-disclosure equality assertion and retain the meaningful surface/frame tests. Add deterministic tests for a successful cross-device copy followed by index-swap failure, target/parent device mismatch before mutation, temp-unlink failure preserving the primary error, and interrupt propagation. Clarify that a named recovery root may be empty after a successful restore. Run both screenshot test files and `just check`. Commit `fix(tooling): harden screenshot publication recovery` with the Assisted-by trailer and no duplicate `Closes` keywords.

- [x] **Step 8: Close the final publication, disclosure and guard findings**

Replace rollback's `moved_*` flags with filesystem-state evidence: restore whenever the backup payload exists, remove a new output only when no old output existed, and keep backups unless every recovery step succeeds. Add deterministic tests for interrupts after the masters and index renames but before control returns, plus a move that fails before renaming. Widen the structured stand-in disclosure to knowledge-dock frame 36 and both graph frames 39/40, regenerate the collection index and README disclosure, and assert every extraction frame is named. Apply `_FUTURE_WORK` to every README prose section except the Documentation link list, stripping image tags and inline links; add stale-claim regressions for Getting started and Status plus false-positive guards for image alt text and link labels. Correct the report's index-temp ignore wording. Run both screenshot test files and `just check`. Commit `refactor(tooling): preserve outputs across publication interrupts` with the Assisted-by trailer and no duplicate `Closes` keywords.

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
- The workflow writes `run=true|false` and the reason through the decide CLI, validates the pending lookup's exact `pending=none|pending=<number>` sentinel, then defers when a screenshot update PR is already open. A malformed lookup fails visibly instead of silently skipping publication.
- Existing manual/schedule/override behavior remains intact.

- [x] **Step 1: Write failing decide and pending-PR tests**

Test `decide` against throwaway git repositories: docs-only push, UI push, manifest push, regenerate/skip footers on normal commits, hostile footer only in a merge commit/PR title, first push, schedule/manual, and a path list larger than 64 KiB. Test `pending_screenshot_pr` with a fake `gh` executable for no PR, one pending PR and multiple pending PRs.

- [x] **Step 2: Implement robust decision logic**

Move the shell decision into `scripts/screenshots_decide.py`. Use full-consumption checks (no `grep -q` producer pipeline) and `git log --no-merges` so editable merge-commit/PR-title text cannot create a footer. Keep the workflow CLI/output contract.

- [x] **Step 3: Defer duplicate pending updates**

Implement `scripts/screenshots_pr.py` and call it after a real staged diff is found but before branch creation. If a screenshot update PR is already open, log its number and exit successfully without creating another branch or PR. Do not force-update the existing branch.

- [x] **Step 4: Run workflow and repository gates**

Run the focused decide and pending-PR tests, actionlint, zizmor, both screenshot test files and `just check`.
Expected: PASS.

- [x] **Step 5: Review and commit**

Reviewer traces all cases against the real YAML and fake `gh` responses. Commit `ci(screenshots): make regeneration decisions robust` with `Closes #982`, `Closes #990` and the Assisted-by trailer.

- [x] **Step 6: Close the workflow review findings**

Add a real publish-step test for `pending=none` that proves publication proceeds. Validate the lookup output in YAML with an exact `pending=none` or `pending=<digits>` case; empty, warning or malformed output must fail before branch creation. Correct the module docstring and contributor/report wording: deferral deliberately leaves an existing PR untouched, but that PR may be stale after newer UI changes and a human must close or replace it when the new diff matters. Correct the report's test counts to 20 decide + 4 PR and describe the fake-gh argv assertion precisely. Run focused tests, actionlint, zizmor, both screenshot suites and `just check`. Commit `ci(screenshots): validate pending update lookup output` with the Assisted-by trailer and no duplicate `Closes` keywords.

## Task 7: Improve framing and remove unbuilt-copy focus (#979, #985)

**Files:**
- Modify: `app/capabilities/knowledge/web/i18n/{en,de,fr}.json` (`knowledge.dossiers.laterWaveNote`, `knowledge.dossier.jumpNote`)
- Modify: `app/capabilities/writing/web/i18n/{en,de,fr}.json:138` (`writing.shelf.comingSoon`)
- Modify: `app/capabilities/planning/web/i18n/{en,de,fr}.json` (`planning.timeline.chapterSequenceNote`, `planning.causality.laterNote`)
- Modify: `app/capabilities/planning/web/CausalityPage.tsx:415` to distribute existing content over the available page height
- Test: `DossiersPage.test.tsx`, `ShelfPage.test.tsx`, `ShelfBanner.test.tsx`, `TimelinePage.test.tsx`, `CausalityPage.test.tsx`
- Modify: `scripts/screenshots.py` framing/scroll for `27`, `28`, `30`, `37`, `38`, `41`, `43`
- Regenerate affected masters and `docs/screenshots/README.md`

**Interfaces:**
- Placeholder copy becomes value-neutral, future-facing text in all three locales; no capture-state masking is allowed because these notes are data-independent.
- `30` shows the fifth prompt card without a sliver or intentionally captures the editor region.
- `28`/`37`/`38` do not crop meaningful content at the fold.
- `27`/`41`/`43` use the frame area intentionally rather than leaving a large empty lower half. Causality groups its existing blocks into top, track and methodology/footnote sections, leaving one intentional vertical gap; it does not invent scenes, add a surface or mechanically separate every block.
- `37`/`38` prioritize the complete last shelf card and subtitle. The page H1 may scroll above the fixed top bar because the plan does not require it in-frame; this is an explicit framing trade-off, not cropped card content.
- The existing expanded stand-in disclosure remains unchanged and covered by its screenshot tests.

- [x] **Step 1: Capture and inspect the affected frames**

Run a temporary capture and inspect `25`, `27`, `28`, `30`, `37`, `38`, `41`, `43`. Use the known seams: scroll `settings-page` until `#settings-daily-goal` is fully visible; scroll `main#main` until the last shelf card and subtitle are visible in both themes; scroll `prompts-page` until the fifth `prompt-card` is fully visible or intentionally show four complete cards plus the editor; extend causality to three chapters with one open gap; seed six placed timeline events plus three unordered notes; seed 6–9 storyboard chapters and open the first card so the drill-in shows real scenes.

- [x] **Step 2: Write failing assertions where practical**

Pin source document/event/chapter counts, last-card and fifth-card bounding boxes inside the viewport, exactly one open causality gap, and the new copy in en/de/fr. For purely visual balance, require two-run hash equality plus reviewer visual inspection.

- [x] **Step 3: Implement the smallest honest fix**

Adjust real seed counts/scroll/framing first. Change product copy only when no honest live capture state avoids the placeholder. No CSS masking, mocks or DB shortcuts.

- [x] **Step 4: Regenerate and prove determinism**

Run two independent captures, compare hashes/index, regenerate canonical masters and index. Run both screenshot test files, any touched product tests and `just check`.

- [x] **Step 5: Review and commit**

Reviewer inspects every affected PNG and the product copy. Commit `fix(web): remove placeholder focus from product captures` with `Closes #979`, `Closes #985`, a real `User-visible:` line and the Assisted-by trailer.

- [x] **Step 6: Close the visual-review findings**

Regroup the existing causality blocks into three visual groups: top subline, header+track, and methodology+footnote. Use a `min-h-full` column with a flexible middle group so frame 27 leaves one intentional vertical gap instead of four stretched voids; keep overflow safe and add geometry assertions for the small intra-group gaps. Correct the French causality term from “bande” to the catalog's established “barre” and update its test. Update the stale German manuscript-note assertion in `test_graph_e2e.py` and run that graph E2E leg. Replace the remaining dossier manuscript-excerpts note (`knowledge.dossier.jumpNote`) with value-neutral future-facing copy in en/de/fr and extend the dossier copy test; correct the report from four gap areas to three plus the separate excerpt note. Make `_require_inside` assert both horizontal and vertical bounds and derive the viewport height from the single viewport definition. Keep the shelf's H1 trade-off explicit; do not tighten product spacing merely to add a heading the plan does not require. Run the touched product tests, causality, graph and dossier E2E, both screenshot suites, `just check` and `just check-generated`; run two independent full captures, inspect 25/27/37/38 and prove the new publication path leaves no debris. Commit `fix(planning): use the causality page height` with a real `User-visible:` line and the Assisted-by trailer; do not repeat `Closes #979`/`Closes #985`, which already belong to `9596c2e89`.

- [x] **Step 7: Make all disabled-feature copy status-honest (#979)**

Replace the six remaining future-promise keys with status-only copy in en/de/fr: `setup.welcome.comingSoon`, `knowledge.sources.laterNote`, `knowledge.sources.viewNote`, `knowledge.dossiers.laterWaveNote`, `knowledge.dossier.excerptsGap`, and `knowledge.dossier.jumpNote`. Use `Not available yet.` / `Noch nicht verfügbar.` / `Pas encore disponible.`. Add catalog contracts for setup and Sources, retarget dossier/capture assertions, and update every listed unit/E2E literal. Run touched setup/knowledge tests, setup/Sources/dossier/graph E2E, both screenshot suites, `just check` and `just check-generated`. After Task 5's disclosure update lands, run two independent full captures, regenerate 24/25/26/39/40, inspect them, and prove publication leaves no debris. Commit `fix(web): label disabled features without future promises` with a real `User-visible:` line and the Assisted-by trailer; do not repeat `Closes #979`/`Closes #985`.

- [x] **Step 8: Finish the disabled-only copy policy**

Convert the nine remaining disabled-only future-promise keys to the same canonical status copy in en/de/fr: `planning.timeline.chapterSequenceNote`, `knowledge.dossier.bookmarkNote`, `knowledge.dossier.exportNote`, `writing.workspace.promptBar.styleNote`, `writing.workspace.zen.soundscapeNote`, `writing.workspace.ribbon.historyNote`, `writing.workspace.ribbon.exportNote`, `writing.workspace.dock.layoutNote`, and `writing.workspace.dock.soon`. Keep `writing.shelf.comingSoon` as the documented shared-live-CTA exception. Update Timeline, ZenMode, EditorColumn, PromptBar, InspectorDock and EntityDossier contracts; update writing Zen/workspace E2E; scope the dossier and graph E2E excerpts assertions to the excerpts heading block; add capture assertions for the painted timeline note and dock badge. Run all touched unit/E2E suites, both screenshot test files, `just check` and `just check-generated`. Run two independent full captures, regenerate and inspect 20/21/35/41/42, prove the full set remains deterministic and publication leaves no debris. Commit `fix(web): finish disabled feature status copy` with a real `User-visible:` line and the Assisted-by trailer; do not repeat `Closes #979`/`Closes #985`.

- [x] **Step 9: Close the shelf-banner copy exception**

Add `writing.shelf.banner.statsNote` with the canonical status copy in en/de/fr and use it for the disabled-only statistics button in `ShelfBanner.tsx`; keep `writing.shelf.comingSoon` only where it is shared with a live CTA. Add exact-locale and forbidden-future-promise contracts in `ShelfBanner.test.tsx`. Run shelf tests, both screenshot suites, `just check` and `just check-generated`; run two independent captures and regenerate 37/38 only if the banner note is in-frame. Commit `fix(writing): give the shelf banner status-only copy` with a real `User-visible:` line and the Assisted-by trailer; do not repeat `Closes #979`/`Closes #985`.

## Task 8: Final verification and close-out

- [x] **Step 0: Close the whole-branch review findings**

Complete Task 3 Step 8, Task 5 Step 8 and Task 7 Step 7; re-review each fix round. Record that pushed `3689a5fb1 fix(tooling)` must be dropped from the release-please entry because history cannot be rewritten. Correct the Task 5 report's index-temp ignore wording. Only then run Steps 1–5 on the new final head.

- [x] **Step 1: Run `just verify` on the final head**

Expected: PASS. Read the output; record current backend/web/E2E counts.

- [x] **Step 2: Run actionlint and zizmor**

Expected: PASS with no new findings.

- [x] **Step 3: Whole-branch review**

Dispatch a fresh reviewer on `zai-coding-plan/glm-5.4` over the complete branch from `12186926e`. Include this plan, the follow-up design and all closing commits.

- [ ] **Step 4: Close remaining issues**

Each fixing commit must carry its `Closes #...`. Remove `status: in-progress` from any issue that remains open after merge; no follow-up may remain open.

- [x] **Step 5: Push and update PR #976**

PR body lists #977–#991 with closing commit SHAs, final gate output and the whole-branch verdict. Stop before merge and wait for owner approval.
