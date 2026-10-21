# Narrare

Local-first, AI-assisted creative writing tool. Python 3.14 · FastAPI · SQLAlchemy
async · PostgreSQL + pgvector · Next.js · TipTap · Tailwind.

## Authority

The v2 architecture spec is the single authority for structure and boundaries:
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`.
The old application under `apps/` and `packages/` is a porting reference; it is not
extended.

## Boundaries

- One capability is one folder under `app/capabilities/<name>/`. A capability never
  imports another capability; shared domain lives in `app/kernel/`.
- Facts live in the capability's `capability.yaml`; every other view of them is
  generated and never hand-edited.
- A capability is done only with a green E2E that drives the real UI, the real backend
  and the real database. The only permitted fake is the LLM provider at its boundary.
- No side effect in the request path beyond the request's own transaction.
- Every user-owned row carries `user_id`; data access goes through the scoped
  repository base.
- Never add a rule, registry, check script, hook, required field or mandatory document.
  Report `NEEDS-APPROVAL` with (1) the failure it prevents, (2) the effort it creates
  per change, (3) the cheaper alternative.

## Language

Source code, comments, tests and developer documentation in English. User-visible
text in en, de and fr through the i18n catalog; a missing key is a build error, not a
review comment.

## Verify

`just check` (fast, changed files) · `just test-file <path>` (inner loop) ·
`just verify` (full gate) · the capability's E2E spec. A gate counts only when its
output was read.

## Agents

`NarrareBuilder` implements. `NarrareReviewer` independently re-runs the gates on a
different model family. `NarrareOperator` owns git and GitHub writes exclusively.
`NarrareArchitect` writes specs and ADRs for irreversible decisions only.
Implementer and reviewer are never the same model.

## Git

Only `NarrareOperator` stages, commits and pushes. `--no-verify` is forbidden.
Conventional commits; internal work is `chore(<scope>)`; `feat`/`fix` require a real
`User-visible:` line that the task provides.
