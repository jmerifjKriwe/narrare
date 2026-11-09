# Implementation Plan: React 19 Best-Practices Review

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review `NovelPage.tsx` and `ChatPanel.tsx` against the React 19
checklist, apply only mechanically safe fixes, and turn every other finding into
a labelled follow-up issue and an honest report.

**Architecture:** A read-and-triage pass, not a refactor. The risk rubric in the
spec (§4) decides what may be applied: no observable change, no test change, a
`refactor(...)` commit subject. Everything else is documented.

**Tech Stack:** React 19.3.1, TypeScript, Vite, TanStack Router, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-11-09-react-19-best-practices-review-design.md`

**Dispatch:** implementer `zai-coding-plan/glm-5.3-flash`; reviewer
`opencode-go/deepseek-v4.1-flash`. The reviewer does not edit, stage, commit or
push.

**Task report:** `docs/superpowers/reports/2026-11-09-react-19-review.md`, the
deliverable itself. It is opened in Task 1 and appended to as work happens;
never written from memory at the end.

## Global Constraints

- No behavioral change; no test file may be modified. A fix that would need one
  is not low-risk and becomes a finding.
- No new dependency, gate or standing rule (CONSTRAINTS §8).
- Changes only in the two named files (plus a shared shell file only when a
  specific finding requires it, named in the report).
- English in code, tests and docs.
- Every finding gets a verdict; an empty checklist category is a defect in the
  report, not a clean bill.

---

## Task 1: Read, load the skill, open the report

**Files:**
- Read: `app/capabilities/writing/web/NovelPage.tsx`
- Read: `app/capabilities/chat/web/ChatPanel.tsx`
- Create: `docs/superpowers/reports/2026-11-09-react-19-review.md`

- [ ] **Step 1: Load the checklist skill**

Invoke `vercel-react-best-practices`. If it is unavailable, stop and report it;
the checklist in the spec stands in for its content, but the absence is a
deviation to record.

- [ ] **Step 2: Read both files end to end**

Read `NovelPage.tsx` in full (it is ~1400 lines; use offset/limit, do not skim
from search hits) and `ChatPanel.tsx`. Note line numbers as you go — they will
drift only if a later fix edits the same area, so cite findings by symbol as
well.

- [ ] **Step 3: Open the report with the checklist skeleton**

Create the report with:

- a header (date, scope, base commit `git rev-parse --short HEAD`),
- one row per checklist item from the spec §5, each with
  `Verdict | Finding id | Severity | Risk | Location | Effort | Recommended fix`,
- the findings table in the order encountered,
- empty sections for "Applied fixes", "Follow-up issues", "Not verified".

Findings get ids `F1…` within this pass — local to the report, not an audit
scheme.

- [ ] **Step 4: Commit the skeleton**

```bash
git add docs/superpowers/reports/2026-11-09-react-19-review.md
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "docs(review): open the React 19 findings report"
```

---

## Task 2: Apply the mechanically safe fixes

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Modify: `app/capabilities/chat/web/ChatPanel.tsx`

- [ ] **Step 1: Classify every finding**

For each finding, walk the spec's four low-risk conditions (§4) in order. Mark
the risk class in the report **before** editing. If a condition fails, the
finding is documented, not applied.

- [ ] **Step 2: One fix per commit, each with the gates**

For each applied fix, in isolation:

1. Edit the file.
2. Run `just test-frontend-changed`.
3. Run `just check`.
4. Append a row to "Applied fixes" with the symbol changed and both command
   results.
5. Commit:

```bash
git add app/capabilities/<area>/web/<File>.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor(<area>): <the mechanical change in one sentence>"
```

`refactor` is deliberate: a commit that needs a `User-visible:` line describes
an observable change, which this pass forbids. If the subject wants to be
`fix`, stop — the finding belongs in a follow-up.

- [ ] **Step 3: Run the affected suites**

Run: `just test-e2e writing` and `just test-e2e chat`
Expected: pass, unmodified tests. Record both results in the report.

- [ ] **Step 4: Confirm nothing observable moved**

Run: `git show --stat --oneline HEAD` — the commit touches one component file
only.
Run: `git diff --name-only "$(git merge-base HEAD main)"..HEAD | rg '(test|spec)\.'`
— no output.
If either differs, a fix crossed the rubric; revert it and reclassify.

---

## Task 3: File the follow-ups

**Files:**
- Modify: `docs/superpowers/reports/2026-11-09-react-19-review.md`

- [ ] **Step 1: One issue per surviving finding**

For every finding that is not applied (medium/high risk, or low risk but
deferred), create exactly one issue:

```bash
gh issue create --label follow-up --label "severity: minor" \
  --label "area: writing" --label "kind: test-gap" \
  --title "<file>: <the defect in one line>" \
  --body-file /tmp/opencode/<finding>.md
```

Body carries: location (file and symbol, line at review time), the trigger that
makes it bite, the recommended fix, the effort, and "Found in the review of
2026-11-09; see `docs/superpowers/reports/2026-11-09-react-19-review.md` (F<id>)".

Label rules:

- `severity: minor` = the product survives it; `severity: major` = it should not
  ship again.
- Exactly one `area:` — `writing` for `NovelPage`, `chat` for `ChatPanel`, `web`
  only for shared shell code.
- `kind:` only where the finding's nature is one of the defined kinds
  (`a11y`, `race`, `test-gap`, `flake`, `security`, `i18n`, `docs-drift`).
- Hang each under index **#308** ("Reviews and audits outside a wave"): list the
  numbers in the report's "Follow-up issues" section and leave a comment on #308
  naming them.

- [ ] **Step 2: Verify the issues exist**

Run: `gh issue list --label follow-up --state open --limit 300`
Expected: every number in the report appears, with the labels named there.

---

## Task 4: Close the report

**Files:**
- Modify: `docs/superpowers/reports/2026-11-09-react-19-review.md`

- [ ] **Step 1: Fill the summary**

- Counts by severity and by risk class.
- Applied fixes, each with its commit hash.
- Created issues with numbers and labels.
- The checklist rows that ended `clean` or `n/a`, with the reason.
- "Not verified": anything the reviewer could not exercise (e.g. a branch only
  reachable with a provider that is not configured), stated plainly.
- Deviations from this plan, if any.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/reports/2026-11-09-react-19-review.md
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "docs(review): close the React 19 findings report"
```

---

## Task 5: Verify

- [ ] `just check` — green, output read.
- [ ] `just test-frontend` — green.
- [ ] `just test-e2e writing` — green.
- [ ] `just test-e2e chat` — green.
- [ ] `git diff --name-only <base>..HEAD | rg '(test|spec)\.'` — no output.
- [ ] `gh issue list --label follow-up --state open --limit 300` — the report's
  numbers are all there.

## Review Focus

- A finding that was applied still has no `User-visible:` line in its commit —
  if it does, it was not low-risk.
- The report answers every checklist item explicitly; "nothing found" is a
  verdict, not an omission.
- Every `area:` label names where the code lives, not where the review happened.
- Severity and effort are stated per finding, so the next wave can order them
  without re-reading the code.
- The report's "Not verified" section is non-empty when something could not be
  proved; an empty one is only credible if the reviewer says why.
