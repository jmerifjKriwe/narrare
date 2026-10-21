# Contributing to Narrare

Thanks for your interest in contributing! **Narrare** is an AI-powered creative
writing environment — local-first, fully customizable, and MIT-licensed. We
welcome contributions of all kinds: bug reports, features, documentation, and
more.

## Getting Started

Choose a setup path depending on what you plan to work on:

| Command | Best for | Notes |
|---------|----------|-------|
| `just dev-setup` | Full-stack work including NLP/analysis features | Installs spaCy + language models (~200 MB extra). ~10 min. |
| `just dev-setup-min` | Frontend, core, or agent work (no NLP) | ~200 MB lighter, faster setup. Add NLP later with `just install-nlp-models`. |

Both commands create your `.env`, install dependencies, start Docker services
(PostgreSQL + pgvector, Redis), run migrations, and seed a dev user.

**DevContainer (VS Code):** Open the repository in VS Code and click
"Reopen in Container" — the container includes Python 3.14, Node.js, uv, just,
and all extensions pre-configured.

## Branch Model

- All work happens on **feature branches** created from `main`.
- Branch naming uses a prefix followed by a short description:
  `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`
  (e.g. `feat/kb-versioning`, `fix/login-timeout`).
- Pull requests are **squash-merged** into `main`. The squash commit message
  must follow Conventional Commits (see below).
- Keep branches focused — one logical change per branch makes review faster.

## Conventional Commits

Every commit message follows the [Conventional Commits](https://www.conventionalcommits.org/)
format. A pre-commit hook validates the message automatically.

```
feat(core): add prompt cascade resolution

User-visible: Prompt cascades can be resolved per project.
fix(api): resolve session timeout on idle
docs: update deployment guide
chore(deps): bump ruff to 0.15
```

The type drives the auto-generated changelog and semantic versioning. `feat`
and `fix` land in the user-facing changelog and bump the version, so both must
state what a user can now do: a `User-visible:` line in the commit body,
checked in review. Work no user can observe — including internal production
code — goes under `chore(<scope>): …`. The `User-visible:` rule and the scope
convention live in [`AGENTS.md`](AGENTS.md).

## Before You PR

Git hooks are installed by `just dev-setup`: format, lint, types and secrets on
every commit; full types and the test suite on every push.

Before opening a PR, run the full gate locally:

```bash
just verify          # check, both test suites, the capability E2E, the web build
```

It must pass cleanly.

**Was bei jedem Commit läuft:** Der Secret-Scan (Gitleaks, `scripts/check_secrets.py`)
scannt das gesamte Repo inklusive History und blockt den Commit. Einige
dokumentierte Example-Keys alter v1-Docs (nur noch in der git history vorhanden)
sind in `.gitleaks.toml` allowlisted; die Allowlist muss bleiben, solange der
Scan die History sieht.

## PR Process

1. Push your feature branch and open a Pull Request against `main`.
2. Fill in the PR template (see `.github/PULL_REQUEST_TEMPLATE/`). For
   AI-powered UI changes, complete the **UX Review Checklist** (`ux_review.md`).
3. **PR checklist:**
   - [ ] `just check` passes (lint + types)
   - [ ] Tests pass (`just test`, `just test-frontend`, and the capability E2E)
   - [ ] Conventional commit, and a `User-visible:` line for `feat` and `fix`
   - [ ] No bypass of the hooks was used for any commit
4. CI runs the pipeline on every PR: lint and types, tests, E2E, build, coverage.
   There is no bypass.
5. Address review feedback with new commits; the merge will squash them.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating you agree to uphold its standards. Please be respectful and
constructive in all interactions.

## Need Help?

- **Project structure & docs:** [`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md)
  for the standing rules, the
  [v2 architecture spec](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
  for structure and boundaries, and [`docs/features/`](docs/features/) for the
  product history of the v1 era.
- **AI-assisted development:** [`AGENTS.md`](AGENTS.md) documents the agent
  skills, subagents, and conventions for working with AI coding tools on this
  project.
- **Architecture decisions:** see [`docs/architecture/decisions/`](docs/architecture/decisions/).

Happy writing! 🚀
