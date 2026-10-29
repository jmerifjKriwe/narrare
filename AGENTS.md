# Narrare

Local-first, AI-assisted creative writing tool. Python 3.14 · FastAPI · SQLAlchemy
async · PostgreSQL + pgvector · Vite + React · TanStack Router · TipTap · Tailwind.

The v2 architecture spec is the single authority for structure and boundaries:
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`. The old app is
gone; git history is its archive. `docs/` keeps the design record, not a second set of
rules.

## Rules

The five standing rules, the shape of a capability, the reading order and the
governance budget are normative in
[`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md) and are
not restated here — read that page before your first change. A change that
violates one of its rules is a review finding, not a style question.

## Verify

`just check` (fast) · `just test-file <path>` (inner loop) · `just verify` (full gate) ·
the capability's E2E. A gate counts only when its output was read.

`just --list` is the whole command surface: 22 recipes, no hidden gates.

## Follow-ups

A finding that survives an implementation becomes a GitHub issue before the branch
merges — one per finding, label `follow-up`, hung under its wave's index issue. The
issue carries the trigger that makes it bite and where it lives; nothing is dropped
for being minor. A fix closes it from its own commit (`Closes #<n>`); an issue that
will not be acted on is closed with the condition that re-opens it, and an index
closes with its last child.

The list is `gh issue list --label follow-up --state open --limit 300`. Index issues
carry `follow-up-index` and sit in `docs/superpowers/follow-ups.md` beside the decided
findings; a new wave adds its row there when it opens. That page is not a second list
of open work.

## Plan mode

Plan mode loads the `brainstorming` skill before the first design question. Its
artifacts stay in `~/.opencode/plan`; the build session moves the design doc into
`docs/superpowers/specs/` and the plan into `docs/superpowers/plans/`, and commits
both. Move, never copy: one state, not two.

## Tools (optional)

`just callers <path> <symbol>` answers "who calls X" from pyright's own call
hierarchy — the analysis `just typecheck` already runs. It sees through the
`service: Service = Depends(...)` receivers that a separate index cannot, and
there is nothing to keep fresh. Everything else (where a symbol is defined,
which files mention it) is `rg`. Neither is a required step: both are cheaper
than reading when grep already answers.

A whole-repo index was measured against this repo on 2026-10-29 and removed:
codebase-memory-mcp needed a re-index nobody ran (five days and 201 commits
behind), its extractor found 0 of 3 dependency-injected callers, and its tool
schemas cost about 4.5k tokens of every session whether used or not. Do not add
a mandatory rule or gate for tooling of this kind (the governance budget, spec §8).

## Git

`--no-verify` and force push are forbidden. Conventional commits; `feat`/`fix` need a
real `User-visible:` line that the task provides. Nothing is committed before the
review is green.

A branch lands as a merge commit: its commits reach `main` unchanged and are the
changelog entries release-please reads. A PR title is none of them; it is the sentence
reviewers read, and it follows the same `type(scope): effect` grammar. Title and
subject name the change, not the work package: no `Phase 0`, `Wave 1`, `P1`, `T17`, no
programme name; the plan and `spec §3.5` belong in the body as references. Work no
user can observe states its effect — a build that can no longer go red — and never
claims a benefit it lacks. A commit whose content is the plan may name the phase.
