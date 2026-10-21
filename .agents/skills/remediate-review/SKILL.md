---
name: remediate-review
description: End-to-end remediation of a single audit review file (technical or content) — analyze findings (including prose without an existing task), triage which gaps genuinely warrant a task, create tasks for those (with confirmation), implement each task, commit with meaningful conventional-commit messages, mark resolved with Implementation+Enforcement evidence, open a PR, and drive CI green. Use when the user says "analysiere/bearbeite review-NN", "audit-datei durchgehen", "AUFG-Aufgaben umsetzen", "Lücken im Review finden", or references a file under _audit/results/technical-review/ or _audit/results/content-review/.
argument-hint: "[path to review file under _audit/results/]"
user-invocable: true
metadata:
  opencode/autoinvoke: false
---

The user wants to remediate a review file end-to-end. Target: `$ARGUMENTS`

`$ARGUMENTS` is a path to a review file under `_audit/results/`. Resolve it to an
absolute path. Accept the short form (`review-01-architektur`,
`cr-01-prompt-quality`) by matching under `_audit/results/{technical,content}-review/`.

Work through the phases below. Do not skip the analysis and gap detection — the point
of this skill is not just "do the listed tasks", it is to catch problems the audit
identified but never turned into a task (including ones only described in prose,
outside any `### [AUFG…]` block), to filter out the ones that don't actually
warrant a task, and to prevent the class of failure only where the underlying
cause is genuinely structural — not to manufacture governance for one-off issues.

Review files, task entries, and evidence stay in **German** (matching the
source file's language). Commit messages, PR titles/bodies, and code comments
stay in **English**, matching this skill's and the project's convention. Do not
mix languages within a single artifact.

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
   - ID regex to capture both: `(?:CR-)?AUFG-\d{2,}-\d{2,}` (do not assume the
     numbering stays two digits forever — match greedily, not `\d{2}` exactly).
3. Ensure a clean starting point: run `git status`. If it is not clean, **stop
   and ask the user** how to handle the pending changes (commit, stash, or
   abort) — do not decide unilaterally to commit or stash work that may be
   unrelated to this remediation. Once clean, `git switch main`, `git pull`,
   then create `chore/review-NN-<topic>-fixes` where `<topic>` is a 2–4 word
   kebab slug drawn from the file's theme (e.g. `chore/review-04-dx-tooling-fixes`).

## Phase 1 — Full analysis (not just the listed tasks)

Read the **entire** file: the header blockquote (context, author role, "do not
reopen these" list), every `## N.` Befunde section, root-cause paragraphs, all
tables (Checks, Re-Check status, refactoring candidates), the closing summary
paragraphs (`Gesamtbewertung`, `Zusammenfassung` — these often carry the
sharpest root-cause language), `## Aufgaben`, and `## Abschluss-Status`. The
resolution vocabulary of the v1 era is archived in git history
(`docs/development/finding-lifecycle.md` at `48e7d7d4^`).

Build a task inventory. For every `(?:CR-)?AUFG-NN-MM`, record:
- the ID, title, and section it lives in;
- **status** — detected from markers, not from optimism:
  - done = `ERLEDIGT` / `Erledigt` / `Umgesetzt` / `✅ Resolved` / `implemented`
    / `enforced` / checkbox `[x]`;
  - open = `OFFEN` / `open` / `identified` / `triaged` / checkbox `[ ]`;
  - partial = mixed (some `[x]`, some `[ ]`, or `WEITGEHEND GELÖST`).
  - If the status marker doesn't match any known vocabulary (e.g. a new phrase
    that isn't in this list), do **not** silently guess open or done. Flag it
    as "status unclear" in the inventory and ask the user, or infer only from
    unambiguous secondary evidence (e.g. all acceptance criteria are `[x]` and
    there's an Exit-evidence block) — never from tone alone.
- the acceptance criteria and what evidence the file already claims.

### Gap detection (including prose without a task)

Walk every Befund bullet, root-cause paragraph, refactoring-candidate table
row, and closing-summary sentence that describes a *problem*, whether or not
it sits inside a `### [AUFG…]` block. A problem without a corresponding task is
a gap candidate. Common gap shapes:
- a root-cause note with no follow-up task;
- a ⚠️ row in a quality table, or an unreferenced row in a "Refactoring
  Candidates" table, that nobody actioned;
- a Befund that says "should be X" but has no `### [AUFG…]`;
- a sentence hedged as "no current violation, but a risk if…" or "should not
  be marketed as X as long as Y isn't proven" — these read like acknowledged
  risk, not settled fact, and are exactly the kind of prose finding that tends
  to get lost;
- an acceptance criterion that references work the task does not actually cover.

**Gap-relevance triage.** Not every unbetasked sentence deserves a task. Before
adding anything to the Phase 2 batch, sort each gap candidate into one of
three classes:

- **A — Real gap (task warranted):** A root-cause statement backed by concrete
  evidence (file:line, graph metric, checker result) describing a *current*
  problem, even if no gate currently fails on it. Typical pattern: "X has only
  Y callers per the graph, but Z would be required", or "the checker is green,
  but it doesn't actually verify Z." → task candidate for Phase 2.
- **B — Observed risk / knowingly accepted:** The text itself already frames it
  as non-current or conditional ("not a current violation, but…", "risk for
  the future if…", "should not be X as long as Y isn't shown"). Do **not**
  automatically turn these into tasks. Collect them separately as
  "Observations without a task" and present them to the user in Phase 2 for a
  decision: either create a task, or record it explicitly in the review file
  as `Accepted Risk (reason: …)`. The user decides — the skill does not assume.
- **C — Stylistic/hypothetical, no evidence:** No file/line reference, no
  concrete consequence named. Ignore; don't even carry it forward as an
  observation.

**Cause analysis — gated by a structural-vs-one-off test, not automatic.**
For each Class-A gap and each existing open task, before proposing any
prevention measure at all, first decide whether prevention is warranted.

Ask: **is the root cause structural, or a one-off?**

Structural (prevention is warranted) if *at least one* holds:
- the same root-cause pattern appears ≥2 times in this review (several
  findings sharing the same explanation is a pattern, not two coincidences);
- an existing SSOT document or an existing checker was *circumvented* rather
  than simply missing (e.g. "the rule is written in CONSTRAINTS.md but nothing
  checks it") — that's an enforcement hole, not chance;
- it is a regression of something a previous review or ADR already tried to fix.

One-off (**no** new prevention) if:
- it's a single human mistake or edge case with no indication it repeats;
- the fix itself already provides adequate protection (e.g. a regression test
  for this exact case covers the risk without needing a new governance layer).

For one-offs: **just fix it.** A single line in the review file suffices —
"Cause: one-off, no structural prevention needed" — no ADR, no new checker, no
RC/P-numbered essay.

**Prevention budget (only for structural causes):**
- **One** root cause → **one** prevention measure, not several. If three gaps
  share a cause, they get one shared prevention, not three.
- Prefer extending an **existing** checker/gate with one additional check
  before proposing a new document, a new ADR category, or a new process step.
  A brand-new checker/ADR is only justified when no existing gate can plausibly
  be extended to catch this class of error.
- New prevention measures start **warning-only with a clean baseline**
  (ratchet), never immediately blocking — this stops the prevention itself
  from becoming the next overhead task someone has to defuse.
- Before proposing a prevention in Phase 2, state it in **one sentence**:
  "Checker X is extended to check Y, which prevents failure class Z." If it
  takes more than one sentence to explain, the measure is too big — shrink it
  instead of justifying it at length.

## Phase 2 — Close the gaps (create tasks, then CONFIRM before implementing)

This phase drafts task entries and observations — no production code yet, and
nothing is committed until the user has confirmed.

1. Prepare, in memory/scratch (not yet written into the review file):
   - **New AUFGs (Class A):** for each, pick the next free `MM` within that
     review's numbering. **Check for collisions** — IDs are scoped per review,
     not globally unique (the `AUFG-01-03` collision is a documented defect;
     re-home to the next free id rather than overloading). Draft: context, root
     cause, acceptance criteria, priority, area, and — if a structural cause
     was identified — the one-sentence prevention measure.
   - **Observations without a task (Class B):** problem description, why it was
     triaged as "accepted risk" candidate rather than a task, and the proposed
     `Accepted Risk` note text.
2. Present **all** drafts to the user in one batch, split into "New AUFGs" and
   "Observations — accept as risk or turn into a task?", and **wait for
   confirmation before writing anything to the file or to Phase 3**.
3. Only after confirmation:
   - Write the confirmed new AUFGs into the review file's `## Aufgaben`
     section, in that file's native format (header + `**Status:**`/checkboxes
     for technical; bold bullet + `**Status DATE:**` for content).
   - Write confirmed `Accepted Risk` notes for the observations the user chose
     not to convert into tasks.
   - Drop anything the user rejects — do not write it into the file, and note
     the rejection only in your own scratch notes / summary to the user, not
     in the review file's history.
4. Commit the review-file additions as a clean Conventional Commit that
   describes *what* was registered — no task IDs in the message (traceability
   lives in the review file, not the git history):
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
   knowledge-graph tools (`code-review-graph_*` / `codebase-memory-mcp_*` —
   whichever is actually registered in this environment; fall back to
   Grep/Glob/Read only if neither is available) over Grep/Glob/Read to find
   callers and impact before changing code.
2. Where the cause analysis in Phase 1 identified a genuinely structural cause
   with an agreed one-sentence prevention, add it now: extend the existing
   checker/gate (preferred) or add a narrowly scoped new one, warning-only with
   a clean baseline. This is what lets the task reach `✅ Resolved` rather than
   stalling at `implemented`. Do not add prevention machinery beyond the one
   sentence agreed in Phase 2 — if the implementation reveals the fix needs
   more scaffolding than that, stop and re-confirm with the user rather than
   silently expanding scope.
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

**Resolution guardrail (v1 vocabulary, archived in git history):**
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
- any new AUFGs created from gaps, flagged as new;
- any `Accepted Risk` observations recorded without a task, with the reason;
- the prevention measure(s) actually added (checker/ADR) and what class of
  failure each blocks — and, if a structural cause was found but deliberately
  left unaddressed (e.g. deferred), say so explicitly instead of silently
  omitting it;
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
- **Prose findings count too.** A problem described only in running text, a
  refactoring-candidate table row, or a closing summary is just as much a gap
  as a missing `### [AUFG…]` — don't limit gap detection to explicit task blocks.
- **Not every gap becomes a task.** Findings the review itself already frames
  as conditional or non-current ("no violation today, but…") go through the
  Class A/B/C triage and, for Class B, get a user decision — task or
  documented accepted risk — rather than an automatic task.
- **No prevention overhead for one-offs.** Not every root cause needs an
  ADR/governance answer. A single, plausibly explained mistake gets fixed and
  documented — not turned into a prevention program. Prevention is reserved
  for patterns that repeat or that circumvented an existing SSOT/gate, and
  even then it's scoped to one sentence and, where possible, an extension of
  an existing checker rather than a new one.
- **Review file is the lifecycle SSOT.** All exit evidence goes in the review
  file — keep it current.
- **IDs are per-review.** `AUFG-NN-MM` is scoped to review `NN` — always check
  existing AUFG ids in the review file for collisions before minting a new id.
- **No silent baselining.** Editing a checker's expected-count to make it pass
  is a real change — surface it explicitly to the user with the reason.
- **No silent stashing/committing of unrelated work.** If `git status` isn't
  clean at Phase 0, ask the user how to handle it rather than deciding for them.
- **Clean git history, no ticket noise.** Commit messages are Conventional
  Commits that describe *what changed*. AUFG/CR-AUFG ids, review numbers, and
  other task identifiers are forbidden in commit messages — they live in the
  review file and the PR body, where traceability belongs. The
  git log should read like normal project history.
- **Language discipline.** Review-file content (task entries, evidence,
  accepted-risk notes) stays in German, matching the source file. Commit
  messages, PR text, and code comments stay in English. Don't mix within one
  artifact.
- **Stop and ask, don't power through.** If CI is unfixably red, a diagnosis is
  uncertain, a status marker doesn't match known vocabulary, or a "resolved"
  claim can't meet the Implementation+Enforcement bar, stop and report — do
  not paper over it.
