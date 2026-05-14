# Changelog

All notable changes to Narrare will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

---

## [Unreleased]

### Added

- httpOnly refresh token cookie (`narrare_refresh`) for secure session management
- Frontend `restoreSession()` — silent refresh via httpOnly cookie on page reload
- Editor TipTap extensions: NarrareDocument (chapter-scoped doc), DialogueMark (dialogue spans), Autosave (debounced save)
- CommandPalette (Cmd+K) with format + editor action commands; extensible registry via `commands.ts`
- Dashboard novel delete (Trash2 icon, hover-revealed, confirmation dialog)
- Focus mode exit: ESC key handler + floating Minimize2 button (semi-transparent)
- Demo project metadata.json files (author, logline, pov, tags) for all 3 starters

### Changed

- Setup wizard steps 2↔3 swapped: starter selection now comes before novel details
- WizardStep3 prefills form from metadata.json when a demo starter is selected
- Demo loader reads metadata from files instead of hardcoded data
- EditorSurface refactored to use Autosave TipTap extension
- editorStore now holds TipTap editor ref (set by EditorSurface, read by CommandPalette)

---

## [0.1.0] - 2026-05-12

Initial MVP release — first running version with Setup Wizard and Writing Editor.

### Phase 0: Repository Foundation

- Monorepo structure (apps/api, packages/core, packages/i18n, packages/web)
- CI pipeline (GitHub Actions: lint, test, architecture checks)
- Dev container (VS Code + Docker)
- Pre-commit hooks (Ruff, architecture checker, commit message format)

### Phase 1: Core Infrastructure

- LLM Gateway with 6 providers (OpenAI, Anthropic, Ollama, Z.AI, Others, Registry) [ADR-001]
- Unified Prompt System with cascade resolver [ADR-002]
- Shared utilities (Result type, pagination, frontmatter parsing, error handling)

### Phase 2: API Foundation

- FastAPI backend with async PostgreSQL (SQLAlchemy 2.0 + pgvector)
- JWT authentication (argon2id password hashing) [ADR-009]
- CRUD endpoints: novels, chapters (with content versioning) [ADR-011], volumes, settings
- Alembic migrations
- OpenTelemetry tracing + Langfuse LLM observability [ADR-010]
- Event-driven architecture (Redis Pub/Sub → TaskIQ) [ADR-012]
- Async rate limiting (fastapi-limiter + Redis) [ADR-009]

### Phase 3: Setup Wizard Backend

- 5-step setup wizard API (project config, novel metadata, demo content, AI provider, confirmation)
- 3 demo projects: "Echoes of the Thornwall" (Fantasy, EN), "Dead Signal" (SciFi, EN), "Im stillen Wald" (DE)
- AI provider validation endpoint

### Phase 4: Frontend Foundation

- Next.js 15 with App Router + TypeScript
- TipTap v3 rich text editor with autosave (debounced API calls)
- Setup wizard UI (5 steps)
- Dashboard with novel cards
- Auth pages (login, register) with JWT token management
- i18n support (en, de, fr) with next-intl
- Dark mode (CSS variables + Tailwind v4)
- 101 frontend tests (Vitest + Testing Library + MSW)

### Phase 5: Integration & Polish

- Playwright E2E testing infrastructure with route mocking for LLM responses
- Backend test coverage expansion (settings, demo loader, gateway, retry)
- Frontend test coverage expansion (editor, wizard, dashboard, shared)
- Documentation polish (architecture questions, CURRENT_STATE, testing standards)
- Security: httpOnly refresh tokens, in-memory access tokens, jose middleware
