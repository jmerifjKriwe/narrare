# Lane B Review Protocol and Reachability E2E Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the Lane B protocol to one independent whole-diff review with no deferred findings, bound standing rule 2's E2E gate to user-reachable behavior, and remove the dead showcase tooling.

**Architecture:** One seam: the repository's review-and-gate boundary. The protocol lands in `AGENTS.md`; the reachability boundary lands once in `docs/_shared/CONSTRAINTS.md` and is mirrored in `TESTING.md` and `REVIEW.md`; the dead showcase marker, filter, and two stale docstrings are removed from `pyproject.toml`, `justfile`, `docs/design/stitch/SCREENSHOT-COMPARISON.md`, and `scripts/side_by_side.py`. The architecture spec is untouched. The approved design and this plan are created in Step 1 and enter the single change commit after the review is green. There are no fix commits before that commit: the first review sees tree hash A, the fix produces tree hash B, and the scoped re-review sees only the diff A→B.

**Tech Stack:** Markdown, TOML (`pyproject.toml`), just, Python 3.14 / pytest / Playwright / Vitest as invoked by the existing gates.

**Spec:** `docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md` — approved by the product owner on 2026-11-28 and created verbatim in Step 1. The plan is `docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md`. Both are committed with the change.

---

## Approved design (summary; the spec created in Step 1 is the authority)

The product owner approved this as Change 1 of a proportional Lane B development path. The five required outcomes:

1. **`AGENTS.md` — Lane B protocol.** One independent whole-diff review replaces the separate task and final reviews. One consolidated fix round answers every finding, and at most one scoped re-review follows. No `Important` or `Nit` finding is deferred. The implementer runs the full `just verify` for the affected scope once before the first review; after fixes, only the gate covering each fixed path runs. The coordinator commits only after the review is green. The first review sees tree hash A; the fix produces tree hash B; the scoped re-review sees only the diff A→B plus the findings it answers. Temporary evidence lives under `.superpowers/sdd/lane-b-<slug>/`: tree hashes A and B, the diff A→B, exact commands and output, review, fix round, re-review.
2. **`docs/_shared/CONSTRAINTS.md` — rule 2.** The E2E gate proves user-reachable app behavior. Maintainer- and developer-only tools — demos, generators, screenshot/showcase tooling, CI hooks — get no E2E; unit or integration tests suffice.
3. **`TESTING.md` and `REVIEW.md`.** Mirror the same boundary, including the harness-smoke exception: a CI-definition change owes the smoke suite, not every suite.
4. **Dead showcase tooling.** Remove the unused `showcase` pytest marker from `pyproject.toml`, remove the `and not showcase` filter from `justfile`'s `test-e2e`, and correct the stale showcase E2E instructions in `docs/design/stitch/SCREENSHOT-COMPARISON.md` and `scripts/side_by_side.py`.
5. **Architecture spec unchanged.** `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` is not edited.

Governance and commit rules:

- This process change is itself governed, **not Lane B**. It runs the full path regardless of its file and line counts. The new Lane B protocol applies only after this change merges.
- Existing uncommitted edits in `AGENTS.md`, `REVIEW.md`, `scripts/side_by_side.py` or the follow-up docs are inspected and merged into the working copy, never overwritten. At plan time (`2026-11-28`) there are none in this checkout.
- Commit type is hidden (`chore(docs)`), with no `User-visible:` line. The `Assisted-by:` trailer is added at execution.

---

## Global Constraints

- Create exactly two new documents: the spec at `docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md` and the plan at `docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md`. No other design doc, issue, gate, registry, or mandatory document.
- If the plan-mode artifacts exist under `~/.opencode/plan`, move them into the worktree, never copy: one state, not two. Reconcile the moved text with the content pinned in Step 1.
- Do not edit `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` or `docs/superpowers/follow-ups.md`.
- Execute in an isolated worktree based on `narrare/main`. The current checkout carries unrelated edits in `app/kernel/db/migrate.py` and `app/kernel/db/tests/test_migrations.py`; they must not appear in this diff or in the `just verify` evidence.
- Before any edit, run the preservation check below. If a target file is dirty, read `git diff -- <path>` and fold its content into the new text by editing. Never run `git checkout --`, `git restore`, or `git stash` on those paths.
- No file diff may be reverted by a broad `git add -A` or `git commit -a`. Stage only the ten named paths in Step 15.
- `--no-verify`, force push, skipped or re-rolled tests, and deferred `Important`/`Nit` findings are forbidden.
- `REVIEW.md`'s three-`Nit` cap still bounds one review. “No deferred finding” means every posted finding is fixed in the one consolidated round.
- A finding the implementer believes is technically wrong is answered with evidence in the same round, not silently deferred. If it cannot be resolved, the task stops open; it does not commit.
- Reviewers are read-only: they never edit, stage, commit or push, and they do not write the evidence bundle. A reviewer returns the review or re-review text to the coordinator; the coordinator saves it.
- Dispatch names its models explicitly. Local assignment: implementer and reviewer `opencode-go/deepseek-v4.1-flash`; use the fallback from the local table only after one failed retry, and record the switch in the evidence bundle.
- The evidence bundle is temporary; `.superpowers/.gitignore` already ignores all of `.superpowers/`. It is never committed.
- The git remote is `narrare`; never push to `origin`. English only in code, tests, and developer documentation.

---

## Review Focus

1. **A maintainer-only tool is still judged by the E2E gate.** A screenshot, showcase, generator, demo, or CI hook has no user-reachable path; demanding a browser suite for it is the failure the new boundary prevents. The harness-smoke exception must stay narrow: CI-definition changes only, suite `settings`.
2. **Lane B is read as “lighter review.”** The text must still require one independent whole-diff reviewer, one consolidated fix round, at most one scoped re-review, and zero deferred `Important`/`Nit` findings.
3. **The reduced loop is used after crossing a Lane B limit** — a new surface, route, endpoint, or schema change still re-routes to Lane A on a fresh branch.
4. **Dead showcase references survive somewhere in the edited surface** — `test_showcase_e2e.py`, `-m showcase`, or `pytest.mark.showcase` still appearing in `SCREENSHOT-COMPARISON.md` or `scripts/side_by_side.py`, or a command that cannot run today.
5. **The process change is mislabeled as Lane B or committed before review** — including an accidental edit to the architecture spec, unrelated dirty files entering the commit, the spec or plan missing from the change commit, or a scoped re-review that reads more than the diff A→B and the findings it answers.

---

### Task 1: Create the spec and plan, state the new Lane B loop and reachability boundary, and retire the showcase leftovers

**Files:**
- Add: `docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md` (Step 1)
- Add: `docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md` (Step 1 — this plan, verbatim)
- Modify: `AGENTS.md:110-114,126-128` (Lane B bullet; insert the review-loop paragraph after the “Neither lane trades…” paragraph)
- Modify: `docs/_shared/CONSTRAINTS.md:11-14` (rule 2)
- Modify: `TESTING.md:8-11,36-43,57-84,126-133` (philosophy, not-tested, gates, checklist)
- Modify: `REVIEW.md:30-56,84-86` (Important/Skip boundary, Lane B section, re-review)
- Modify: `pyproject.toml:155` (remove marker)
- Modify: `justfile:126` (remove filter)
- Modify: `docs/design/stitch/SCREENSHOT-COMPARISON.md:1-82` (correct the suspended workflow)
- Modify: `scripts/side_by_side.py:3-19` (remove the dead showcase instruction)

**Interfaces:**
- Consumes: `just verify` (`justfile:62-70`), the affected resolver (`scripts/affected.py`: `SHARED` includes `pyproject.toml` and `justfile`; `INERT` includes `AGENTS.md`, `TESTING.md`, `docs/`; `HARNESS` is `.github/workflows/` and `.github/actions/`; `SMOKE = "settings"`), and the pytest marker registry in `pyproject.toml`.
- Produces: no runtime interface. Produces the standing text that later Lane B changes and reviews read, a `test-e2e` command that no longer filters a marker no test uses, and the design record under `docs/superpowers/specs/`.

- [ ] **Step 1: Start an isolated worktree, create the spec and plan, and check for pre-existing edits**

Use the harness's native worktree tool (`superpowers:using-git-worktrees`) if available; the manual equivalent from the repository root is:

```bash
git worktree add /tmp/opencode/narrare-lane-b -b chore/lane-b-review-protocol narrare/main
```

From the new worktree root, create `docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md` with exactly:

```markdown
# A proportional Lane B development path — Change 1

**Status:** approved by the product owner on 2026-11-28. This is a governed
process change, not a Lane B change; the new protocol applies only after this
change merges. This document records Change 1 only.

## Context

Lane B carries bounded fixes, follow-ups, refactors and UI corrections inside
one capability folder. Its protocol today names one whole-diff review but does
not say how many fix rounds follow, when the gate runs, or what evidence is
kept. The result is either a second review layer Lane B does not need or a
review whose findings are deferred to a later change.

Standing rule 2 binds every capability to a green E2E. Read literally, it also
demands an E2E from tools no user can reach: demos, generators, screenshot and
showcase harnesses, and CI hooks.

## Change

### 1. Lane B's review loop

- One independent review of the whole diff against `main` replaces the separate
  task review and the final review. That first review pins tree hash A.
- The implementer runs the full `just verify` for the affected scope once,
  before the first review, and records the exact command and output.
- One consolidated fix round answers every `Important` and `Nit` finding. No
  finding is deferred: the change's scope is the whole diff. The fix round
  produces tree hash B.
- The scoped re-review reads only the diff A→B plus the findings it answers —
  one re-review, at most. It does not re-read tree B as a whole.
- After the fixes, only the gate covering each fixed path runs; a second full
  `just verify` is not owed.
- The coordinator commits only after the review is green.
- Evidence is temporary and not committed: `.superpowers/sdd/lane-b-<slug>/`
  holds tree hashes A and B, the diff A→B, the exact commands and output, the
  review, the fix round and the re-review.

### 2. The E2E boundary

Standing rule 2 proves user-reachable app behavior. A maintainer- or
developer-only tool — a demo, generator, screenshot or showcase tool, or a CI
hook — has no user-reachable path and owes unit or integration tests, never an
E2E. The narrow exception is a change to `.github/workflows/` or
`.github/actions/`, which owes the smoke suite `settings` as proof the harness
runs.

### 3. Mirrors

`TESTING.md` and `REVIEW.md` state the same boundary. A CI-definition change is
the narrow harness exception: it owes the smoke suite `settings`, not every
capability suite.

### 4. Dead showcase tooling

No showcase E2E spec exists in the tree. Remove the unused `showcase` pytest
marker from `pyproject.toml`, the `and not showcase` filter from `justfile`, and
the dead showcase instructions from
`docs/design/stitch/SCREENSHOT-COMPARISON.md` and `scripts/side_by_side.py`.

## Non-goals

- The architecture spec
  `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` is
  unchanged.
- This change does not run as Lane B, whatever its file and line counts; it is a
  governed process change.
- No new gate, test, registry or mandatory document is introduced.

## Acceptance

- `AGENTS.md` names all six elements of the Lane B loop.
- `CONSTRAINTS.md` rule 2, `TESTING.md` and `REVIEW.md` agree on reachability
  and the `settings` harness exception.
- `rg -n "showcase" pyproject.toml justfile scripts/side_by_side.py` returns no
  matches, and `SCREENSHOT-COMPARISON.md` contains no dead showcase command or
  E2E path.
- `just verify` is green once before review; the review and one scoped
  re-review are green; the commit carries the `Assisted-by` trailer.
```

Save this plan verbatim at `docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md`. Both files enter the single change commit in Step 15. If plan-mode artifacts exist under `~/.opencode/plan`, move rather than copy them, then reconcile against the pinned content.

Then run:

```bash
git status --porcelain -- AGENTS.md TESTING.md REVIEW.md docs/_shared/CONSTRAINTS.md \
  docs/superpowers/follow-ups.md docs/design/stitch/SCREENSHOT-COMPARISON.md \
  pyproject.toml justfile scripts/side_by_side.py
test -f docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md
test -f docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md
```

Expected: the first command has no output; both `test -f` commands exit 0. If the status command lists a target file, read `git diff -- <path>` and merge that content by editing; do not overwrite it. Record the check in the evidence bundle.

- [ ] **Step 2: Rewrite the Lane B bullet and add the review-loop paragraph in `AGENTS.md`**

Replace the Lane B bullet so its review sentence reads:

```markdown
- **Lane B — a bounded change.** A fix, a follow-up, a refactor or a UI correction
  inside one capability folder that changes no surface. One task: one implementer,
  one independent review of the whole diff, no design doc, no plan, no gap ledger, no
  index issue. The capability's existing E2E leg must run green; if it does not cover
  the change, the change is Lane A.
```

Insert this paragraph immediately after the paragraph ending “Neither lane trades the E2E proof, the independent reviewer or a gate.”:

```markdown
**Lane B's review loop** (2026-11-28, owner decision). The implementer runs the
full `just verify` for the change's affected scope once, before the first review,
and records the exact command and its output. One independent reviewer then reads
the whole diff against `main` at tree hash A: there is no per-task review and no
second final review. One consolidated fix round answers every `Important` and
`Nit` finding from that review; nothing is deferred, because the change's scope
is the whole diff. The fix round produces tree hash B. The scoped re-review reads
only the diff A→B plus the findings that round answered — one re-review, at most.
After the fixes, run only the gate that covers what a fix touched: `just check`
for code, the capability's E2E file or test file for a UI or logic path, the
static checks for prose alone. A Lane B change commits only after the review is
green. Evidence is temporary and stays out of the commit:
`.superpowers/sdd/lane-b-<slug>/` holds tree hashes A and B, the diff A→B, the
exact commands and output, the review, the fix round and the re-review.
```

Expected: the bullet names `one independent review`, and the paragraph names all required elements — one full verify, no task/final split, tree hash A, one consolidated round producing tree hash B, no deferral, one scoped re-review of A→B, temporary evidence.

- [ ] **Step 3: Sharpen rule 2 in `docs/_shared/CONSTRAINTS.md`**

Replace rule 2 with:

```markdown
2. **A capability is done only with a green E2E** that proves a user-reachable
   path through the real UI, the real backend and the real database. A
   maintainer- or developer-only tool — a demo, a generator, screenshot or
   showcase tooling, a CI hook — has no user-reachable path: it owes unit or
   integration tests, never an E2E. The narrow exception is a change to
   `.github/workflows/` or `.github/actions/`, which owes the smoke suite
   `settings` as proof the harness runs. The only permitted fake is the LLM
   provider at its boundary: a provider row of kind `fake`, chosen by
   configuration, never a test branch.
```

Expected: the fake-provider sentence is unchanged; the new first sentence names reachability, and the new second sentence enumerates the tool classes.

- [ ] **Step 4: Mirror the boundary in `TESTING.md`**

Replace the first philosophy bullet with:

```markdown
- **E2E is the gate for what a user can reach.** A capability is done when a
  green E2E drives the real UI, the real backend and the real database. A
  maintainer- or developer-only tool has no user-reachable path and is tested at
  its own layer instead. Nothing else counts as "done" for a capability.
```

Append to the second philosophy bullet, after “They do not replace E2E.”:

```markdown
  For a maintainer-only tool they are the proof, because the E2E gate does not
  apply.
```

Keep “What is not tested” limited to render-only components, styling and logic
already covered by E2E. Scope its closing “E2E covers these sufficiently”
paragraph to those three items. Then add a separate paragraph:

```markdown
Maintainer- and developer-only tools — demos, generators, screenshot and
showcase tooling, and CI hooks — expose no user-reachable path, so they get no
E2E suite; the logic they carry ships with unit or integration tests
(`scripts/tests/` for a script). The narrow exception is a change to
`.github/workflows/` or `.github/actions/`, which owes the smoke suite `settings`
(the answer `scripts/affected.py` already encodes), proof the harness runs — not
every capability suite.
```

Add to “Gates and CI”, after the `test-e2e` bullet:

```markdown
A CI-harness change runs the smoke suite `settings`; it does not owe every
capability suite, because it can break the harness, not a capability's code.
```

Add to the “Review checklist”:

```markdown
- [ ] No E2E was added for a maintainer- or developer-only tool; its proof is a
      unit or integration test.
- [ ] A CI-harness change ran the smoke suite, not every capability suite.
```

Expected: the E2E gate is not weakened for capabilities; a tool's missing E2E is explicitly not a gap; the smoke suite is named as `settings`.

- [ ] **Step 5: Mirror the boundary and the Lane B loop in `REVIEW.md`**

Add under `## Important`, after the Lane B-limit bullet:

```markdown
- An E2E suite demanded for, or added to, a maintainer- or developer-only tool
  (a demo, generator, screenshot/showcase tool, or CI hook). Such a tool owes
  unit or integration tests. A CI-harness change owes the smoke suite `settings`,
  not every suite.
```

Add under `## Skip`:

```markdown
- A missing E2E for a maintainer- or developer-only tool. It is covered at its
  own layer; the smoke suite is owed only when the CI harness itself changes.
```

Insert before `## Re-review`:

```markdown
## Lane B

- One independent review of the whole diff against `main` replaces the per-task
  and final reviews. Read the diff once, whole, at tree hash A.
- One consolidated fix round answers every `Important` and `Nit` finding from
  that review. Nothing is deferred: a finding needed for the agreed behavior,
  correctness, tests or gates belongs in that round. The fix round produces tree
  hash B.
- The scoped re-review reads only the diff A→B plus the findings it answers —
  one re-review, at most. Do not re-read tree B as a whole or repeat a finding
  already posted.
- The change commits only after this review is green. The implementer ran
  `just verify` once before the first review; after fixes, only the gate covering
  each fixed path is owed, not a second full `just verify`.
- Evidence lives in `.superpowers/sdd/lane-b-<slug>/` — tree hashes A and B, the
  diff A→B, exact commands and output, review, fix round, re-review — and is not
  committed.
```

Append to `## Re-review`:

```markdown
- A Lane B fix round gets one scoped re-review of the diff A→B only; there is no
  further round.
```

Expected: a reviewer reading only `REVIEW.md` can run the Lane B loop without opening `AGENTS.md`, and the boundary produces neither a false “missing E2E” finding nor a demand for every suite after a CI change.

- [ ] **Step 6: Remove the dead showcase marker and filter**

In `pyproject.toml`, delete the marker line:

```toml
  "showcase: visual showcase seeds for Stitch comparison; run manually, not in CI",
```

Leave the `e2e` marker and every other line untouched.

In `justfile`, change the `test-e2e` invocation from:

```bash
uv run pytest $paths -v -m "e2e and not showcase" --timeout=60 -n "$workers"
```

to:

```bash
uv run pytest $paths -v -m e2e --timeout=60 -n "$workers"
```

Expected: `rg -n "showcase" pyproject.toml justfile` returns no matches (exit 1). No test uses the marker, so collection is unchanged.

- [ ] **Step 7: Correct `docs/design/stitch/SCREENSHOT-COMPARISON.md`**

Replace the whole file with exactly:

```markdown
# Screenshot comparison against the Stitch drafts

The Stitch exports under `screens/` are design drafts, not specifications (see
the README). A visual comparison needs a *populated* instance, because empty
shelves and empty graphs tell nothing about density, spacing or chrome. The
showcase specs that once seeded one were removed with the frontend rebuild (W0)
and have not returned.

> **Suspended for the rebuild interim (W0).** The capability screens were
> demolished for the frontend rebuild, and the showcase specs left with them.
> No showcase spec exists in the tree. The `showcase` pytest marker and the
> `just test-e2e` filter that excluded it were removed on 2026-11-28. The drafts
> under `screens/` stay here as the reference W1 harmonizes and W2 ports.

## The removed capture specs

Three E2E specs once seeded a real instance with Stitch-canonical data and
captured screenshots:

| Capability | Screenshots |
|---|---|
| Writing | `shelf.png`, `workspace-dead-signal.png` |
| Knowledge | `knowledge-graph.png` |
| Planning | `planning-chronology.png`, `planning-storyboard.png`, `planning-structure.png` |

They were deleted with W0 and have not been rebuilt. A screenshot or visual
comparison harness is maintainer-only tooling: it has no user-reachable path, so
it gets no E2E suite and owes unit or integration tests instead
([`CONSTRAINTS.md`](../../_shared/CONSTRAINTS.md), rule 2). Rebuild the capture as
a tool, not as a browser test.

## What the seeds contained

- **Writing**: Dead Signal (3 chapters, 3.384 words), Winterhaus (0), The Salt
  Road (12 chapters, 24.144 words), Der Nebel von Arkona (5 chapters, 11.200
  words) — word totals taken from `screens/library/shelf.webp`. Dead Signal's
  first chapter carries the prose the workspace screen draws, padded to its
  stated 765 words.
- **Knowledge**: one novel whose chapter body names the capitalized entities the
  fake provider turns into nodes (Maya, Chen, Horizon, Station, Kavic, …). The
  entities are derived, not curated — read the screenshot for chrome/density,
  not for exact labels.
- **Planning**: one novel with five timeline events and one chapter carrying
  four scenes.

## How to compare

When a populated capture exists, open it next to the corresponding `.webp`:

- `shelf.png` ↔ `screens/library/shelf.webp`
- `workspace-dead-signal.png` ↔ `screens/writing/workspace*.webp`
- `knowledge-graph.png` ↔ `screens/knowledge/lore-graph*.webp`
- `planning-chronology.png` ↔ `screens/planning/chronology-timeline.webp`
- `planning-storyboard.png` ↔ `screens/planning/three-act-storyboard.webp`

Read for drift in layout, spacing, typography scale and component chrome. The
Stitch drafts are not the spec — where they and the frontend-design spec
disagree, the spec decides (`docs/superpowers/specs/`).

## Why not a unified seed for the automated suites

The automated E2E suites keep their own minimal per-test seeds: isolation
between tests, CI narrowing to touched capabilities, and the different shapes
each test needs (empty DB, 50 scenes, …). The removed showcase was a development
and visual-review tool, not a test fixture.
```

Expected: no `test_showcase_e2e.py`, `-m showcase`, `pytest.mark.showcase`, or `just test-e2e writing` command remains in this file, and the relative link `../../_shared/CONSTRAINTS.md` resolves.

- [ ] **Step 8: Remove the dead showcase instruction from `scripts/side_by_side.py`**

Replace the module docstring's opening through the run example with:

```python
"""Compose the fidelity artifact: a real surface beside its archived draft.

The Literary Modernism pilot's acceptance is the side-by-side (spec §6.6, §9):
one image per theme holding a real capture of the seeded route next to the
Stitch WebP it was built against. This script is the composition step — it
scales both panels to one height, labels them and writes one PNG. It is not a
gate: the artifact lands in the wave's ``.superpowers/`` folder for the PR
description, never in ``assets/screenshots/``.

Pass a real capture and its archived draft with ``--real`` and ``--draft``::

    uv run python -m scripts.side_by_side \
        --real path/to/shelf.png \
        --draft docs/design/stitch/screens/library/shelf.webp \
        --out .superpowers/sdd/<wave>/side-by-side-light.png

The dark artifact pairs ``shelf-dark.png`` with ``shelf-dark.webp`` and passes
``--theme dark`` so the frame around the comparison wears the midnight ground.
"""
```

Also replace the remaining seeded-E2E help and default labels with real-capture
wording. Expected: no dead showcase command, obsolete theme flag, or E2E-seed
wording remains in `scripts/side_by_side.py`.

- [ ] **Step 9: Run the static gates**

```bash
rg -n "showcase" pyproject.toml justfile scripts/side_by_side.py
rg -n "test_showcase_e2e|just test-e2e.*showcase|-m showcase|pytest\.mark\.showcase" \
  docs/design/stitch/SCREENSHOT-COMPARISON.md
rg -n "tree hash A|tree hash B|diff A→B|consolidated fix round|scoped re-review" \
  AGENTS.md
rg -n "user-reachable" docs/_shared/CONSTRAINTS.md TESTING.md REVIEW.md
git diff --stat
git status --porcelain
git diff --exit-code -- docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
git diff --exit-code -- docs/superpowers/follow-ups.md
```

Expected:

- First two `rg` commands: no matches, exit status 1.
- Third: at least four matching lines in `AGENTS.md`, including `tree hash A`, `tree hash B`, and `diff A→B`.
- Fourth: at least one match in each of the three files.
- `git diff --stat`: exactly eight modified tracked files — `AGENTS.md`, `TESTING.md`, `REVIEW.md`, `docs/_shared/CONSTRAINTS.md`, `pyproject.toml`, `justfile`, `docs/design/stitch/SCREENSHOT-COMPARISON.md`, `scripts/side_by_side.py`.
- `git status --porcelain`: those eight as `M`, plus the spec and plan as `??`, and nothing else.
- Both `git diff --exit-code` commands: exit 0, no output.

- [ ] **Step 10: Run the full gate once, before the first review**

```bash
mkdir -p .superpowers/sdd/2026-11-28-lane-b-review-protocol
set -o pipefail
just verify 2>&1 | tee .superpowers/sdd/2026-11-28-lane-b-review-protocol/verify.log
```

Expected: exit 0; `check`, the backend integration suite, the frontend unit suite, the production build, and the E2E all green. Because `pyproject.toml` and `justfile` are shared surfaces, the affected resolver runs all six existing E2E suites: knowledge, planning, prompts, settings, setup, writing. The log does not print “no capability touched — no browser suite owed”.

Do not run `just verify all`; `just verify` is the design's one full run.

- [ ] **Step 11: Pin the reviewed state as tree hash A**

Build a tree object from the working tree without touching the real index and without creating a commit:

```bash
tmpi=$(mktemp)
GIT_INDEX_FILE="$tmpi" git read-tree HEAD
GIT_INDEX_FILE="$tmpi" git add -A -- \
  AGENTS.md TESTING.md REVIEW.md docs/_shared/CONSTRAINTS.md \
  pyproject.toml justfile docs/design/stitch/SCREENSHOT-COMPARISON.md \
  scripts/side_by_side.py \
  docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md \
  docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md
A=$(GIT_INDEX_FILE="$tmpi" git write-tree)
printf '%s\n' "$A" > .superpowers/sdd/2026-11-28-lane-b-review-protocol/tree-a.txt
git cat-file -t "$A"
rm -f "$tmpi"
```

Expected: `git cat-file` prints `tree`; `tree-a.txt` holds one hash; no commit exists. This is the exact state the first review sees.

- [ ] **Step 12: Dispatch the one independent whole-diff review at tree hash A**

Dispatch a fresh reviewer session; it must not be the implementer. The reviewer is read-only: no edits, staging, commits, pushes, or evidence writing. Name the model explicitly in the dispatch (`opencode-go/deepseek-v4.1-flash` unless the local assignment has switched and the evidence records it). The reviewer receives:

- The spec at `docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md` and the `Review Focus` list.
- The pinned review state: `A=$(cat .superpowers/sdd/2026-11-28-lane-b-review-protocol/tree-a.txt)` followed by `git diff narrare/main "$A"`. This is the whole diff, including the spec and plan; there is no separate untracked-file instruction.
- `REVIEW.md`'s tags and count-first summary format.

The reviewer checks at minimum: the six Lane B protocol elements, the user-reachable boundary in all three docs, the narrow smoke exception, that the showcase surface has no dead command or E2E path in either file, that no rule is weakened, and that the architecture spec is untouched.

The reviewer **returns the review text in its reply**. The coordinator writes that text to `.superpowers/sdd/2026-11-28-lane-b-review-protocol/review.md`.

Expected: the coordinator saves a count-first review against tree hash A. If it says `Nothing to fix.`, the review is green; skip Steps 13–14 and go to Step 15.

- [ ] **Step 13: One consolidated fix round produces tree hash B**

The implementer answers every `Important` and `Nit` finding from the returned review in one round. No finding is deferred, re-filed, or downgraded. A disputed finding is answered with file-and-line evidence in `.superpowers/sdd/2026-11-28-lane-b-review-protocol/fix-round.md`; it is not left open.

After the fixes, run only the gate that covers what changed:

```bash
# If any code or tooling changed:
just check

# If the E2E selection (pyproject.toml / justfile) changed:
just test-e2e affected

# Always re-run the static checks from Step 9.
```

Then pin the fixed state as tree hash B and capture the exact diff the re-review will read:

```bash
A=$(cat .superpowers/sdd/2026-11-28-lane-b-review-protocol/tree-a.txt)
tmpi=$(mktemp)
GIT_INDEX_FILE="$tmpi" git read-tree HEAD
GIT_INDEX_FILE="$tmpi" git add -A -- \
  AGENTS.md TESTING.md REVIEW.md docs/_shared/CONSTRAINTS.md \
  pyproject.toml justfile docs/design/stitch/SCREENSHOT-COMPARISON.md \
  scripts/side_by_side.py \
  docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md \
  docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md
B=$(GIT_INDEX_FILE="$tmpi" git write-tree)
printf '%s\n' "$B" > .superpowers/sdd/2026-11-28-lane-b-review-protocol/tree-b.txt
git diff "$A" "$B" > .superpowers/sdd/2026-11-28-lane-b-review-protocol/fix.diff
git cat-file -t "$B"
rm -f "$tmpi"
```

Expected: each gate that ran is green and its command and output are recorded in `fix-round.md`; `git cat-file` prints `tree`; `fix.diff` contains only the changes from A to B. Prose-only fixes still run the static checks.

- [ ] **Step 14: One scoped re-review of A→B**

The same reviewer receives exactly two inputs and nothing else:

- `.superpowers/sdd/2026-11-28-lane-b-review-protocol/fix.diff` — the diff from tree hash A to tree hash B.
- The findings in `.superpowers/sdd/2026-11-28-lane-b-review-protocol/review.md` that the fix round answers.

The reviewer does not read the whole of tree B, does not repeat an earlier finding, and returns the re-review text. The coordinator writes it to `.superpowers/sdd/2026-11-28-lane-b-review-protocol/re-review.md`. The reviewer does not write the file itself.

Expected: green re-review, naming for each finding the change in A→B that answers it. If it is not green, stop and report to the coordinator; do not start a second round and do not commit. The coordinator decides whether the task stays open or is re-routed.

- [ ] **Step 15: Commit only after the green review**

Confirm the returned re-review is green, then stage exactly these ten paths:

```bash
git add \
  AGENTS.md \
  TESTING.md \
  REVIEW.md \
  docs/_shared/CONSTRAINTS.md \
  pyproject.toml \
  justfile \
  docs/design/stitch/SCREENSHOT-COMPARISON.md \
  scripts/side_by_side.py \
  docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md \
  docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md

git commit \
  --trailer "Assisted-by: OpenCode (opencode-go/deepseek-v4.1-flash)" \
  -m "chore(docs): one Lane B review and a reachable-behavior E2E gate" \
  -m "Lane B now runs one independent whole-diff review with a single
consolidated fix round and no deferred findings, after one full verify.
The E2E gate now names user-reachable behavior: maintainer-only tools owe
unit or integration tests, and a CI-harness change owes the smoke suite.
The approved design and its plan travel with the change."
```

Expected: the commit hook passes. The type is hidden (`chore`), so no `User-visible:` line is required or added. The author and committer remain the human; only the trailer names the agent. The spec and plan are committed, not left untracked.

- [ ] **Step 16: Verify the commit, push to `narrare`, and open the PR**

```bash
git show --stat --oneline HEAD
git log -1 --format='%B' | grep -E '^Assisted-by: OpenCode \(opencode-go/deepseek-v4\.1-flash\)$'
git status --short
git diff --exit-code HEAD^ HEAD -- docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
```

Expected:

- `git show --stat`: exactly ten files changed, including the spec, the plan, and `scripts/side_by_side.py`.
- The trailer grep prints one line.
- `git status --short`: empty in the isolated worktree.
- The spec diff exits 0.

Push to the `narrare` remote and open the PR with a non-conventional title and a concrete body:

```bash
git push -u narrare chore/lane-b-review-protocol

gh pr create \
  --repo jmerifjKriwe/narrare \
  --base main \
  --head chore/lane-b-review-protocol \
  --title "One Lane B review and a reachable-behavior E2E gate" \
  --body "Approved process change. Lane B now runs one independent whole-diff review with a consolidated fix round and no deferred findings; the E2E gate now names user-reachable behavior, so maintainer-only tools owe unit or integration tests. Design: docs/superpowers/specs/2026-11-28-proportionaler-lane-b-design.md. Plan: docs/superpowers/plans/2026-11-28-lane-b-review-protocol.md. The new Lane B protocol applies after merge."
```

---

## Self-review against the approved design

| Approved outcome | Task step |
|---|---|
| Spec and plan created, committed with the change | Steps 1, 15, 16 |
| Lane B: one independent whole-diff review at tree hash A | Steps 2, 5, 12 |
| One consolidated fix round producing tree hash B, no deferral | Steps 2, 5, 13 |
| Scoped re-review sees only diff A→B plus answered findings | Steps 2, 5, 14 |
| Full `just verify` once before review; only covering gates after fixes | Steps 10, 13 |
| Evidence bundle with tree hashes A/B, diff A→B, commands/output, review/fix/re-review | Steps 11–14 |
| Coordinator saves review text; reviewer never writes files | Steps 12, 14 |
| Commit only after green review | Steps 12–15 |
| Rule 2: user-reachable behavior; tools get no E2E | Step 3 |
| TESTING/REVIEW mirror, harness-smoke exception | Steps 4, 5 |
| Showcase marker, justfile filter, screenshot doc, `side_by_side.py` | Steps 6–9 |
| Architecture spec unchanged | Steps 9, 16 |
| Governed process change, not Lane B; new lane after merge | Global Constraints, Step 16 |
| Remote `narrare`, concrete PR command | Step 16 |

No new test is added: this is a prose-and-tooling change whose evidence is the static negative greps, the full verify log, tree hashes A and B, and the reviewed diff. No new gate is introduced.
