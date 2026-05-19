# Narrare — MVP Plan: First Running Version

> **Goal:** A fully working, production-quality foundation.
> Not a demo. Not a prototype. Not "we'll clean this up later."
> Every piece built here is the real thing — extensible, tested, correct.
>
> This plan is the source of truth for what the first milestone delivers.
> Location: `docs/mvp/mvp-plan.md`
> Maintained by: Architecture Agent

---

## Definition of Done (MVP)

The MVP is complete when a developer can:

1. Clone the repo and run `just dev-setup` on a clean machine
2. Run `just dev` and have the WebUI accessible at `http://localhost:3000`
3. Complete the 5-step Setup Wizard
4. See demo content (if selected) in the editor and dashboard
5. Write text in the editor and have it autosaved
6. Log in with the dev credentials
7. Change settings and have them persist across restarts
8. Run `just test` and have all tests pass
9. Run `just check` and have all constraints pass

No stubs. No "TODO: implement this later." No hardcoded bypasses.

---

## What the MVP Includes

### Infrastructure (must be production-quality from day one)

| Component | Why it must be right from the start |
|-----------|-------------------------------------|
| Monorepo structure | Everything else builds on this |
| Database + migrations | Schema changes later are expensive if base is wrong |
| Auth system | Security cannot be retrofitted |
| LLM Gateway (skeleton) | All future AI features go through this |
| Prompt system (skeleton) | Cascade resolver must be right before prompts are added |
| Settings persistence | Used by every feature |
| Dev container | Every developer needs a reproducible environment |
| CI pipeline | Constraints must be enforced before any code accumulates |
| pre-commit hooks | Same reason |
| justfile | Developer experience from day one |
| release-please | Versioning from the first commit |

### Application Features

| Feature | What specifically is built |
|---------|---------------------------|
| Setup Wizard | All 5 steps, fully functional, all 3 languages |
| Demo content | All 3 demo projects loadable |
| Writing Editor | Full editor surface — extensible for all future AI features |
| Dashboard | Basic dashboard showing novel + chapter list |
| User Settings | User preferences, persisted |
| Project Settings | Project configuration, persisted |
| Login | JWT auth, dev user seeded |
| Dev login | `dev@narrare.dev` / `narrare-dev` |

### What is explicitly NOT in MVP

These are real features that will be built — but not now:
- Any AI writing generation (new chapter, extend, rewrite)
- KB entity management
- Analysis features
- Planning features
- Background task processing (Celery)
- Embedding/pgvector operations
- mem0 memory layer
- MCP / A2A adapters

The infrastructure for all of these is designed in from day one.
The services and routes simply don't exist yet — no stubs, no placeholder endpoints.

---

## The Editor: Built for the Future

The editor is the most important MVP component because it must be extensible
without refactoring. Getting it wrong now means rewriting it later.

### What the editor must support at MVP (even without AI features)

**Document model:**
- ProseMirror or equivalent (not a textarea — that cannot be extended)
- Proper node types: paragraph, heading, scene-break, dialogue
- Chapter-scoped documents (not the whole novel in one editor)
- Autosave on change (configurable interval)
- Word count, reading time (live)

**Layout infrastructure:**
- Left sidebar: chapter list (collapsible)
- Main: editor surface
- Right sidebar: context panel (empty at MVP, populated by AI features later)
- Toolbar: formatting + action slots for AI features (empty at MVP)
- Command palette: keyboard-accessible (empty at MVP, populated later)

**Why this level of detail matters:**
If the editor is a `<textarea>`, adding inline AI suggestions later requires
replacing the entire editor. If the layout is a simple column, adding the
context panel later requires restructuring all pages. Build the shell correctly
now.

### Editor extensibility contract

Every AI feature added to the editor will use one of these slots:
- **Toolbar action** — a button that triggers an AI operation
- **Context panel section** — a panel that shows AI-generated content
- **Inline decoration** — highlights or annotations in the text
- **Command palette command** — keyboard-accessible AI operation

These slots are designed into the editor at MVP. The AI features plug into them.
No structural changes needed when AI features arrive.

---

## Implementation Order

The order matters. Each phase unblocks the next.

### Phase 0: Repository Foundation
*Duration estimate: 1 session*
*No application code. Everything that makes development possible.*

```
✓ Monorepo structure (apps/, packages/, docs/, tests/, scripts/)
✓ pyproject.toml with Python 3.14, all dependencies pinned
✓ pnpm workspace for frontend
✓ justfile with all commands
✓ .pre-commit-config.yaml (all hooks)
✓ .devcontainer/ (Dockerfile + devcontainer.json + post-create.sh)
✓ docker-compose.dev.yml (postgres pgvector/pgvector:pg17 + redis)
✓ release-please configuration
✓ GitHub Actions: ci.yml, architecture.yml, release-please.yml
✓ scripts/check_architecture.py (full implementation)
✓ pyright configuration (pyrightconfig.json)
✓ ruff configuration (pyproject.toml)
✓ pytest configuration (pyproject.toml)
✓ .env.example
✓ Initial CHANGELOG.md
✓ README.md (setup instructions only)
```

**Definition of done:** `just dev-setup` runs clean. `just check` passes on empty project.

---

### Phase 1: Core Infrastructure
*Duration estimate: 2-3 sessions*
*The foundation layers. No HTTP yet.*

```
packages/core/narrare_core/
  shared/
    ✓ frontmatter.py (parse_frontmatter, parse_frontmatter_with_content)
    ✓ file_utils.py (safe read/write, path helpers)
    ✓ pagination.py (PaginatedResponse type)
    ✓ result.py (Result[T, E], Ok, Err)

  llm/
    ✓ intents.py (LLMIntent enum — stubs for all intents, routing table)
    ✓ result.py (LLMResult, StreamChunk, LLMError)
    ✓ retry.py (retry configs, exponential backoff)
    ✓ metrics.py (cost tracking hooks — Prometheus counters)
    ✓ _providers/registry.py (provider registry, empty providers)
    ✓ _providers/openai.py (OpenAI + OpenAI-compatible adapter)
    ✓ _providers/anthropic.py (Anthropic adapter)
    ✓ _providers/zai.py (Z.AI OpenAI-compatible adapter)
    ✓ embeddings.py (embed_texts — approved RULE-01 exception)
    ✓ gateway.py (LLMGateway — full implementation)

  prompts/
    ✓ context.py (PromptContext dataclass — all fields)
    ✓ variable_engine.py (substitution, validation)
    ✓ meta.py (meta-prompt loader, cascade, lite variant)
    ✓ registry.py (single cascade resolver — replaces all three old resolvers)
    ✓ composer.py (assembles final prompt from parts)
    ✓ cache.py (fixed-key prompt cache)
    ✓ service.py (CRUD for file-based prompt management)
    ✓ _bundled/ (meta/en/system.md, meta/en/system.lite.md, meta/de/, meta/fr/)

  schemas/
    ✓ auth.py, novels.py, chapters.py (base schemas for MVP)
```

**Tests:** `tests/unit/core/` — full coverage for llm/ and prompts/

**Definition of done:** LLMGateway can make a real call to at least one provider.
Prompt cascade resolves correctly in all test cases.

---

### Phase 2: API Foundation
*Duration estimate: 2 sessions*
*The HTTP layer. No features yet — just the application shell.*

```
apps/api/narrare/
  _app/
    ✓ main.py (FastAPI factory, all middleware, lifespan)
    ✓ database.py (async engine, get_db session factory)
    ✓ dependencies.py (get_settings, get_gateway, get_composer)
    ✓ middleware.py (CORS, rate limiting, request logging)
    ✓ lifespan.py (startup: auto-migrate DB, seed dev user, log schema version)

  auth/
    ✓ models.py (User SQLAlchemy model)
    ✓ schemas.py (LoginRequest, TokenResponse, UserResponse)
    ✓ contracts.py (AuthServiceProtocol)
    ✓ repository.py (get_user_by_email, create_user)
    ✓ security.py (JWT create/verify, bcrypt hash/verify)
    ✓ service.py (login, register, refresh)
    ✓ router.py (POST /auth/login, /auth/register, /auth/refresh)

  novels/
    ✓ models.py (Novel SQLAlchemy model)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ service.py
    ✓ router.py (CRUD + list)

  chapters/
    ✓ models.py (Chapter model — full schema for future AI fields)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ service.py
    ✓ router.py (CRUD + reorder)

  volumes/
    ✓ [same structure — chapters can belong to volumes]

  settings/
    ✓ models.py (UserSettings, ProjectSettings)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ user_service.py + project_service.py + resolver.py
    ✓ router.py

  metrics/
    ✓ router.py (Prometheus scraping endpoint)

Alembic:
    ✓ Initial migration (all tables)
    ✓ Dev seeder (dev user + demo content scripts)
```

**Tests:** `tests/integration/` — all router endpoints, auth flow

**Definition of done:** `just dev-api` starts. Auth works. CRUD works. Migrations run automatically on startup. `just db-migrate` also works for manual control.

---

### Phase 3: Setup Wizard (Backend)
*Duration estimate: 1-2 sessions*

```
apps/api/narrare/setup/
  ✓ contracts.py
  ✓ schemas.py (SetupWizardState, all 5 step request/response types)
  ✓ service.py:
      - validate_step_1() (project name, language, autosave)
      - validate_step_2() (novel metadata)
      - validate_step_3() (starter content selection)
      - load_demo_content() (Fantasy / SciFi / German)
      - validate_step_4() (provider + API key validation — real test call)
      - complete_setup() (creates novel, chapters, settings, writes to user_providers + user_ai_settings, returns redirect)
  ✓ _validation.py (step validation pure functions — RULE-04 split)
  ✓ provider_service.py (fetch available models per provider — real API call)
  ✓ router.py

Demo content:
  ✓ scripts/demo_data/fantasy/ (Echoes of the Thornwall — 4 chapters, 5 KB stubs)
  ✓ scripts/demo_data/scifi/ (Dead Signal — 3 chapters, 3 KB stubs)
  ✓ scripts/demo_data/german/ (Im stillen Wald — 2 chapters, 3 KB stubs)
```

**Tests:** `tests/integration/setup/` — all 5 wizard steps, all 3 demo projects, provider validation

---

### Phase 4: Frontend Foundation
*Duration estimate: 2-3 sessions*
*The shell. Correct from day one. Built for extension.*

```
packages/web/
  ✓ Next.js 16 App Router setup
  ✓ Tailwind CSS + design tokens (CSS variables in globals.css)
  ✓ i18n setup (next-intl, en/de/fr)
  ✓ Zustand stores: auth, editor, ui
  ✓ TanStack Query setup
  ✓ API client (typed, all endpoints)

  app/
    ✓ (auth)/login/page.tsx
    ✓ (auth)/register/page.tsx
    ✓ (setup)/wizard/page.tsx (5-step wizard, fully functional)
    ✓ (app)/dashboard/page.tsx (novel list + chapter list)
    ✓ (app)/novel/[id]/editor/page.tsx (editor page — full shell)

  components/
    setup/
      ✓ WizardLayout.tsx
      ✓ Step1Location.tsx
      ✓ Step2Novel.tsx
      ✓ Step3StarterContent.tsx
      ✓ Step4AIProvider.tsx (with live model loading)
      ✓ Step5Confirm.tsx
    editor/
      ✓ EditorLayout.tsx (sidebar + main + right panel slots)
      ✓ ChapterSidebar.tsx
      ✓ EditorSurface.tsx (ProseMirror — full node types, autosave)
      ✓ EditorToolbar.tsx (formatting + AI action slots, empty)
      ✓ ContextPanel.tsx (right panel shell, empty)
      ✓ CommandPalette.tsx (shell, empty)
      ✓ WordCount.tsx
    shared/
      ✓ Button, Input, Select, Modal, Toast (design system components)
      ✓ LanguageSwitch.tsx
      ✓ ThemeToggle.tsx (light/dark)
```

**Definition of done:** Complete Setup Wizard flow works. Editor opens and autosaves.
All UI text is i18n strings (no hardcoded English). Light + dark mode works.

---

### Phase 5: Integration & Polish
*Duration estimate: 1 session*

```
✓ End-to-end flow: signup → wizard → demo content → editor
✓ Post-login redirect: has_providers ? /dashboard : /wizard
✓ Dev user seeded automatically on first startup
✓ Auto-migration: lifespan.py runs alembic upgrade head on startup
✓ Integration tests use real Alembic migrations (not create_all)
✓ All settings persist correctly
✓ All tests pass (unit + integration)
✓ All checks pass (architecture + lint + typecheck + security)
✓ README updated with actual setup instructions
✓ CHANGELOG.md has v0.1.0 entry
```

---

## Architecture Decisions Pre-Made for MVP

These decisions are made now so the MVP doesn't need to revisit them:

### Editor: ProseMirror via TipTap
TipTap wraps ProseMirror with a React-friendly API. Extensible via custom extensions.
The AI feature slots (toolbar, context panel, inline decorations) are TipTap extensions.

### Frontend State
- Server state: TanStack Query v5
- Client state: Zustand v5
- Forms: React Hook Form v7

### i18n
next-intl. Messages in `packages/web/messages/{locale}.json`.
All user-facing strings use `useTranslations()`. Zero hardcoded English in components.

### Auth
JWT (access + refresh token). Access token in memory (not localStorage).
Refresh token in httpOnly cookie. Standard, secure, extensible.

### Autosave
Debounced on editor content change. Configurable interval via project settings.
Optimistic update in UI, confirmed by server response.

---

## What "No Stubs" Actually Means

For every API endpoint in the MVP:
- Has a real service implementation (not `return {"todo": "implement"}`)
- Has input validation (Pydantic models, real errors)
- Has auth checking where required
- Has at least one integration test

For every UI component:
- Has real data (not hardcoded mock data except for Storybook)
- Has loading state
- Has error state
- Has i18n strings (not hardcoded English)

For the editor specifically:
- Autosave actually saves to the database
- Word count is actually computed from content
- Chapter switching actually loads the correct chapter content

---

## pyproject.toml Key Configuration

```toml
[project]
requires-python = ">=3.14"

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false  # Some stubs not yet available for 3.14

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "TCH"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.coverage.run]
source = ["apps", "packages"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.narrare.architecture]
llm_allowed_modules = ["core/llm/gateway.py", "core/llm/embeddings.py"]
prompt_allowed_modules = ["core/prompts/"]
forbidden_llm_imports = ["openai", "anthropic", "pydantic_ai"]
forbidden_llm_urls = ["api.openai.com", "api.anthropic.com"]
file_size_limits = {router = 150, service = 300, repository = 250, default = 400}
```

---

## Open Questions Blocking MVP

See `docs/architecture/questions/Q-005-resolved.md`

The Z.AI/GLM provider adapter must be confirmed working before Phase 1 is complete.
All other providers (OpenAI, Anthropic) are unblocked and can proceed in parallel.

---

> Last updated: project initialization
> Owner: Architecture Agent
> This plan changes only via Architecture session + DECISIONS.md entry
