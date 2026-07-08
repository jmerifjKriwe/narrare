---
name: remediate-review
description: End-to-end remediation of a single audit review file (technical or content) — analyze findings, detect problems that have no AUFG task and create one (with confirmation), implement each task, commit with meaningful conventional-commit messages, mark resolved with Implementation+Enforcement evidence, open a PR, and drive CI green. Use when the user says "analysiere/bearbeite review-NN", "audit-datei durchgehen", "AUFG-Aufgaben umsetzen", "Lücken im Review finden", or references a file under _audit/results/technical-review/ or _audit/results/content-review/.
argument-hint: "[path to review file under _audit/results/]"
user-invocable: true
---

The user wants to remediate a review file end-to-end. Target: `$ARGUMENTS`

`$ARGUMENTS` is a path to a review file under `_audit/results/`. Resolve it to an
absolute path. Accept the short form (`review-01-architektur`,
`cr-01-prompt-quality`) by matching under `_audit/results/{technical,content}-review/`.

Work through the phases below. Do not skip the analysis and gap detection — the point
of this skill is not just "do the listed tasks", it is to catch problems the audit
identified but never turned into a task, and to prevent the class of failure.

---

## Phase 0 — Pre-flight & branch

1. Confirm the file exists and is under `_audit/results/technical-review/` or
   `_audit/results/content-review/`. If not, stop and ask.
2. Determine the review type and numbering scheme:
   - **Technical** (`review-NN-*.md`) → tasks are `AUFG-NN-MM`, written as
     `### [AUFG-NN-MM] Title` headers with a `**Status:**` / `**Re-Check:**` line
     and `- [ ]` / `- [x]` acceptance-criteria checkboxes.
   - **Content** (`cr-NN-*.md`) → tasks are `CR-AUFG-NN-MM`, written as
     `- **CR-AUFG-NN-MM:** …` bullets with an inline `**Status DATE:**` marker.
   - ID regex to capture both: `(?:CR-)?AUFG-\d{2}-\d{2}`.
3. Ensure a clean starting point: `git status` must be clean (commit or stash any
   pending work first). `git switch main`, `git pull`, then create
   `chore/review-NN-<topic>-fixes` where `<topic>` is a 2–4 word kebab slug drawn
   from the file's theme (e.g. `chore/review-04-dx-tooling-fixes`).

## Phase 1 — Full analysis (not just the listed tasks)

Read the **entire** file: the header blockquote (context, author role, "do not
reopen these" list), every `## N.` Befunde section, root-cause paragraphs, all
tables (Checks, Re-Check status, refactoring candidates), `## Aufgaben`, and
`## Abschluss-Status`. Also skim `docs/development/finding-lifecycle.md` for the
resolution vocabulary.

Build a task inventory. For every `(?:CR-)?AUFG-NN-MM`, record:
- the ID, title, and section it lives in;
- **status** — detected from markers, not from optimism:
  - done = `ERLEDIGT` / `Erledigt` / `Umgesetzt` / `✅ Resolved` / `implemented`
    / `enforced` / checkbox `[x]`;
  - open = `OFFEN` / `open` / `identified` / `triaged` / checkbox `[ ]`;
  - partial = mixed (some `[x]`, some `[ ]`, or `WEITGEHEND GELÖST`).
- the acceptance criteria and what evidence the file already claims.

**Gap detection — the core of this skill.** Walk every Befund bullet, Root-Cause
paragraph, and table row that describes a *problem*, and check whether a
corresponding AUFG task exists. A problem without a task is a gap. Common gap
shapes:
- a Root-Cause note with no follow-up task;
- a ⚠️ row in a quality table that nobody actioned;
- a Befund that says "should be X" but has no `### [AUFG…]`;
- an acceptance criterion that references work the task does not actually cover.

**Cause analysis (explicit deliverable).** For the gaps (and ideally for the
existing tasks too), answer: *why did this slip through despite
`docs/_shared/CONSTRAINTS.md` and `finding-lifecycle.md`?* Typical answers:
missing CI gate, a check that is warning-only, a doc that is SSOT but not
enforced, a contract without a checker, "documented ≠ implemented". The
prevention becomes its own AUFG (usually a ratcheted checker or an ADR).

## Phase 2 — Close the gaps (create tasks, then CONFIRM before implementing)

This phase creates task entries only. No production code yet.

For each gap:
1. Pick the next free `MM` within that review's numbering. **Check for collisions**
   — IDs are scoped per review, not globally unique (the `AUFG-01-03` collision is
   a documented defect; re-home to the next free id rather than overloading).
2. Add the task to the review file's `## Aufgaben` section in that file's native
   format (header + `**Status:**`/checkboxes for technical; bold bullet +
   `**Status DATE:**` for content). Include: context, root cause, acceptance
   criteria, priority, area.

Present **all** new AUFGs to the user in one batch (ID, problem, proposed scope,
proposed prevention) and **wait for confirmation before Phase 3**. Do not
implement a gap task the user rejects — drop it and note the rejection.

Commit the review-file additions as a clean Conventional Commit that
describes *what* was registered — no task IDs in the message (traceability lives
in the review file, not the git history):
`docs(audit): register prompt-quality gaps from cr-01`.

## Phase 3 — Implement (loop, one commit per task)

For each open AUFG — both the original tasks and the confirmed new ones — in a
sensible order (dependencies first):

1. Implement to the project's standards. The authoritative rules live in
   `docs/_shared/CONSTRAINTS.md` and `AGENTS.md`; do not restate them here, just
   follow them. The load-bearing ones for this work: RULE-03 (contract before
   implementation), RULE-04 (modularize, don't compress — extract a module near
   the size limit instead of squeezing lines), RULE-06 (one responsibility per
   file; routers delegate, no business logic in routers). Prefer the code
   knowledge-graph tools (`code-review-graph_*` / `codebase-memory-mcp_*`) over
   Grep/Glob/Read to find callers and impact before changing code.
2. Where the cause analysis pointed at a missing enforcement, add it: a
    CI-blocking checker or regression test. This is what lets the task
    reach `✅ Resolved` rather than stalling at `implemented`.
3. Commit **each task separately** with a meaningful Conventional Commit message.
   The subject (and ideally the body too) must **describe what changed, not which
   ticket drove it.** AUFG/CR-AUFG ids, review numbers, and other task
   identifiers go in the review file and the PR body — **never in
   the commit message.** The git log should read like clean project history.

   Examples:
   `fix(prompts): add schema-level confidence/severity gating to review + readability analysis`
   `refactor(editor): split WritingPipeline.generate, extract _mode_dispatch`
    `feat(web): add session recovery with preserved editor state`

   **Forbidden** in commit messages:
   - task IDs of any kind: `AUFG-01-03`, `CR-AUFG-01-08`, `review-NN`,
     `(NN-MM)`, `resolve …-01..08`;
   - low-information subjects: `AUFG-04-02 umgesetzt`, `fix: review`,
     `chore: aufg`, `resolve CR-01`.
   If you cannot write a descriptive subject without a ticket id, the commit is
   probably doing two things — split it.

## Phase 4 — Verify locally before pushing

Run the gates that match what you touched, then the full suite once at the end:
`just check` (architecture + size + adoption), `just check-architecture`,
`just lint`, `just typecheck`, `just test-unit` / `just test-frontend` as
relevant, then `just test`. Red is not skippable — fix the cause, do not weaken
the assertion. If a check is genuinely wrong, say so explicitly to the user
rather than silently editing a baseline.

## Phase 5 — Document resolution (finding-lifecycle compliant)

For each resolved AUFG, update the review file in its native format:
- technical: a `**Re-Check DATE:** **ERLEDIGT DATE** — <evidence>` line under the
  header, tick every acceptance criterion `[x]`, and add to `## Abschluss-Status`.
- content: an inline `**Status DATE:** implemented via …` on the bullet.
- both: the evidence must be **concrete** — file paths that exist on disk, the
  checker name and its PASS result, test counts. No "now works" / "fixed".

**Resolution guardrail (from `docs/development/finding-lifecycle.md`):**
`✅ Resolved` requires **Implementation + Enforcement**. These anti-patterns are
forbidden and must not be claimed as resolved:
- "ADR proposed → resolved" (an ADR alone caps a finding at `accepted`);
- "template exists → runtime uses it" (verify the runtime consumer);
- "check is green → done" (a green check covers only its inspected layer);
- "implemented → resolved" without a CI-blocking checker or regression test.

Then update each resolved AUFG task's entry in the review file: set its status to
`resolved (YYYY-MM-DD)`, add a `Resolved` row and an **Exit evidence** block
(ADR, file paths, checker + ratchet baseline, PR #). The review file is the
lifecycle SSOT — all exit evidence lives there.

## Phase 6 — Commit docs, open PR

Commit the doc updates separately from code as a clean Conventional
Commit. Same rule as Phase 3: describe *what* the change does, **no task ids**:
`docs(audit): resolve cr-01 + verification postscript`.

Push the branch and `gh pr create`. PR body must list:
- resolved AUFG ids (original + gaps) with one-line evidence each;
- any new AUFGs created from gaps, flagged as new.
- the prevention measure (checker/ADR) and what class of failure it blocks;
- links to the key files/ADRs.

## Phase 7 — Drive CI green, then STOP before merge

Watch CI (`gh pr checks --watch`). Fix failures by editing the branch and pushing
— do not disable checks. When CI is green, **stop here**: print the PR URL and a
one-paragraph summary (what was resolved, what was newly registered, what is
prevented going forward). **Do not merge.** Wait for explicit user confirmation.

After the user confirms the merge:
1. Merge via the project's usual method (check the PR or ask — do not assume
   squash vs. merge).
2. `git switch main`, `git pull`, delete the branch locally and on the remote.
3. If the user queued another review file, loop back to Phase 0 for it.

---

## Guardrails

- **Evidence over intent.** Never mark a task resolved without files-on-disk +
  enforcement evidence. "Documented" ≠ "implemented"; "check green" ≠ "done".
- **Review file is the lifecycle SSOT.** All exit evidence goes in the review
  file — keep it current.
- **IDs are per-review.** `AUFG-NN-MM` is scoped to review `NN` — always check
  existing AUFG ids in the review file for collisions before minting a new id.
- **No silent baselining.** Editing a checker's expected-count to make it pass
  is a real change — surface it explicitly to the user with the reason.
- **Clean git history, no ticket noise.** Commit messages are Conventional
  Commits that describe *what changed*. AUFG/CR-AUFG ids, review numbers, and
other task identifiers are forbidden in commit messages — they live in the
review file and the PR body, where traceability belongs. The
  git log should read like normal project history.
- **Stop and ask, don't power through.** If CI is unfixably red, a diagnosis is
  uncertain, or a "resolved" claim can't meet the Implementation+Enforcement bar,
  stop and report — do not paper over it.
