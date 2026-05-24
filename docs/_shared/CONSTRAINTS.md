# Narrare — Architecture Constraints

> **This document is the constitution of the codebase.**
> Every rule here is machine-enforced via `scripts/check_architecture.py` (pre-commit + CI).
> Changes require an explicit entry in `docs/architecture/decisions/ (add new entry)`
> and must be approved via PR review — never unilaterally.

---

## 1. The Cardinal Rules

These four rules are absolute. No exception without a documented, reviewed decision.

### RULE-01b · Agents are the way to use LLMs. Models come from the ModelRegistry. Always.

No module outside `core/agents/` may import or instantiate `pydantic_ai.Agent` or any subclass.
No module outside `core/llm/` may import or instantiate model/provider classes.
No module may make HTTP calls to LLM provider endpoints.

**Erlaubt in `core/agents/`:**
```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import ...
from pydantic_ai.output import ...
agent.run() / agent.run_sync()
```

**Erlaubt in `core/llm/`:**
```python
from pydantic_ai.models import Model
from pydantic_ai.providers import ...
from pydantic_ai.models.openai import OpenAIChatModel (etc.)
```

**Forbidden everywhere:**
```python
import openai
import anthropic
openai.AsyncOpenAI()
httpx.post("https://api.openai.com/...")
httpx.post("https://api.anthropic.com/...")
```

**Required everywhere else:**
```python
from narrare_core.agents.base import NarrareAgent  # injected, never instantiated locally
result = await agent.run(prompt=..., deps=...)
```

**Why:** RULE-01 allowed pydantic_ai.Agent imports only in core/llm/, but
pydantic-ai is an agent framework, not a model framework. Agents (tools,
capabilities, output types, system prompts) belong in core/agents/. The
ModelRegistry in core/llm/ provides model instances for agents.
Separation of concerns: agent logic vs model resolution.

**Approved exceptions:** Listed in `pyproject.toml [tool.narrare.architecture]`.
Each exception requires the inline comment `# narrare: allow-agent  reason="..."`.

---

### RULE-02 · Prompts are built in `core/prompts/`. Nowhere else.

No module outside `core/prompts/` may assemble a prompt string via f-string,
string concatenation, or template substitution.
No module outside `core/prompts/` may implement cascade resolution logic.

**Forbidden everywhere except `core/prompts/`:**
```python
system_prompt = f"You are a {role} assistant..."
prompt = f"{system_prompt}\n\n{content}"
user_prompt = "Last paragraphs: " + text + "\nContinue with..."
if Path(".narrare/prompts/...").exists():  # own cascade logic
    ...
```

**Required everywhere else:**
```python
from core.prompts.composer import PromptComposer  # injected
prompt = await composer.build(intent=LLMIntent.WRITE, context=ctx)
```

**Why:** Three competing cascade implementations existed simultaneously in the
previous codebase. A user override saved via the UI did not reliably reach
the runtime resolver for the same feature. That must never happen again.

---

### RULE-03 · Contracts before implementation.

Every service class must have a corresponding Protocol definition in its
`_types.py` or the domain's `contracts.py` before implementation begins.

**Forbidden:**
```python
class ChapterWritingService:
    async def write(self, ...):  # no Protocol exists
        ...
```

**Required:**
```python
# writing/contracts.py  ← written first
class ChapterWriterProtocol(Protocol):
    async def write(self, request: WriteRequest) -> WriteResult: ...

# writing/service.py  ← written after
class ChapterWritingService:
    ...  # implements ChapterWriterProtocol implicitly
```

**Why:** In the previous codebase, 0 of ~60 services had defined contracts
(`contract_defined: false` for all). This made mocking, testing, and
client-switching (MCP, A2A, CLI) require rewriting calling code.

---

### RULE-04 · Split before you squeeze — modularity over minification.

| File type | Hard limit | Soft target |
|-----------|-----------|-------------|
| Any Python module | 400 lines | 250 lines |
| Router file | 150 lines | 80 lines |
| Service file | 300 lines | 200 lines |
| Agent definition | 200 lines | 150 lines |
| Test file | 400 lines | 300 lines |
| Config / schema file | 200 lines | 150 lines |

A file approaching its soft target is a signal to **split**.
A file at its hard limit is a build failure.

**When a file approaches its limit, the ONLY acceptable response is modularization:**

1. Extract a new service, repository, or utility module with its own responsibility
2. Move cohesive functionality to a dedicated file (e.g., `draft_service.py` split out of `service.py`)
3. Add a new router file for additional resource endpoints (e.g., `router_drafts.py`)

**Explicitly FORBIDDEN "solutions" — do NOT:**
- Compress code to squeeze under the limit (removing whitespace, shortening names, collapsing multi-line expressions)
- Combine related functions into dense one-liners
- Sacrifice readability to stay within line count

These tactics produce files that are technically under the limit but harder to read than the original — and the **next** change will push them over again. The limit exists to force **modularization**, not to encourage code golf.

**Split strategy** — when a file grows too large, split by:
1. **Routers:** one router file per resource sub-group (e.g., `writing/router_sessions.py`, `writing/router_drafts.py`)
2. **Services:** extract into focused sub-services (e.g., `writing/draft_service.py`, `writing/session_service.py`)
3. **Agents:** separate system prompt logic from tool definitions from run logic

**Why:** `writing/service.py` in the previous codebase reached 1200+ lines
with 8 different responsibilities. It contained the worst violations of
every other rule precisely because it was too large to review carefully.

Additionally: AI coding agents waste significant reasoning tokens on
"how do I save 5 lines" instead of simply extracting a focused module.
This rule makes the correct path unambiguous: modularize, don't compress.

---

### RULE-15 · No `middleware.ts` — `proxy.ts` is the only Next.js route middleware.

No file named `middleware.ts` may exist in `packages/web/` or any of its subdirectories.
Next.js 16+ uses `proxy.ts` exclusively. Having both files causes a hard build failure.

**Forbidden:**
```
packages/web/middleware.ts          — NEVER create this file
packages/web/src/middleware.ts      — NEVER create this file
packages/web/**/middleware.ts       — NEVER create this file
```

**Required:**
```
packages/web/proxy.ts               — edit THIS file for route protection / auth / redirects
```

**Why:** This has happened repeatedly. AI coding agents and developers instinctively
create `middleware.ts` because Next.js ≤15 used that convention. The resulting build
error — "Both middleware file and proxy file are detected" — is cryptic, wastes
debugging time, and breaks CI for everyone.

The file `proxy.ts` already contains a header warning. That has proven insufficient.
This rule makes the prohibition machine-enforceable.

---

## 2. Structural Rules

### RULE-05 · Module boundaries are ownership boundaries.

Each domain module owns its own:
- DB models (if any)
- Pydantic schemas (request/response)
- Service contracts (Protocols)
- Service implementations
- Router
- Tests

A module must **not** import from another module's `_internal` submodule.
Cross-domain communication goes through the domain's public `__init__.py` exports only.

```
# Forbidden:
from narrare.writing._internal.prompt_vars import build_vars

# Required:
from narrare.writing import PromptContext  # public export only
```

---

### RULE-06 · One responsibility per file.

Each file has exactly one of these roles:

| Role | Naming | Contains |
|------|--------|----------|
| Router | `router.py` or `router_<group>.py` | FastAPI routes only, no business logic |
| Service | `service.py` or `<name>_service.py` | Business logic, no DB queries |
| Repository | `repository.py` or `<name>_repo.py` | DB queries only, no business logic |
| Schema | `schemas.py` or `<name>_schemas.py` | Pydantic models only |
| Contract | `contracts.py` | Protocol definitions only |
| Model | `models.py` | SQLAlchemy models only |
| Agent | `agent.py` or `<name>_agent.py` | LLM agent definition only |
| Config | `config.py` | Settings/constants only |
| Utilities | `utils.py` or `<name>_utils.py` | Pure functions, no I/O |

Routers **delegate immediately** to services. No business logic in routers.
Services **delegate DB operations** to repositories. No raw SQLAlchemy in services.

---

### RULE-07 · Dependency direction is one-way.

```
router → service → repository → database
           ↓
        core/llm/gateway (via DI)
        core/prompts/composer (via DI)
```

Arrows point down only. A repository never imports from a service.
A service never imports from a router.
`core/` never imports from `apps/`.

---

### RULE-08 · All external integrations are abstracted.

No direct SDK calls to external services outside their dedicated adapter:

| Service | Allowed location |
|---------|-----------------|
| PostgreSQL / SQLAlchemy | `*/repository.py` only |
| Redis | `core/cache/client.py` only |
| pgvector | `core/embeddings/store.py` only |
| mem0 | `core/memory/client.py` only |
| SMTP | `core/notifications/email.py` only |
| Web search (Tavily/Serp) | `core/research/search_client.py` only |
| Langfuse | `core/llm/observability.py` only |
| OpenTelemetry | `apps/api/narrare/_app/telemetry.py` only |
| Event bus (Redis Pub/Sub) | `apps/api/narrare/_app/events.py` only |

---

### RULE-14 · Every model column needs a migration.

When a SQLAlchemy model column is added, renamed, changed type, or removed,
the corresponding Alembic migration **must** be created in the same task.
A model change without a matching migration is a build failure.

**When touching `models.py`:**

1. Create the Alembic migration in the same task.
2. Verify `upgrade()` and `downgrade()` both work.
3. Cross-check: if the column exists in a related table, add it there too.
4. Write a regression test that verifies the schema matches the model.

**Forbidden:**

```python
# Adding a column to models.py without a migration
class ProjectSettings(Base):
    token_limit_profile: Mapped[str] = mapped_column(String(20))
    # ↑ If no migration adds this column → build failure
```

**Required:**

```
# 1. models.py — add column
# 2. alembic/versions/NNNN_add_token_limit_profile.py — add migration
# 3. tests/integration/.../test_..._schema.py — regression test
```

**Cross-table check — the bug that motivated this rule:**

Migration 0004 added `token_limit_profile` to `user_ai_settings` but forgot
`project_settings`. Both tables store AI configuration. When adding a column
to one table in a shared concern, check ALL tables in that concern.

**Why:** The setup wizard crashed at runtime because the SQLAlchemy model
included `token_limit_profile` but the database column never existed. The
migration had been marked as "applied" — no automated check caught the mismatch.
Integration tests using real Alembic migrations (not `create_all()`) are the
safety net.

---

### RULE-18 · No hardcoded configuration in routers.

Router endpoints must NOT hardcode provider names, model IDs, API keys, or
other configuration values that should come from user/project settings.
All runtime configuration must be resolved via dependency injection or the
settings cascade.

**Forbidden:**
```python
@router.post("/generate")
async def generate(
    provider_name: str = "anthropic",  # ← hardcoded
    model_id: str = "claude-sonnet-4-20250514",  # ← hardcoded
):
    ...
```

**Required:**
```python
@router.post("/generate")
async def generate(
    settings: ProjectAISettings = Depends(resolve_ai_settings),
    # ↑ resolved via settings cascade: user > project > system default
):
    provider = settings.provider_name
    model = settings.model_id
```

**Why:** Hardcoding `provider_name="anthropic"` in a router works in
development but crashes in production when users have configured a different
provider. Configuration must flow through the `ModelRoutingResolver` cascade.
Without this rule, a developer testing with one provider hardcodes their
defaults — and every user with a different provider gets a runtime crash.

**Enforcement:**
- `check_architecture.py` could be extended to scan router files for hardcoded
  provider strings (`"anthropic"`, `"openai"`, `"ollama"`) and known model IDs
- Regression tests in `tests/unit/api/test_generation_router_contract.py` verify
  no hardcoded configuration values leak into dependency factory functions
- Code review: look for string literals in dependency factory functions and
  router default parameter values

---

### RULE-19 · Dependency factories must use `SessionDep`, not bare `AsyncSession`.

All FastAPI dependency factory functions in `**/dependencies.py` files must use
`SessionDep` (which is `Annotated[AsyncSession, Depends(get_async_session)]`)
for session parameters — never bare `AsyncSession`.

**Forbidden:**
```python
# dependencies.py — bare AsyncSession causes 422 in production
def get_kb_service(session: AsyncSession) -> KBService:
    ...
```

**Required:**
```python
# dependencies.py — SessionDep includes Depends() marker
from narrare._app.dependencies import SessionDep

def get_kb_service(session: SessionDep) -> KBService:
    ...
```

**Why:** FastAPI treats bare `AsyncSession` as a query parameter — the endpoint
returns 422 "Field required" instead of injecting a database session. This bug
has occurred multiple times (at least twice in KB and settings modules) because
the difference between `AsyncSession` and `SessionDep` is invisible in unit tests
(where sessions are manually provided) and only surfaces in production. The
architecture checker now catches this automatically.

**Enforcement:** `check_architecture.py` — AST scan for bare `AsyncSession` annotations
in `dependencies.py` files under `apps/api/`.

---

## 3. Quality Rules

### RULE-09 · Every public function has a type signature.

No untyped public functions. Return type annotation is mandatory.
`Any` is forbidden except in explicitly approved adapter code.

```python
# Forbidden:
def build_context(novel, chapters, settings):
    ...

# Required:
async def build_context(
    novel: Novel,
    chapters: list[Chapter],
    settings: ProjectSettings,
) -> PromptContext:
    ...
```

---

### RULE-10 · Tests are not optional.

Every new service method requires a corresponding unit test.
Every new router endpoint requires a corresponding integration test.
Minimum coverage for `core/` modules: **90%**.
Minimum coverage for `apps/api/` modules: **80%**.

Test files live in `tests/unit/` and `tests/integration/` — never inside the
source package itself.

Test naming mirrors source structure:
```
core/prompts/composer.py  →  tests/unit/core/prompts/test_composer.py
apps/api/writing/service.py  →  tests/unit/writing/test_writing_service.py
```

---

### RULE-11 · No silent failures.

Every `except` block must either re-raise, log with `structlog`, or convert to
a typed domain error. Bare `except: pass` is a build failure.

```python
# Forbidden:
try:
    result = await gateway.run(...)
except Exception:
    pass

# Required:
try:
    result = await gateway.run(...)
except LLMGatewayError as e:
    logger.error("llm_call_failed", intent=intent, error=str(e))
    raise WritingServiceError("Generation failed") from e
```

---

### RULE-16 · i18n namespace registration.

Every `useTranslations("X")` call must have a corresponding `"X"` entry in
the `namespaces` array in `packages/web/lib/i18n/request.ts`, AND a
corresponding `X.json` file must exist in all 3 locale directories
(`en`, `de`, `fr`).

**What goes wrong without this rule:**

When a namespace is used in a component but not registered in `request.ts`,
`next-intl` silently returns raw keys instead of translated strings. The UI
shows broken labels like `generation.nameGenerator` instead of
"Name Generator". This is a **runtime-only failure** — no compile-time check
catches it. Unit tests mock translations and integration tests may not render
the specific component, so the broken labels ship to users unnoticed.

**Required:**
```typescript
// 1. Component uses the namespace
const t = useTranslations("generation");

// 2. Namespace registered in request.ts
export const namespaces = ["common", "generation", ...];
//                                    ↑ must be listed

// 3. Files exist in all locales
// packages/web/messages/en/generation.json  ← must exist
// packages/web/messages/de/generation.json  ← must exist
// packages/web/messages/fr/generation.json  ← must exist
```

**Enforcement:**
- Regression test: `packages/web/__tests__/i18n-namespace-registry.test.ts`
  scans all source files for `useTranslations("X")` calls and validates that
  each `"X"` is registered in `request.ts` and that all locale files exist
- Existing i18n validator (`validate-i18n.ts`) checks key completeness
  between locales

---

### RULE-17 · API-Frontend contract consistency.

Backend Pydantic response schema field names must exactly match the frontend
TypeScript interface field names. When the backend returns `{"id": "..."}` but
the frontend reads `.prompt_id`, the result is `undefined` at runtime.

**What goes wrong without this rule:**

Without contract tests, field name mismatches between backend schemas and
frontend types cause runtime crashes that unit tests miss — unit tests mock
the data and never see the real API shape. The backend test asserts the schema
has `id`, the frontend test asserts the component reads `prompt_id`, and both
pass while the real integration is broken.

**Required:**
```python
# Backend: apps/api/generation/schemas.py
class PromptResponse(BaseModel):
    prompt_id: str    # ← field name
    name: str
    template: str

# Frontend: packages/web/types/generation.ts
interface PromptResponse {
  prompt_id: string  // ← MUST match exactly
  name: string
  template: string
}
```

**When adding or changing a response schema field, the corresponding
TypeScript type must be updated in the same commit.**

**Enforcement:**
- Regression tests in `tests/unit/api/test_prompt_contract.py` verify field
  names match frontend expectations by importing both schemas and comparing
- PR review: any Pydantic schema change must have a matching TypeScript change
- Future: consider auto-generating TypeScript types from Pydantic schemas
  (`pydantic-to-typescript` or similar)

---

## 4. Future-Compatibility Rules

### RULE-12 · The Service Layer is the only public API.

WebUI, MCP, A2A, and CLI are all clients of the Service Layer.
They never call each other. They never contain business logic.

```
WebUI  ──┐
MCP    ──┤──→  Service Layer API  ──→  core/  ──→  LLM / DB / Cache
A2A    ──┤
CLI    ──┘
```

When adding MCP or A2A support: create a new adapter in `apps/mcp/` or
`apps/a2a/` that calls existing services. Do not modify services to
accommodate a specific client.

---

### RULE-13 · Streaming and non-streaming share one interface.

Every LLM operation that supports streaming must also support non-streaming
through the same method signature:

```python
async def run(
    self,
    ...,
    stream: bool = False,
) -> LLMResult | AsyncIterator[str]:
    ...
```

This ensures MCP and A2A (which may not support streaming) can use the
same service methods without a parallel non-streaming implementation.

---

## 5. Enforcement Summary

| Rule | Enforced by |
|------|-------------|
| RULE-01b Agent/Model imports | `check_architecture.py` — import scan (agent + model checks) |
| RULE-01b Agent instantiation | `check_architecture.py` — AST scan (Agent(), .run(), .run_sync()) |
| RULE-01b LLM URLs | `check_architecture.py` — string scan |
| RULE-02 Prompt building | `check_architecture.py` — AST scan |
| RULE-04 File size | `check_architecture.py` — line count |
| RULE-06 Router purity | `check_architecture.py` — complexity heuristic |
| RULE-09 Type signatures | `mypy --strict` in CI |
| RULE-10 Test coverage | `pytest --cov` with minimum thresholds |
| RULE-11 Silent failures | `check_architecture.py` — bare except scan |
| RULE-14 Model-migration consistency | Integration tests + PR review |
| RULE-15 No middleware.ts | `check_architecture.py` — file existence scan |
| RULE-16 i18n namespace registration | `i18n-namespace-registry.test.ts` + `validate-i18n.ts` |
| RULE-17 API-Frontend contract | `test_prompt_contract.py` + PR review |
| RULE-18 No hardcoded config in routers | `test_generation_router_contract.py` + PR review |
| RULE-19 SessionDep in dependency factories | `check_architecture.py` — AST scan for bare AsyncSession |
| All rules | PR review by Architecture Agent |

---

## 6. Approved Exceptions Register

Current approved exceptions to the above rules.
Each entry requires: rule, location, reason, approved-by, date.

```toml
# pyproject.toml
[tool.narrare.architecture.exceptions]

[[tool.narrare.architecture.exceptions.entries]]
rule = "RULE-01"
file = "packages/core/narrare_core/memory/mem0_client.py"
reason = "mem0 AsyncMemory requires direct LLM client for memory extraction. Provider/model is user-configurable via settings. Gateway's intent routing and rate limiting don't apply to infrastructure-level memory extraction."
approved_by = "generation-prompt-memory-foundation"
date = "2026-05-15"

[[tool.narrare.architecture.exceptions.entries]]
rule = "RULE-01b"
file = "packages/core/narrare_core/llm/gateway.py"
reason = "Gateway._make_agent() is the internal bridge between ModelRegistry and Agent. Core/llm/ creates Agent instances with resolved models and system prompts — this is the approved boundary crossing. Agents in core/agents/ will use higher-level NarrareAgent wrappers."
approved_by = "ADR-015"
date = "2026-05-20"

[[tool.narrare.architecture.exceptions.entries]]
rule = "RULE-01b"
file = "apps/api/narrare/setup/provider_service.py"
reason = "Setup-phase provider validation requires direct pydantic-ai Agent to test credentials. This runs once during project setup, not in the LLM call path."
approved_by = "ADR-015"
date = "2026-05-20"
```

### Exception: mem0 LLM client in `core/memory/mem0_client.py`

mem0's `AsyncMemory` class requires its own LLM client instance for memory
extraction — it calls the LLM internally to analyze text, extract facts, and
build preference profiles. The Gateway's intent-based routing and rate limiting
do not apply here because:

1. **The LLM call is infrastructure-level**, not a user-facing feature call.
   mem0 decides when and how to call the LLM for memory extraction.
2. **Provider/model is user-configurable** via the same settings used by the
   gateway (stored in `user_ai_settings`). The mem0 client reads these settings
   to construct its own client.
3. **Cost-efficient defaults** are used per provider (Haiku for Anthropic,
   GPT-4.1-nano for OpenAI, Llama3.2 for Ollama) — these are lightweight
   extraction calls, not generation calls.
4. **Graceful degradation**: `NullMemoryClient` is used when mem0 is unavailable,
   so this never blocks user requests.

This exception mirrors the embedding exception in `core/llm/embeddings.py` —
both are infrastructure-level LLM calls that operate outside the user-facing
intent routing system.

*Every exception is a debt that should be paid down. Revisit when the Gateway
supports infrastructure-level calls with different routing rules.*

---

> Last updated: 2026-05-20 — RULE-01→RULE-01b (agents first-class, ModelRegistry)
> Maintained by: Architecture Agent
> Review cycle: every major milestone
