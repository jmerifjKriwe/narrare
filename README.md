# Narrare

[![CI](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml/badge.svg)](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

<!-- Pytest Coverage Comment:Begin -->
<a href="https://github.com/jmerifjKriwe/narrare/blob/main/README.md"><img alt="Coverage" src="https://img.shields.io/badge/Coverage-88%25-green.svg" /></a>
<!-- Pytest Coverage Comment:End -->

> AI-assisted creative writing environment — local-first, fully customizable.

## Requirements

- [Python 3.14+](https://www.python.org/downloads/)
- [Node.js 24+](https://nodejs.org/) + [pnpm](https://pnpm.io/installation)
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose (provides PostgreSQL + pgvector and Redis via `docker-compose.dev.yml`)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [just](https://just.systems/man/en/chapter_4.html)

## Quick Start

```bash
git clone https://github.com/your-org/narrare.git
cd narrare

# First-time setup (installs dev + NLP deps/models, creates .env, runs migrations, seeds dev user)
just dev-setup

# Edit .env and add your AI provider API key, then:
just dev
```

> **Note:** If you run `uv sync` manually instead of `just dev-setup`, use
> `uv sync --frozen --all-packages --group dev --extra nlp`. See
> [deployment-guide.md](docs/development/deployment-guide.md) for details.

Open [http://localhost:3000](http://localhost:3000) and complete the Setup Wizard.

**Dev login** (created automatically):
- Email: `dev@narrare.dev`
- Password: `narrare-dev`

## Development Commands

```bash
just --list          # Show all available commands

just dev             # Start all services
just dev-api         # API only (port 8000)
just dev-frontend    # Frontend only (port 3000)
just dev-worker      # TaskIQ worker only

just test            # Run all tests
just test-unit       # Unit tests only (fast)
just check           # All checks (architecture + lint + types + security)

just db-migrate      # Run migrations
just db-revision "description"  # Create new migration
```

## Project Structure

```
narrare/
├── apps/
│   ├── api/          ← FastAPI backend (Python 3.14)
│   └── mcp/          ← MCP adapter (planned; calls Service Layer when built)
├── packages/
│   ├── core/         ← Shared domain logic
│   ├── i18n/         ← Translations
│   └── web/          ← Next.js frontend
├── docs/
│   ├── agents/       ← AI agent definitions + architectural docs
│   └── features/     ← Feature specifications
├── scripts/          ← Dev tooling
└── tests/            ← Test suite
```

## Dev Container (VS Code)

For a fully configured environment (recommended when using a remote VM):

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the repository in VS Code
3. When prompted, click "Reopen in Container"

The container includes Python 3.14, Node.js, uv, just, and all VS Code extensions pre-configured.

## Architecture

See [`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md) for architectural rules.

See [`docs/_shared/TECH_STACK.md`](docs/_shared/TECH_STACK.md) for technology decisions.

MCP and A2A are roadmap adapters, not implemented product surfaces. Under
RULE-12, future adapters call the existing Service Layer; Q-001 (MCP auth) and
Q-002 (A2A streaming) remain open until adapter-specific specs are written.

## License

MIT
