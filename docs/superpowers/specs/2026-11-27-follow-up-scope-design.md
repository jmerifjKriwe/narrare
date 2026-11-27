# Follow-up scope clarification design

## Intent

A task must not close with unfinished work from its own scope. Work needed to complete the agreed behavior — including correctness, tests and gates — is implemented in the same change. Follow-up issues are reserved for a larger bug with a clearly different subject. A pure NIT is discarded without issue or further triage.

## Goals

- One consistent completion rule in the central agent instructions, the review gate, the standing constraints, the follow-up index and the issue-processing skill.
- No new form, checklist field or automated gate.

## Non-goals

- No change to the existing GitHub label, index, close-out or `Closes #<n>` mechanics.
- No retrospective edits to dated plans or to existing open follow-up issues.
- No change to product behavior.

## Anti-goals

- Turning small but real defects into NITs to avoid work.
- Using a follow-up issue to make an incomplete task look complete.

## Constraints

- `REVIEW.md` is subordinate to `AGENTS.md` and `CONSTRAINTS.md`; they must say the same thing.
- The owner explicitly asked for direct implementation and push to `main`.
- Governance budget: no new mandatory project document or gate is introduced beyond the plan and short design record for this change.

## Approaches

1. **Clarify the existing rule sites** (chosen). Five existing texts receive the same scope test. It changes behavior without adding process overhead.
2. **Add a mandatory completion checkbox and an automated check** (rejected). It would create the very triage overhead the owner wants to avoid for NITs.

## Decisions

- A finding in the task's own scope is fixed in that task even if it was not planned.
- A follow-up issue is opened only for a larger bug with a clearly different subject, before the branch merges.
- `NIT` means no effect on behavior, quality or gates; it is discarded without an issue.
- If in-scope work cannot be completed in the change, the task remains open or blocked; it does not become a follow-up issue.
- Existing follow-up issues and their mechanics stay valid. Future plans must not contain a default closing task that files in-scope findings.

## What is left to the builder

- Apply the wording to `AGENTS.md`, `REVIEW.md`, `docs/_shared/CONSTRAINTS.md`, `docs/superpowers/follow-ups.md` and `.agents/skills/secure-issue-work/SKILL.md`.
- Verify no superseded rule phrases remain and that the new scope test is stated consistently.
- Run the reviewer gate before committing.
