# README screenshot follow-ups — design

**Status:** approved by owner instruction, 2026-11-26 · **Owner:** kiesow · **Size:** one follow-up work package

## Intent

Close every finding raised by the README/screenshot branch and its reviews
(#977–#991) on the same branch. The owner does not accept follow-up debt for this
task.

## Baseline

- Branch: `chore/readme-screenshots`.
- The screenshot pipeline, 25 masters, focused README, full collection index and
  advisory workflow are implemented and reviewed.
- `just verify` passed before the final screenshot fix wave: 1,753 backend tests,
  1,653 web tests, production build and 143 E2E tests.
- Issues #977–#991 are claimed with `status: in-progress` and assignee
  `jmerifjKriwe`.

## Goals

- Make documentation truth match the product and ensure its relative links resolve.
- Make lore-graph layout deterministic across fresh UUIDs and restore a real
  multi-node graph master.
- Remove English-UI content drift in setup and prompt examples, and make the
  writing year dynamic.
- Give settings subpages a route-aware breadcrumb.
- Harden screenshot publication, test boundaries, workflow decisions and framing.
- Avoid making unbuilt-product placeholder copy the visual focus of published
  masters.
- Regenerate every affected master and close each issue from its fixing commit.

## Non-goals

- No new capability, route, API, schema or migration unless a finding proves it
  unavoidable.
- No new screenshot folder or duplicate image source.
- No force push and no rewrite of pushed history. Local unpushed commits may be
  rebuilt into coherent task commits before first push.
- No deferred minor finding after the branch is ready.

## Anti-goals

- A test passes because it repeats the implementation's own ordering or wording.
- A screenshot hides a defect with CSS, mocked data or a database shortcut.
- A product fix is implemented in the screenshot script instead of the product.
- An issue is closed merely because it was filed or linked.

## Constraints

- The five standing rules in `docs/_shared/CONSTRAINTS.md` apply.
- User-visible text stays in the en/de/fr catalogs; code, tests and developer
  documentation stay English.
- UI/frontend work is implemented and reviewed by subagents with explicit model
  names.
- Every task has an independent reviewer and a focused gate; the final branch has
  a whole-branch review.
- Screenshot frames remain real-stack 1600×1000 captures, below 1 MB, with
  deterministic hashes on this machine and documented cross-machine font limits.
- The workflow remains advisory and loop-safe.

## Decisions

### Documentation truth

- `docs/features/INDEX.md` marks the retired Structure view as `backend` in
  Phase 1: the structures registry/API remains, but no productive surface or E2E
  leg exists. Phase 1 is the inventory's unfinished-surface phase; Phase 0 is
  already done. `ROADMAP.md` lists the view among its three loose doors without
  presenting it as a delivered or AI surface.
- `docs/design/stitch/README.md` uses `../../superpowers/specs/...` for its two
  design/spec links, and a resolve-based test covers every relative Markdown
  target in that file.

### Graph determinism

- `layoutGraph` sorts by case-folded entity name, using ID only as the final
  tiebreaker for duplicate names.
- `graphSignature` uses the same canonical key so a rename changes both positions
  and the reframe signature.
- Parallel relation arcs use a content key rather than relation UUID where
  duplicate pairs exist.
- Tests compare identical names under different UUIDs and reversed input order.
- The graph masters use a real three-node/two-edge canon.

### Content and navigation

- Setup's writing year is derived at render time or supplied through a tested
  language-neutral value; it is not hardcoded to 2025.
- Prompt sample values are English or language-neutral on the English UI.
- Every English setup display site uses the demo's English display title; later
  wizard steps do not switch back to the German archive title. The provisioning
  POST and imported novel keep the archive's original title and language.
  `title_en` is optional display-only interchange metadata, not an imported novel
  fact; absent or empty values fall back to the archive title. General archive
  parsing preserves any string value without a display-title length limit and
  treats non-string values as absent, so unusable display metadata can never
  reject otherwise valid novel content. Persisted metadata stays strict.
- Settings subpages derive their breadcrumb from the settings route, not the
  bookshelf shell.

### Screenshot tooling

- Publication helpers live in a filesystem-only module so asset contract tests do
  not import Playwright.
- Masters and index may live on different filesystems; each output is staged and
  backed up on its own filesystem, with joint rollback and preserved backups on
  restore failure. An existing output must share its parent's device so its
  sibling backup stays on that filesystem; a mount-point mismatch fails before
  mutation. Canonical recovery roots are ignored, cleanup never masks the primary
  publication error, and interrupts propagate with recovery data preserved.
- Documentation tests assert structured meaning where practical; exact accepted
  wording is centralized and explained where semantics cannot be inferred.
- The workflow's UI-path check consumes the full diff without `grep -q` under
  `pipefail`, the bot merge guard does not depend on editable PR-title text, and
  repeated runs defer when a screenshot update PR is already open. The lookup
  sentinel is validated exactly; malformed output fails visibly. Deferral never
  updates the existing PR, so a human must close or replace it when newer UI
  changes make its captured diff stale.
- README and collection disclosures name every stand-in source, including
  dossier extraction, and never claim other frames contain no generated content.
- Framing fixes adjust real seed counts, scroll positions or capture regions;
  they do not mask UI copy. The causality page groups its existing subline,
  header/track and methodology/footnote blocks, leaving one intentional vertical
  gap instead of adding scenes, a new surface or mechanically stretched gaps.
- Shelf frames prioritize the complete last card and subtitle; the page H1 may
  sit above the fixed top bar because it is not an acceptance element.
- Unbuilt-product copy is removed from the visual focus by choosing honest live
  states or correcting product copy in its owning capability.

## Acceptance

- #977–#991 are closed from commits on this branch.
- No `status: in-progress` follow-up remains.
- New/changed tests cover each finding's trigger.
- Affected masters are regenerated; two independent captures match byte-for-byte.
- `just verify` passes on the final head.
- The final whole-branch review is green.
- The PR body lists the closing commits and verification evidence.
