# Contributing to Narrare

Thanks for your interest in contributing! **Narrare** is an AI-powered creative
writing environment — local-first, fully customizable, and MIT-licensed. We
welcome contributions of all kinds: bug reports, features, documentation, and
more.

## Getting Started

You need [Python 3.14+](https://www.python.org/downloads/) with
[uv](https://docs.astral.sh/uv/), [Node.js 22+](https://nodejs.org/) with
[pnpm](https://pnpm.io/), [Docker](https://docs.docker.com/get-docker/) with
Compose, and [just](https://just.systems/). One command sets everything else
up — the Python environment, web dependencies, git hooks, the Postgres
services and the schema:

```bash
just dev-setup
just dev          # API on :8000, web on :3100
```

Open <http://localhost:3100> — a fresh database lands on `/setup`. There is no
other setup variant: the schema comes from the models (`just db-init`), and
`just db-reset` recreates the development database when the models change.

## Branch Model

- All work happens on **feature branches** created from `main`.
- Branch naming uses a prefix followed by a short description:
  `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`
  (e.g. `feat/kb-versioning`, `fix/login-timeout`).
- Keep branches focused — one logical change per branch makes review faster.

**Merging:** a pull request whose branch meets the commit standard —
conventional commits, green at every commit — is merged with a **merge
commit**: the commits land on `main` unchanged, commit references stay
valid, and release-please sees every conventional commit. A pull request
that does not meet the standard (typical for drive-by contributions) is
**squashed**, with a conventional-commit title that becomes the changelog
entry. Auto-merge is off: a green PR waits for a human approval. Direct pushes to `main` are
fine for documentation-only changes (`*.md`); everything else goes through
a pull request, because only CI runs the E2E and the web build before the
merge.

## Conventional Commits

Every commit message follows the [Conventional Commits](https://www.conventionalcommits.org/)
format:

```
feat(core): add prompt cascade resolution

User-visible: Prompt cascades can be resolved per project.
fix(api): resolve session timeout on idle
docs: update deployment guide
chore(deps): bump ruff to 0.15
```

The type drives the auto-generated changelog and semantic versioning. `feat`
and `fix` land in the user-facing changelog and bump the version, so both must
state what a user can now do: a `User-visible:` line in the commit body. Work no
user can observe — including internal production code — goes under
`chore(<scope>): …`. The `User-visible:` rule and the scope convention live in
[`AGENTS.md`](AGENTS.md) and are checked in review.

## Before You PR

Git hooks are installed by `just dev-setup`: format, lint, the typecheck of the
changed files and the secret scan run on every commit; the full typecheck and
the test suite run on every push. Bypassing a hook (`--no-verify`) is forbidden.

Before opening a PR, run the full gate locally:

```bash
just verify          # check, both test suites, the affected capability E2E suites,
                     # the web build; `just verify all` before a risky change
```

It must pass cleanly.

**The README's images.** On a fresh checkout, `uv run playwright install chromium`
once — `just dev-setup` installs the Python package, not the browser itself. Then
`uv run python -m scripts.screenshots` boots the same stack the E2E suites use,
loads the bundled demo novel and writes the five frames under `assets/screenshots/`.
Run it when a surface they show has changed: the images are the one part of the
README no test reads.

**Was bei jedem Commit läuft:** Der Secret-Scan (Gitleaks,
`scripts/check_secrets.py`) scannt das gesamte Repo inklusive History und
blockt den Commit. Einige dokumentierte Example-Keys alter v1-Docs (nur noch in
der git history vorhanden) sind in `.gitleaks.toml` allowlisted; die Allowlist
muss bleiben, solange der Scan die History sieht.

## PR Process

1. Push your feature branch and open a Pull Request against `main`. Title it as the
   sentence the change deserves: the same `type(scope): effect` grammar the commits
   use. `Phase 0`, `Wave 1`, task ids and internal programme names say how the work
   was planned, not what it does; they belong to the plan, and at most to the body as
   a reference.
2. Fill in the PR template (`.github/PULL_REQUEST_TEMPLATE.md`). For UI or
   AI-touching changes, complete the **UX review** section; delete it otherwise.
3. **PR checklist:**
   - [ ] `just check` passes (lint + types)
   - [ ] Tests pass (`just test`, `just test-frontend`, and the capability E2E)
   - [ ] Conventional commit, and a `User-visible:` line for `feat` and `fix`
   - [ ] No bypass of the hooks was used for any commit
4. CI runs on every PR and on every push to `main`: lint and types, the
   integration tests and the web build. The E2E runs on the PR — in parallel
   per capability behind one `e2e` check, for the capabilities the change
   touches: all of them when kernel, web, the justfile, `pyproject.toml`, the
   locks or the CI workflow change, none of them for a documentation-only
   change. A push to `main` owes no E2E: what it merges is the tree the PR
   tested, and a direct push is covered by the nightly, which tests
   everything but only when `main` moved since the last one. Coverage is
   measured on `main`. There is no bypass.
5. Address review feedback with new commits.

## Code of Conduct

This project follows the
[Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating in this project you agree to uphold its terms. Please be
respectful and constructive.

## Need Help?

- **The five standing rules:** [`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md)
- **Structure and boundaries:** the
  [v2 architecture spec](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
  — §14 records where the built system is simpler than it describes
- **Architecture decisions:** [`docs/architecture/decisions/`](docs/architecture/decisions/)
- **Product history of the v1 era:** [`docs/features/`](docs/features/) (kept as
  an archive; v2 capability documentation is generated, not migrated)
- **AI-assisted development:** [`AGENTS.md`](AGENTS.md) documents the agent
  layer and the conventions for working with AI coding tools on this project.

Happy writing! 🚀
