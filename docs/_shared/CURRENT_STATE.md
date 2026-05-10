# Narrare — Current State

> **This document is the live status of the project.**
> Every agent reads this at the start of every session.
> Updated at the end of every session by the responsible agent.
>
> Location: `docs/_shared/CURRENT_STATE.md`

---

## Last Updated

Date: 2026-05-10
Updated by: Orchestrator
Session summary: Audited CURRENT_STATE.md against actual codebase.
Found major drift — Phases 1–3 were implemented but not reflected here.
Updated to match reality.

---

## Project Phase

```
Phase 0: Repository Foundation     ✅ COMPLETE
Phase 1: Core Infrastructure       ✅ COMPLETE
Phase 2: API Foundation            ✅ COMPLETE
Phase 3: Setup Wizard Backend      ✅ COMPLETE
Phase 4: Frontend Foundation       · not started
Phase 5: Integration & Polish      · not started
```

---

## What Exists Right Now

### Documentation (complete)

**Shared Foundation (`docs/_shared/`):**
- `CONSTRAINTS.md` — 13 rules, CI-enforced
- `TECH_STACK.md` — canonical technology decisions
- `GLOSSARY.md` — shared vocabulary
- `CURRENT_STATE.md` — this file

**Development (`docs/development/`):**
- `coding-standards.md` — Python 3.14 + TypeScript standards
- `testing-standards.md` — test architecture, coverage targets, fixtures
- `ui-principles.md` — UX principles, component structure, state management
- `deployment-guide.md` — CI/CD, dev environment, release process
- `orchestrator.md` — orchestrator agent definition

**Reference (`docs/reference/`):**
- `project-vision.md` — why, what, for whom
- `directory-structure.md` — canonical file locations

**Architecture (`docs/architecture/`):**
- `decisions/INDEX.md` + ADR-001 through ADR-007
- `questions/INDEX.md` + Q-001 through Q-005

**Features (`docs/features/`):**
- `INDEX.md` — 40+ features catalogued
- `_TEMPLATE.md`
- Individual feature specs (SETUP-001, SETUP-002, WRITE-001) referenced in INDEX but not yet created as separate files

**MVP (`docs/mvp/`):**
- `mvp-plan.md` — 5-phase plan for first running version

### Demo Content (complete)

**German demo ("Im stillen Wald") — `scripts/demo_data/german/im-stillen-wald/`:**
- Chapter 1: "Das Flüstern im Wald" (`ch-de-001-fluestern.md`) ✅
- Chapter 2: "Grenze der Welten" (`ch-de-002-grenze-welten.md`) ✅
- KB: Der Waldgeist, Das Försterhaus, Der Wald, Das Dorf ✅
- KB: Charaktere — Anna Müller, Johann Bauer ✅

**Fantasy demo ("Echoes of the Thornwall") — `scripts/demo_data/english/echoes-of-the-thornwall/`:**
- 4 chapters (`ch-en-001` through `ch-en-004`) ✅
- 15 KB entries: 5 characters, 5 locations, 2 factions, 3 systems, 1 object ✅

**SciFi demo ("Dead Signal") — `scripts/demo_data/english/dead-signal/`:**
- 3 chapters (`ch-en-ds-001` through `ch-en-ds-003`) ✅
- 7 KB entries: 3 characters, 2 locations, 1 object, 2 systems ✅

### Code

#### `packages/core/narrare_core/` — Shared Domain Logic (Phase 1)

**LLM Layer (`llm/`):**
- `gateway.py` — Single LLM Gateway (ADR-001), ~290 lines
- `_providers/` — OpenAI, Anthropic, Ollama, ZAI, Others, Registry (6 providers)
- `result.py`, `retry.py`, `metrics.py`, `intents.py`, `embeddings.py`

**Prompt System (`prompts/`):**
- `composer.py` — Prompt composition (ADR-002)
- `registry.py` — Prompt registry
- `variable_engine.py` — Variable interpolation
- `context.py`, `meta.py`

**Shared Utilities (`shared/`):**
- `result.py` — Result type pattern (Ok/Err)
- `pagination.py`, `frontmatter.py`, `file_utils.py`, `errors.py`

**Stub Modules (interfaces only):**
- `context/`, `cache/`, `schemas/`, `memory/`, `embeddings/`

#### `apps/api/narrare/` — FastAPI Backend (Phase 2 & 3)

**App Infrastructure (`_app/`):**
- `main.py`, `config.py`, `database.py`, `dependencies.py`, `lifespan.py`, `middleware.py`

**Domain Modules (all contract-first per ADR-003):**
- `auth/` — JWT auth: models, service, router, repository, contracts, schemas, security
- `novels/` — CRUD: models → repository → service → router, contracts, schemas
- `chapters/` — CRUD: models → repository → service → router, contracts, schemas
- `volumes/` — CRUD: models → repository → service → router, contracts, schemas
- `settings/` — models, repository, router, schemas
- `setup/` — Setup wizard: router, service, contracts, schemas, provider_service, provider_schemas, demo_loader
- `metrics/` — Health/metrics router

**Database:**
- Alembic migration `0001_initial.py` — initial schema

#### `packages/i18n/` — Translations

- Package structure exists (`narrare_i18n/`, `pyproject.toml`)
- Content not yet populated (Phase 4+)

#### `packages/web/` — Next.js Frontend

- **Does not exist yet.** Planned for Phase 4.

#### `tests/` — Test Suite

**Unit tests (14 files):**
- `core/llm/` — gateway, intents, retry (3 files)
- `core/prompts/` — registry, composer, variable_engine (3 files)
- `core/shared/` — frontmatter (1 file)
- `api/setup/` — setup_service, setup_schemas, demo_loader (3 files)
- `api/auth/` — security (1 file)
- `api/chapters/` — chapter_service (1 file)
- `api/novels/` — placeholder

**Integration tests (4 files):**
- `setup/test_setup_api.py`, `novels/test_novels_api.py`
- `chapters/test_chapters_api.py`, `auth/test_auth_api.py`
- `conftest.py` with shared fixtures

**E2E:** Directory exists, no tests yet.

#### Infrastructure

- `scripts/` — `check_architecture.py`, `seed_dev_user.py`, `check_commit_message.py`, `demo_data/`, `local/`
- `.devcontainer/` — full dev container setup
- `.github/workflows/` — CI (`ci.yml`), architecture check (`architecture.yml`), release (`release-please.yml`)
- Docker Compose (`docker-compose.dev.yml`) for PostgreSQL (pgvector) + Redis
- `justfile`, `pyproject.toml`, `uv.lock`

### AI Tooling (opencode + OAC)

- opencode CLI installed in dev container
- OpenAgentsControl (OAC) installed with full profile
- Custom Narrare Orchestrator agent (`.opencode/agent/narrare-orchestrator.md`)
- Narrare behavioral rules (`.opencode/context/narrare/` — 5 files: architecture, documentation, implementation, navigation, orchestration)
- Narrare navigation pointing to `docs/` as single source of truth

---

## What Is In Progress

Nothing. Ready for Phase 4.

---

## What Is Blocked

Nothing blocking Phase 4.

All demo content is complete — sufficient for testing through Phase 5.

---

## Resolved Since Last Update

| Item | Resolution |
|------|-----------|
| Q-004 Celery vs arq | → TaskIQ. ADR-007 created. arq in maintenance-only mode. |
| Q-005 GLM/Z.AI/pydantic-ai | → OpenAI-compatible endpoints. Factory function in `core/llm/_providers/zai.py`. |
| Dead links in docs/ | Fixed: CURRENT_STATE.md created, PROJECT_VISION path corrected, Q-005 reference fixed |
| Deployment guide gaps | CI pipeline specs, pre-commit config, justfile catalog, env vars added |
| Coding standards gaps | Result type pattern, service DI pattern added |
| CURRENT_STATE.md drift | Audited and corrected — Phases 1–3 were implemented but not reflected |

---

## Decisions Made (full log in ADR files)

| ADR | Decision | Status |
|-----|---------|--------|
| ADR-001 | Single LLM Gateway | ✅ Implemented in `core/llm/gateway.py` |
| ADR-002 | Unified Prompt System | ✅ Implemented in `core/prompts/` |
| ADR-003 | Protocol-First Development | ✅ Applied across all API modules |
| ADR-004 | Hard File Size Limits | ✅ Enforced via `check_architecture.py` |
| ADR-005 | Directory Structure & Module Ownership | ✅ Applied |
| ADR-006 | Technology Stack | ✅ Applied |
| ADR-007 | TaskIQ for Background Tasks | ✅ Decided, integration pending |

---

## Open Questions (summary)

| ID | Question | Status | Blocks |
|----|---------|--------|--------|
| Q-001 | MCP auth strategy | 🟡 Open | apps/mcp/ (post-MVP) |
| Q-002 | A2A streaming requirement | 🟡 Open | apps/a2a/ (post-MVP) |
| Q-003 | Embedding provider abstraction | 🟡 Open | core/llm/embeddings.py (Phase 5) |
| Q-004 | Celery vs arq | ✅ Resolved → TaskIQ | — |
| Q-005 | GLM/Z.AI compatibility | ✅ Resolved → OpenAI-compatible | — |

---

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Python 3.14 missing type stubs for some deps | Low | Low | `reportMissingTypeStubs = false` in pyrightconfig |
| TipTap v3 extension API changes during Phase 4 | Low | Medium | Pin exact version in package.json |
| Feature spec files not yet individualized | Low | Low | INDEX.md has catalogue, can be expanded per-feature as needed |
| No frontend code yet — Phase 4 is the largest phase | Medium | Medium | Start with scaffold, iterate incrementally |

---

## Next Session Should Start With

**Phase 4: Frontend Foundation** — see `docs/mvp/mvp-plan.md` for full checklist.

Key steps:
1. Initialize `packages/web/` as Next.js 15 project
2. Set up TipTap v3 editor scaffold
3. Connect to existing API endpoints (auth, novels, chapters, volumes, setup)
4. Build first navigable page structure

---

> Maintained by: Architecture Agent, updated by Orchestrator at session end
