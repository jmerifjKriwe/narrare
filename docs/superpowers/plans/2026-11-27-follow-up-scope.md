# Follow-up Scope Clarification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every task finish its own scope, reserve follow-up issues for larger bugs with a clearly different subject, and discard pure NITs without overhead.

**Architecture:** One documentation seam: the completion rule is stated once and the reviewer gate, follow-up index and issue-processing skill point to the same test. No product code changes.

**Tech Stack:** Markdown, repository agent instructions.

**Spec:** `docs/superpowers/specs/2026-11-27-follow-up-scope-design.md`

## Global Constraints

- A task is complete only when the work in its own scope is done.
- Findings needed for the agreed behavior, correctness, tests or gates belong in the same change.
- A follow-up issue is opened only for a larger bug with a clearly different subject.
- A NIT has no effect on behavior, quality or gates; it is discarded without an issue.
- An in-scope flake blocks completion; only a larger flake with a clearly different subject becomes a follow-up issue.
- Existing follow-up issues and GitHub mechanics remain valid; dated plans are not edited.
- Nothing is committed before the reviewer gate is green.

## Review Focus

- An in-scope finding appears late: it is fixed in the same change, not filed — Task 1, step 2 (`AGENTS.md` scope rule).
- A reviewer sees a small real defect: it blocks the task rather than becoming an issue — Task 1, step 3 (`REVIEW.md` gate).
- A cosmetic suggestion arrives: it is discarded without an issue or triage — Task 1, steps 2–4 (NIT definition).
- A larger, clearly foreign bug appears: it becomes a `follow-up` issue before merge — Task 1, steps 2 and 5 (exception and preserved mechanics).
- An in-scope flake is deferred: it blocks the task instead — Task 1, step 6 (`CONSTRAINTS.md`).
- The old "nothing is dropped for being minor" rule survives in one of the five texts: contradiction — Task 1, step 7 (grep checks).

---

### Task 1: One consistent completion rule

**Files:**
- Create: `docs/superpowers/specs/2026-11-27-follow-up-scope-design.md`
- Create: `docs/superpowers/plans/2026-11-27-follow-up-scope.md`
- Modify: `AGENTS.md:34-44`
- Modify: `REVIEW.md:30-44`
- Modify: `docs/_shared/CONSTRAINTS.md:27-35`
- Modify: `docs/superpowers/follow-ups.md:3` and `:45-48`
- Modify: `.agents/skills/secure-issue-work/SKILL.md:165-167`

**Interfaces:**
- Consumes: the short design record above.
- Produces: no code interfaces; the shared phrase `larger bug with a clearly different subject` is the rule anchor across the instruction files, with `CONSTRAINTS.md` stating its flake-specific form.

- [ ] **Step 1: Ensure the two record files exist and match the approved design**

Both files are created with the content written in this session; no further decision is left to the implementer.

- [ ] **Step 2: Replace the central rule in `AGENTS.md`**

Replace `AGENTS.md:36-39` ("A finding that survives an implementation ... nothing is dropped for being minor.") with a completion rule stating:
  - a task is complete only when its own scope is finished;
  - findings needed for behavior, correctness, tests or gates belong in the same change;
  - only a larger bug with a clearly different subject becomes a `follow-up` issue before merge, one per finding, with the existing trigger/where body and wave index;
  - a NIT with no effect on behavior, quality or gates is discarded without an issue or triage.

Keep the Lane B sentence, the `Closes #<n>` close-out and all lines from "Processing issues" onward unchanged, except changing "A finding from a Lane B change" to "A follow-up from a Lane B change".

- [ ] **Step 3: Replace the review gate in `REVIEW.md`**

Replace `REVIEW.md:41-42` with an Important item that flags a task closing with unfinished work from its own scope, names the same NIT definition and the same sole issue exception, and keeps `area:` mandatory and `kind:` optional. Leave the Nit section otherwise unchanged.

- [ ] **Step 4: Update the follow-up index rule text**

In `docs/superpowers/follow-ups.md`, change line 3 so new issues are described as larger bugs with a clearly different subject and earlier findings stay tracked. In lines 45–48, replace "Nothing is dropped for being minor" with the NIT discard rule; keep severity definitions, the index row instruction and `Closes #<n>` unchanged.

- [ ] **Step 5: Update the issue skill's scope discipline**

Replace `.agents/skills/secure-issue-work/SKILL.md:165-167` so the issue's own scope is finished first, a larger bug with a clearly different subject becomes a `follow-up` issue, and a pure NIT is discarded without issue or further triage. Leave every other phase unchanged.

- [ ] **Step 6: Update the standing Flakes rule**

Replace `docs/_shared/CONSTRAINTS.md:33-35` so a flake in the task's own scope blocks completion and only a larger flake with a clearly different subject becomes a `follow-up` issue. Keep the ban on skipping, re-rolling and timeout raising and the close-out sentence unchanged.

- [ ] **Step 7: Verify the rule is consistent**

Run:

```bash
git diff --check
rg -n "nothing is dropped for being minor|surviving finding with no|if you discover related work|any flake that cannot be fixed" AGENTS.md REVIEW.md docs/_shared/CONSTRAINTS.md docs/superpowers/follow-ups.md .agents/skills/secure-issue-work/SKILL.md
```

Expected: `git diff --check` is clean; the `rg` command prints no matches.

Then run:

```bash
rg -n "larger bug with a clearly different subject" AGENTS.md REVIEW.md docs/superpowers/follow-ups.md .agents/skills/secure-issue-work/SKILL.md
```

Expected: a match in each of the four files. Read `git diff` and confirm the GitHub labels, index rows, close-out and dated follow-ups are unchanged.

- [ ] **Step 8: Reviewer gate**

A fresh reviewer reviews the whole uncommitted diff against this plan and the spec before any commit.

- [ ] **Step 9: Commit and push**

```bash
git add AGENTS.md REVIEW.md docs/_shared/CONSTRAINTS.md docs/superpowers/follow-ups.md .agents/skills/secure-issue-work/SKILL.md docs/superpowers/specs/2026-11-27-follow-up-scope-design.md docs/superpowers/plans/2026-11-27-follow-up-scope.md
git commit -m "chore(docs): clarify follow-up scope" --trailer 'Assisted-by: OpenCode (hy4-flash-free)'
git push
```

Expected: one commit on `main`, pushed to `narrare/main`.
