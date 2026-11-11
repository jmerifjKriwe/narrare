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

`just check` (fast) · `just test-file <path>` (inner loop) · `just verify` (the
suites the change touches) · `just verify all` (everything) · the capability's E2E.
A gate counts only when its output was read.

`just --list` is the whole command surface, no hidden gates.

## Follow-ups

A finding that survives an implementation becomes a GitHub issue before the branch
merges — one per finding, label `follow-up`, hung under its wave's index issue. The
issue carries the trigger that makes it bite and where it lives; nothing is dropped
for being minor. A fix closes it from its own commit (`Closes #<n>`); an issue that
will not be acted on is closed with the condition that re-opens it, and an index
closes with its last child.

A finding also carries exactly one `area:` label — writing, knowledge, chat, settings,
setup, brand, kernel, web, tooling, ci, docs — naming where it lives, and a `kind:`
label — test-gap, docs-drift, flake, a11y, i18n, race, security — when its nature is
one of those. Area is mandatory, kind is optional, and an index issue carries neither:

    gh issue create --label follow-up --label "severity: minor" \
        --label "area: web" --label "kind: a11y" --body-file …

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

## Frontend & UI

UI and frontend work is implemented and reviewed by subagents
(superpowers:subagent-driven-development), never inline in the coordinating
session: one implementer per task, one reviewer per task, one whole-branch
review at the end. Every dispatch names its implementer and reviewer models
explicitly — an omitted model silently inherits the session's most capable one
and defeats the purpose. The coordinator picks the concrete models at dispatch
time; the standing preference below is the default until the owner changes it.

Standing preference (2026-11-11, owner decision, rev. 3; supersedes 2026-11-09):
the agent-model assignment for narrare is — Coordinator
`opencode-go/mimo-v2.6-pro`, Coding Agent `opencode-go/deepseek-v4.1-flash`,
Reviewer `zai-coding-plan/glm-5.3`, UI Agent
`opencode-go/minimax-m3.1-flash`. UI tasks are implemented by the UI Agent
and reviewed by the Reviewer.

Keep the PR updated while the work continues: push after every green task
group, so review never faces a wall of commits at the end.

## Git

`--no-verify` and force push are forbidden. Conventional commits. The types that
reach the release notes — `feat`, `fix`, `perf`, `docs` — need a real
`User-visible:` line that the task provides; the commit-message hook refuses a
missing or placeholder value (`none`, `n/a`, `-`, `nothing`, `tbd`). Work no user
can observe — internal production code, tooling, CI, tests, dependencies, plans,
specs, follow-ups, process — uses a hidden type: `chore`, `refactor`, `test`,
`ci`, `build` or `style`. Development documentation is `chore(docs)`; only
documentation a user reads is `docs`. Scopes that name development work (`ci`,
`tooling`, `tests`, `e2e`, `gates`, `repo`, `deps`, `hooks`, `plan`, `process`,
`follow-ups`) belong under a hidden type even when the change is a feature or a
fix to that tooling. Nothing is committed before the review is
green. A commit made through an agent ends with the trailer
`Assisted-by: OpenCode (<model>)`, added with `git commit --trailer`; author and
committer stay the human.

A branch lands as a merge commit: its commits reach `main` unchanged and are the
changelog entries release-please reads. A PR title is none of them, and it is deliberately
**not** conventional: GitHub writes the title into the merge commit's body, and a title
that reads like a commit makes release-please parse it as a second change — the duplicate
lines in `v0.3.0` and `v0.3.1` are exactly that. The title is the sentence reviewers read:
plain language, naming the change, not the work package: no `Phase 0`, `Wave 1`, `P1`,
`T17`, no programme name; the plan and `spec §3.5` belong in the body as references. The
commit subjects carry the grammar, and the local commit-message hook is what checks it. Work no
user can observe states its effect — a build that can no longer go red — and never
claims a benefit it lacks. A commit whose content is the plan may name the phase.
