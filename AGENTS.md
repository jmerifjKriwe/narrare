# Narrare

Local-first, AI-assisted creative writing tool. Python 3.14 · FastAPI · SQLAlchemy
async · PostgreSQL + pgvector · Next.js · TipTap · Tailwind.

The v2 architecture spec is the single authority for structure and boundaries:
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`. The old app is
gone; git history is its archive. `docs/` keeps the design record, not a second set of
rules.

## Rules

- One capability is one folder under `app/capabilities/<name>/`. A capability never
  imports another capability; shared domain lives in `app/kernel/`.
- A capability is done only with a green E2E that drives the real UI, the real backend
  and the real database. The only permitted fake is the LLM provider at its boundary.
- No side effect in the request path beyond the request's own transaction.
- Every user-owned row carries `user_id`; data access goes through the scoped
  repository base.
- English in code, comments, tests and developer documentation. User-visible text in
  en, de and fr through the i18n catalog; a missing key is a build error.
- Never add a rule, registry, check script, hook, required field or mandatory document.
  Report `NEEDS-APPROVAL` with the failure it prevents, the effort it creates per
  change, and the cheaper alternative.

## Verify

`just check` (fast) · `just test-file <path>` (inner loop) · `just verify` (full gate) ·
the capability's E2E. A gate counts only when its output was read.

`just --list` is the whole command surface: 22 recipes, no hidden gates.

## Agents

`NarrareBuilder` builds and commits. `NarrareReviewer` checks it on a different model.
That is the whole layer.

## Git

`--no-verify` and force push are forbidden. Conventional commits; `feat`/`fix` need a
real `User-visible:` line that the task provides.
