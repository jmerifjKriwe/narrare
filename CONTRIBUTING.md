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

For the full setup walkthrough and troubleshooting, see
[deployment-guide.md](docs/development/deployment-guide.md).

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
fix(api): resolve session timeout on idle
docs: update deployment guide
chore(deps): bump ruff to 0.15
```

The type (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`)
drives the auto-generated changelog and semantic versioning. For the full
specification and the allowed scope list, see
[coding-standards.md](docs/development/coding-standards.md).

## Before You PR

Pre-commit hooks are mandatory and are installed automatically by
`just dev-setup` / `just dev-setup-min`. They enforce architecture constraints,
linting, formatting, and commit-message format.

Before opening a PR, run the full check suite locally:

```bash
just check           # architecture + lint + typecheck + security
just check-frontend  # frontend lint + typecheck + test
```

Both must pass cleanly.

**Was bei jedem Commit läuft:** Neben den Architektur-/Lint-/Format-Checks führt
jeder Commit zwei Repo-weite Gates aus: (1) **SSOT-Check**
(`check_current_state_facts.py`) — prüft `CURRENT_STATE.md` auf verbotene
volatile Count-Claims; (2) **Secret-Scan** (Gitleaks) — scannt das gesamte Repo
inkl. History auf Secrets. Beide blocken den Commit. Wenn Gitleaks einen
dokumentierten Example-Key markiert (z. B. `openai_api_key="test-key"` aus
ADR-071), wird der Key in `.gitleaks.toml` explizit allowlisted — siehe
`.gitleaks.toml` für die Allowlist-Regel und ADR-071 für die Herkunft des
Beispiel-Keys.

## PR Process

1. Push your feature branch and open a Pull Request against `main`.
2. Fill in the PR template (see `.github/PULL_REQUEST_TEMPLATE/`). For
   AI-powered UI changes, complete the **UX Review Checklist** (`ux_review.md`).
3. **PR checklist:**
   - [ ] `just check` passes (architecture + lint + typecheck + security)
   - [ ] `just check-frontend` passes (if frontend touched)
   - [ ] Tests pass (`just test` and/or `just test-frontend`)
   - [ ] No `--no-verify` was used for any commit
   - [ ] Architecture checks are green (CI job "Architecture Constraints")
   - [ ] Neue `packages/web/lib/**`-Dateien haben Unit-Tests (CI-Floor 80% branches — `pnpm test:coverage`)
   - [ ] Neue/Geänderte VRT-Specs folgen dem Mock-Contract (ADR-059 BINDING): `just vrt` lokal grün
4. CI runs the full pipeline on every PR — all applicable jobs must be green.
   There is no bypass.
5. Address review feedback with new commits; the merge will squash them.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating you agree to uphold its standards. Please be respectful and
constructive in all interactions.

## Need Help?

- **Project structure & docs:** browse the [`docs/`](docs/) directory —
  [`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md) for architecture
  rules, [`docs/development/`](docs/development/) for coding and testing standards.
- **AI-assisted development:** [`AGENTS.md`](AGENTS.md) documents the agent
  skills, subagents, and conventions for working with AI coding tools on this
  project.
- **Architecture decisions:** see [`docs/architecture/decisions/`](docs/architecture/decisions/).

Happy writing! 🚀
