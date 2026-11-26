# README and Screenshot Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the current post-W9 `main`, repair and extend the real-stack screenshot capture, publish a focused README plus a complete screenshot collection, and re-enable automatic regeneration without a feedback loop.

**Architecture:** `assets/screenshots/` remains the only PNG master source. A small manifest module owns shot names, captions, grouping and the curated README selection; `scripts/screenshots.py` drives the real UI and writes both the PNGs and `docs/screenshots/README.md`. The README embeds only the curated subset. The workflow stays advisory, runs manually/weekly/on relevant `main` pushes, and never treats its own output as a reason to regenerate.

**Tech Stack:** Python 3.14, Playwright, pytest, PIL, GitHub Actions, actionlint, zizmor, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-26-readme-screenshots-design.md`; prior README constraints in `docs/superpowers/specs/2026-10-31-readme-showcase-design.md`; W4 fidelity requirement in `docs/superpowers/specs/2026-11-16-frontend-rebuild-w4-design.md`; W9 cut 1 in `docs/superpowers/specs/2026-11-20-assistant-sessions-design.md`; issues #903 and #848.

## Current Baseline — 2026-11-26

- `main` is `12186926e46932dfd01759f5777d780687052f9b`, clean and equal to `narrare/main`.
- W9 is complete: #956 (`38e1e58a4`), #973 (`61f715fae`) and #974 (`53f462cd5`) are merged; the wave record, index #975, follow-ups row, roadmap and feature inventory are present. #975 stays open for #966/#969; that is not unfinished W9 scope.
- The update check from #965 (`865db07f0`) is live but absent from `ROADMAP.md`, `docs/features/INDEX.md` and `README.md`, and has open follow-ups #959–#964. It is deliberately outside this plan's claims and frames until that inventory catches up.
- #903 and #848 are open, unassigned and carry no `status: in-progress` label. No competing screenshot PR is open; #794 is release-only.

## Design Decisions

- **README scope:** focused product overview, not a complete gallery. It shows the writing workspace, Zen, knowledge, planning, settings/prompts and the W9 interview.
- **Full collection:** additional live surfaces remain available in `assets/screenshots/` and are indexed by a new `docs/screenshots/README.md`.
- **One source:** no duplicate `gallery/` or `showcase/` PNG tree. The README and the overview both reference `assets/screenshots/`.
- **Live gate:** W9 is complete. Implementation may start after owner approval, but the workflow live switch remains the final task and waits for the capture, README and full-branch gates.
- **Update-check boundary:** do not add an update banner, release-notes modal, update-settings frame or README claim in this change. Revisit after the product inventory includes #965 and its open follow-ups are settled.
- **Rejected alternatives:** a trigger-only fix leaves #903 open; putting every image in the README makes it noisy; copying images into a second folder creates drift.

## Global Constraints

- W9 is complete at the recorded baseline. Task 0 revalidates that evidence and the current `main` SHA before any dispatch; if `main` moved, re-check the screenshot seam rather than trusting stale line numbers.
- No product route, API, schema, migration or application behavior changes.
- Frames are 1600×1000, device scale 1, `en-US`, light by default; dark frames are explicit pairs. Every PNG is below 1 MB and has descriptive alt text where embedded.
- Materially changed images get new stable filenames; do not overwrite an old name with different pixels.
- Capture uses the real stack, API seeding and the fake provider at the test boundary. No production fake, DB shortcut or mocked screenshot surface.
- Two consecutive captures must produce identical PNG hashes and identical generated index Markdown. Pin the browser clock and remove random/time-dependent pixels.
- The workflow remains non-required. Schedule is Sunday 06:00 UTC; push is `main` only. Generated assets, README and `docs/screenshots/**` are not UI-change triggers. Reuse the existing `just screenshots` recipe; add no new `just` command.
- Conventional commits; `docs` commits need a real `User-visible:` line; every agent commit ends with `Assisted-by: OpenCode (<model>)`. Nothing is committed before its review is green.
- Every dispatch names its implementer and reviewer models explicitly. The coordinator chooses both at dispatch time from the local assignment; no concrete model pins belong in this plan or shared project instructions.
- This plan supersedes `~/.opencode/plan/screenshots-re-enable.md`.

## Review Focus

1. **The baseline moves before execution** — Task 0 records the current SHA and rechecks issue state, W9 evidence and seam files; stale line numbers are not treated as authority.
2. **Capture drifts again** — use the same stable test IDs and route helpers as the capability E2E tests; a missing selector must fail at its source with a named error.
3. **Pixels are nondeterministic** — the two-run hash comparison must cover every PNG and the generated index, including relative-time labels, animations and the update-check shell state.
4. **README claims outrun the product** — every claim is checked against `docs/features/INDEX.md`; Stitch drafts, designed-only surfaces and the not-yet-inventoried update check are excluded.
5. **Workflow creates noise or a loop** — bot output is excluded from the UI regex, bot commits carry no regenerate override, the bot branch is not `main`, and no-diff runs open no PR. Image paths, dimensions, sizes and alt text are pinned by tests.

---

## File Structure

- Create `scripts/screenshot_manifest.py` — pure shot metadata, validation and overview rendering.
- Create `app/kernel/tests/test_screenshot_manifest.py` — manifest and rendered-index contract tests; runs inside `just test`.
- Modify `scripts/screenshots.py` — real-stack capture, repaired selectors, new faces, index writing.
- Create `app/kernel/tests/test_screenshot_assets.py` — PNG and README image-reference contract; runs inside `just test`.
- Create `docs/screenshots/README.md` — generated full collection index.
- Modify `docs/README.md` — link to the screenshot collection.
- Modify `docs/design/stitch/README.md` — point to the canonical collection instead of duplicating its file list.
- Modify `README.md` — focused product narrative, curated frames, current settings/prompts/W9 claims.
- Modify `.github/workflows/screenshots.yml` — live triggers, consistent prose, generated-index staging, loop guards.
- Modify `CONTRIBUTING.md` — current capture/workflow instructions.
- Generate `assets/screenshots/*.png` — canonical masters, including the audited legacy set and new W4–W9 faces.

## Task 0: Revalidate the baseline and claim the follow-ups

**Files:** read-only W9 plan/spec/ledger, `ROADMAP.md`, `docs/features/INDEX.md`, `docs/superpowers/follow-ups.md`, screenshot seam files.

- [x] **Step 1: W9 completion verified at the planning baseline**

#956 (`38e1e58a4`), #973 (`61f715fae`) and #974 (`53f462cd5`) are merged. `docs/superpowers/follow-ups.md:42` and the W9 gap ledger record the wave; `ROADMAP.md` and `docs/features/INDEX.md` mark create/interview live. #975 remains open only for #966/#969.

- [x] **Step 2: Revalidate immediately before dispatch**

Run `git fetch narrare`, record `git rev-parse narrare/main`, and confirm a clean worktree. Re-read #903/#848 state, labels and assignees; both must still be open and unclaimed. Re-check `scripts/screenshots.py`, `.github/workflows/screenshots.yml`, `README.md`, `CONTRIBUTING.md`, `docs/design/stitch/README.md` and the four planned new files. If the SHA or seam changed, update this plan before Task 1.

- [x] **Step 3: Confirm the update-check boundary**

Confirm #965 remains outside `ROADMAP.md`, `docs/features/INDEX.md` and the README, or explicitly revise this plan with the owner before adding any update-check frame or claim. Normal captures must keep `NARRE_UPDATE_CHECK_URL=off`.

- [x] **Step 4: Claim both issues**

```bash
gh issue edit 903 --add-label "status: in-progress" --add-assignee jmerifjKriwe
gh issue edit 848 --add-label "status: in-progress" --add-assignee jmerifjKriwe
```

- [x] **Step 5: Start from current `main` in an isolated worktree**

Use the `using-git-worktrees` skill. Branch from the freshly fetched `narrare/main`; the planning checkout was current at `12186926e`, but execution must not assume that SHA is still head.

## Task 1: Add the screenshot manifest and its contract tests

**Files:**
- Create: `scripts/screenshot_manifest.py`
- Test: `app/kernel/tests/test_screenshot_manifest.py`

**Interfaces:**
- Produces `Shot(name: str, title: str, caption: str, group: str, theme: Literal["light", "dark"], readme: bool = False)`.
- Produces `SHOTS: tuple[Shot, ...]`, `README_SHOTS: tuple[Shot, ...]`, `validate_shots(shots: Sequence[Shot]) -> None`, `render_index(shots: Sequence[Shot]) -> str`.
- Shot filename is always `{name}.png`; overview links are always `../../assets/screenshots/{name}.png`.

- [x] **Step 1: Write failing manifest tests**

Pin these assertions in `test_screenshot_manifest.py`:

```python
def test_shot_names_are_unique_and_safe() -> None:
    validate_shots(SHOTS)
    names = [shot.name for shot in SHOTS]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"\d{2}-[a-z0-9-]+", name) for name in names)


def test_required_surfaces_and_readme_selection_exist() -> None:
    required = {
        "20-workspace-rebuilt", "21-workspace-rebuilt-dark",
        "22-zen", "23-zen-dark", "24-welcome-setup", "25-dossiers",
        "26-sources", "27-causality", "28-settings-hub", "29-ai-rules",
        "30-prompts", "31-entity-create", "32-entity-create-dark",
        "33-entity-interview", "34-entity-interview-dark",
    }
    assert required <= {shot.name for shot in SHOTS}
    assert tuple(shot.name for shot in README_SHOTS) == (
        "20-workspace-rebuilt", "21-workspace-rebuilt-dark", "22-zen",
        "25-dossiers", "27-causality", "28-settings-hub", "30-prompts",
        "33-entity-interview",
    )
    assert not any(shot.name.startswith("update-") for shot in SHOTS)


def test_index_links_every_master_once() -> None:
    rendered = render_index(SHOTS)
    for shot in SHOTS:
        assert rendered.count(f"../../assets/screenshots/{shot.name}.png") == 1
    assert "/home/" not in rendered
    assert "assets/screenshots/" in rendered
```

- [x] **Step 2: Run the tests and verify failure**

Run: `just test-file app/kernel/tests/test_screenshot_manifest.py`
Expected: FAIL because `scripts.screenshot_manifest` does not exist.

- [x] **Step 3: Implement the manifest**

Seed the manifest with the existing 01–19 names as provisional entries; Task 2 owns the keep/rename/remove audit. Add the required 20–34 faces with concise English titles/captions and groups `Writing`, `Knowledge`, `Planning`, `Settings`, `Assistant`. Mark exactly the eight README shots above. `render_index` emits a short introduction, grouped headings and one relative image link per shot. It must not embed binary data or absolute paths.

- [x] **Step 4: Run the tests**

Run: `just test-file app/kernel/tests/test_screenshot_manifest.py`
Expected: PASS.

- [x] **Step 5: Review, then commit**

Reviewer checks names, grouping, captions and the curated selection. Then commit `chore(tooling): add the screenshot manifest and overview contract` with the required trailer.

## Task 2: Repair the capture recipe and publish a valid master set

**Files:**
- Modify: `scripts/screenshots.py`
- Modify: `scripts/screenshot_manifest.py` if the legacy audit renames or removes a shot
- Create: `app/kernel/tests/test_screenshot_assets.py`
- Generate: `assets/screenshots/*.png`
- Create: `docs/screenshots/README.md`
- Modify: `README.md` only where the legacy audit changes an existing image path

**Interfaces:**
- Consumes `SHOTS` from `scripts.screenshot_manifest`.
- Keeps `capture(out: Path) -> list[Path]`.
- Produces `_shot(page: Page, out: Path, name: str) -> Path`, `_set_theme(page: Page, theme: Literal["light", "dark"]) -> None`, `_open_workspace(page: Page, novel_id: str) -> None`.
- CLI adds `--index PATH`; default is `docs/screenshots/README.md`. `--out` remains `assets/screenshots`.

- [ ] **Step 1: Replace the stale workspace selector**

At `scripts/screenshots.py:406-408`, stop looking for a `complementary` named `Chapters`. Use the same `get_by_test_id("explorer-tree")` contract and `_goto_workspace` path as `app/capabilities/writing/e2e/test_workspace_e2e.py:77-83`. Raise a named error if the explorer is absent; do not wait 30 seconds on a role label that no longer exists.

- [ ] **Step 2: Audit the legacy 01–19 frame names**

With the workspace entry repaired, drive each existing surface once and compare it with its committed PNG. Keep a name only when the surface and pixels are materially unchanged; rename a materially changed frame and remove a dead surface. Update `SHOTS` and record the README path changes that must land with the renamed/generated assets. Never overwrite an old filename with different pixels merely because the capture script already uses that name.

- [ ] **Step 3: Add the W4 workspace and Zen pair**

Capture `20-workspace-rebuilt` and `21-workspace-rebuilt-dark` from the rebuilt scene-centric workspace, and `22-zen`/`23-zen-dark` through `_enter_zen` in `app/capabilities/writing/e2e/test_zen_e2e.py:86-92` (`zen-mode`, F9, Escape/F9 back). These new names prevent GitHub's image cache from serving the pre-W4 workspace/Zen pixels.

- [ ] **Step 4: Add the missing live knowledge/planning/settings faces**

Capture `24-welcome-setup` at `/setup`; `25-dossiers` at `/novels/{id}/knowledge/dossiers` (`dossiers-page`); `26-sources` in the real empty state at `/novels/{id}/knowledge/sources` (`sources-empty`, upload door); `27-causality` at `/novels/{id}/planning/causality` (`causality-page`); `28-settings-hub` at `/settings` (`settings-page`); `29-ai-rules` at `/settings/ai-regeln` (`ai-rules-page`); and `30-prompts` at `/settings/prompts` (`prompts-page`, catalog and editor). The empty Sources frame avoids the server-generated upload date, which cannot be pinned without a product clock seam or a forbidden DB shortcut. Reuse the route/test-id contracts in the setup, knowledge, planning, settings and prompts E2E suites. Do not capture Stitch drafts, designed-only surfaces or update-check UI.

- [ ] **Step 5: Add the W9 create/interview faces**

Capture `31-entity-create`, `32-entity-create-dark`, `33-entity-interview` and `34-entity-interview-dark` from the live W9 flow. Start at `/novels/{id}/knowledge/graph`; `graph-new-entity` now opens the interview, and `entity-interview-manual` reaches the create dialog. Use `entity-create-dialog` for the manual face. For the interview, open `?interview=new`, choose `entity-interview-type-*`, start, answer through `entity-interview-composer`/`-send`, and wait for `entity-interview-proposal`. Seed with `_seed_canon` from `app/capabilities/knowledge/e2e/test_entity_interview_e2e.py:62-69` and the real fake provider (`chat_vendor()`); reuse `_goto_graph`, `_open_interview`, `_start`, `_composer` and `_say` from that suite. The frame must show a real proposal card and composer, not an empty or mocked panel.

- [ ] **Step 6: Pin the capture environment and write the generated overview**

Pin `NARRE_UPDATE_CHECK_URL=off` in the `run_stack` call at `scripts/screenshots.py:643`, beside the fake-provider settings. `app/kernel/testing/stack.py:448` already defaults it for spawned stacks; the explicit value documents the capture contract. Do not use `NARRE_E2E_ATTACH` for these captures, because an attached process cannot be reconfigured by the caller's environment.

After `capture` succeeds, write `render_index(SHOTS)` to the `--index` path. `just screenshots` uses the repository defaults; Task 5 owns the workflow's explicit `--index` invocation, index staging and manifest-path trigger. Capture into a temporary sibling directory first and replace the target PNG set—including removals—and index only after the full set succeeds; a failed capture must leave the previous masters untouched.

- [ ] **Step 7: Write failing asset tests**

Pin: the PNG directory exactly matches `SHOTS` (no missing or stale files); every file is PNG; every image is 1600×1000; every file is below 1 MB; the generated overview references every master exactly once; every current README screenshot path resolves to a committed PNG.

- [ ] **Step 8: Run the asset tests and verify failure**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: FAIL on missing new assets/index.

- [ ] **Step 9: Run two independent temporary captures**

```bash
just screenshots --out /tmp/opencode/screenshots-a --index /tmp/opencode/screenshots-a.md
just screenshots --out /tmp/opencode/screenshots-b --index /tmp/opencode/screenshots-b.md
```

- [ ] **Step 10: Prove determinism**

```bash
diff -u <(cd /tmp/opencode/screenshots-a && sha256sum *.png | sort) <(cd /tmp/opencode/screenshots-b && sha256sum *.png | sort)
diff -u /tmp/opencode/screenshots-a.md /tmp/opencode/screenshots-b.md
```

Expected: no output. Any clock, random ID, animation, update banner or scroll-position difference is a defect to fix before continuing.

- [ ] **Step 11: Generate the canonical assets and index**

Run: `just screenshots`
Expected: new 20–34 PNGs and `docs/screenshots/README.md` are written; the legacy set matches the keep/rename/remove audit, with no stale PNG left behind.

- [ ] **Step 12: Keep existing README image paths valid**

Apply only the path changes required by the legacy audit. Do not rewrite the README narrative yet. Every existing `<img>` must resolve to a committed PNG before this task is reviewed.

- [ ] **Step 13: Run both screenshot test files**

Run: `just test-file app/kernel/tests/test_screenshot_manifest.py` and `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: PASS.

- [ ] **Step 14: Review, then commit**

Reviewer reads the legacy-name audit, selector/route changes, update-check pin and README path delta, and visually checks the full master set. Then commit `docs(screenshots): refresh the product capture set` with a real `User-visible:` line and the required trailer.

## Task 3: Link the complete collection from the documentation

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/design/stitch/README.md:152-176`
- Test: `app/kernel/tests/test_screenshot_assets.py`

- [ ] **Step 1: Add failing documentation-link assertions**

Extend `test_screenshot_assets.py` to assert `docs/README.md` links to `screenshots/README.md` and `docs/design/stitch/README.md` links to `../screenshots/README.md` instead of duplicating the master-file list.

- [ ] **Step 2: Run tests and verify failure**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: FAIL on the missing links.

- [ ] **Step 3: Add the documentation links**

Add the screenshot collection under "Using the application" in `docs/README.md`. In `docs/design/stitch/README.md`, replace the duplicated 19-file list with a link to `../screenshots/README.md` and a short note that Stitch reference screens remain design evidence, not product captures.

- [ ] **Step 4: Run the asset tests**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: PASS.

- [ ] **Step 5: Review, then commit**

Reviewer checks the full collection link and the design-record wording. Then commit `docs(screenshots): link the complete capture collection` with a real `User-visible:` line and the required trailer.

## Task 4: Focus the README on the current product

**Files:**
- Modify: `README.md`
- Test: `app/kernel/tests/test_screenshot_assets.py`

- [ ] **Step 1: Add failing README contract assertions**

Extend `test_screenshot_assets.py` to parse every `<img src="assets/screenshots/...png" alt="...">` in `README.md`. Assert the sources equal `README_SHOTS` in manifest order, every source exists, every alt text is non-empty and descriptive, and the stale sentence claiming settings are "Phase 1 of the roadmap" is absent.

- [ ] **Step 2: Run tests and verify failure**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: FAIL on the old six-image selection and stale settings copy.

- [ ] **Step 3: Rewrite the product narrative**

Keep the local-first promise, setup path and contributor section. Replace the gallery with the eight curated frames. Add concise sections for writing/Zen, knowledge, planning, settings/prompts and the W9 entity interview. Correct `README.md:109-123`: provider/model configuration, per-task assignment and prompt preview/live test are live; `.env` is no longer the primary configuration story. Align export/import and series status with `docs/features/INDEX.md` rather than repeating the old claims. Do not mention the update check until its inventory row exists.

- [ ] **Step 4: Make the full collection discoverable**

Link to `docs/screenshots/README.md` directly below the curated gallery. Move the fake-provider/stand-in disclosure next to the images. State that the action runs manually, weekly and on relevant `main` pushes, but is advisory and never a required check.

- [ ] **Step 5: Run tests and inspect the rendered result**

Run: `just test-file app/kernel/tests/test_screenshot_assets.py`
Expected: PASS. Read the rendered README on the PR branch and confirm the images dominate neither the page nor the text.

- [ ] **Step 6: Review, then commit**

Reviewer checks every claim against `docs/features/INDEX.md` and the eight selected images. Then commit `docs(readme): show the current writing, knowledge and AI workflow` with a real `User-visible:` line and the required trailer.

## Task 5: Re-enable the workflow as one consistent live switch

**Files:**
- Modify: `.github/workflows/screenshots.yml`
- Modify: `CONTRIBUTING.md:208-220`
- Modify: `README.md` development/screenshot paragraph if needed

- [ ] **Step 1: Make header, triggers and decide path tell one story**

Rewrite the header for active manual, weekly and push regeneration. Uncomment `schedule` with `cron: "0 6 * * 0"` and `push` with `branches: [main]`. Keep trigger-level path filters absent; the `decide` job remains the single filter.

- [ ] **Step 2: Extend the UI-change regex and stage the generated index**

The `decide` regex at `.github/workflows/screenshots.yml:70` must include `scripts/screenshots.py` and the new `scripts/screenshot_manifest.py`, plus the existing `web/`, `app/capabilities/*/web/` and `i18n/` trees. It must not include `README.md`, `docs/**` or `assets/screenshots/**`.

The screenshot job's no-diff check and staging must cover both `assets/screenshots` and `docs/screenshots/README.md`. Keep the bot branch `chore/screenshots-${RUN_ID}` and keep `Screenshots: regenerate` out of the bot commit body.

- [ ] **Step 3: Update contributor documentation**

Replace the "five frames" and already-active-push description at `CONTRIBUTING.md:208-220` with the current manifest-driven collection, `just screenshots`, manual dispatch, Sunday schedule and relevant `main` push behavior. Link `docs/screenshots/README.md`.

- [ ] **Step 4: Run workflow security and syntax checks**

```bash
docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 -color
uvx zizmor==1.32.0 .github/workflows .github/actions
```

Expected: exit 0; no new findings.

- [ ] **Step 5: Run repository checks**

Run: `just check`
Expected: PASS. Also re-run both screenshot test files.

- [ ] **Step 6: Review the loop guards, then commit**

Reviewer traces four cases: docs-only push skips; UI push regenerates; bot PR merge does not retrigger; scheduled no-diff run opens no PR. Then commit:

```bash
git commit -m "ci(screenshots): regenerate master frames automatically

Closes #848
Closes #903" --trailer "Assisted-by: OpenCode (<actual-model>)"
```

## Task 6: Whole-branch verification and handoff

- [ ] **Step 1: Run the affected full gate**

Run: `just verify`
Expected: PASS. W9's last PR reported 142 browser tests, and #965 added another E2E leg afterward; use the current count printed by `just verify`. `assets/screenshots/**` currently resolves to every capability E2E suite, so confirm the output includes the full current set rather than accepting a narrower affected run.

- [ ] **Step 2: Run the whole-branch review**

A fresh reviewer reads the complete diff, including binary assets and generated Markdown. Findings are fixed before push; no minor finding is deferred.

- [ ] **Step 3: Push and open the PR**

Use a plain-language PR title, for example: `The README shows the current product and screenshots regenerate reliably`. The body names #903/#848, the revalidated `main` baseline and W9 completion evidence, the two-run hash proof, the full E2E proof and the workflow-lint commands. Push after each green task group; do not save the entire branch for the end.

- [ ] **Step 4: Stop before merge**

Wait for explicit owner approval. After merge, run one manual `Screenshots` workflow smoke test on `main`; expected: success and no regeneration PR when the committed assets/index are current. Remove the `status: in-progress` labels if they remain after the issues close.

## Verification Checklist

- `just test-file app/kernel/tests/test_screenshot_manifest.py`
- `just test-file app/kernel/tests/test_screenshot_assets.py`
- `just check`
- Two independent captures with identical `sha256sum` output and identical index Markdown, with `NARRE_UPDATE_CHECK_URL=off` and no attach mode
- actionlint and zizmor clean
- `just verify` with the full E2E set
- Whole-branch review green
- Post-merge manual workflow smoke test green
