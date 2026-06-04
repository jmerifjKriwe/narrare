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

#### RULE-02a · Prompt content categories and their injection mechanisms

Prompt content falls into three categories, each with a distinct injection
mechanism. Using the wrong mechanism for a content type is a RULE-02 violation.

**1. User-customizable prompt content** — MUST go through `core/prompts/` cascade
(templates, PromptComposer). This includes: role descriptions, task instructions,
output format specifications, mode-specific instructions.

These are content that users can override via the cascade (project-level,
user-level, or bundled). The PromptComposer is the ONLY valid injection path.

```python
# CORRECT: User-customizable content via PromptComposer
prompt = await composer.build(intent=LLMIntent.WRITE, context=ctx)

# FORBIDDEN: Assembling user-customizable content outside core/prompts/
system_prompt = f"You are a {role} assistant. Task: {task}..."
```

**2. Architecturally guaranteed prompt content** — MAY be injected via
`AbstractCapability.get_instructions()` in `core/agents/capabilities/`. This
includes: fiction guidelines, conflict resolution rules, injection defense rules,
meta-prompt identity.

These are content that must ALWAYS be present and must NEVER be user-customizable.
Capabilities are attached at agent construction time and cannot be omitted.

Conditions:
- The content must always be present (no cascade override, no user override)
- The content must not be user-customizable
- The content must be loaded from a single canonical source (typically
  `core/prompts/_bundled/`) — Capabilities MUST NOT assemble prompts via
  f-string or concatenation

```python
# CORRECT: Guaranteed content via Capability loading from canonical source
class NarrareUniversalRules(AbstractCapability):
    async def get_instructions(self) -> str:
        loader = UniversalRulesLoader()  # uses core/prompts/ cascade
        return await loader.load(language=self._language)

# FORBIDDEN: Assembling guaranteed content via f-string
class NarrareUniversalRules(AbstractCapability):
    async def get_instructions(self) -> str:
        return f"Always follow these rules: {rules}..."
```

**3. Dynamic per-invocation content** — MAY be injected via `@agent.instructions`
or `AbstractCapability.for_run()`. This includes: KB data, style profiles,
voice profiles.

These are content that varies per invocation (depends on Deps). They are data,
not instructions (though they may contain formatting).

Conditions:
- The content varies per invocation (depends on Deps)
- The content is data, not instructions (though it may contain formatting)
- The content is assembled from runtime data, not from prompt templates

```python
# CORRECT: Dynamic content via @agent.instructions
@agent.instructions
async def kb_context(ctx: RunContext[WritingDeps]) -> str:
    assembler = ctx.deps.context_assembler
    if assembler is None:
        return ""
    return await assembler.build_context(ctx.deps)

# CORRECT: Dynamic content via Capability.for_run()
class NarrareKBContext(AbstractCapability):
    async def for_run(self, ctx: RunContext[Any]) -> NarrareKBContext:
        # Extract per-invocation data from deps
        ...

# FORBIDDEN: Hardcoding dynamic content in templates
# (KB data should not be baked into prompt templates)
```

**Enforcement:** `check_architecture.py` should verify that:
- No `get_instructions()` in `core/agents/capabilities/` assembles prompts via
  f-string or concatenation — it must load from `core/prompts/` or return
  static strings
- No `@agent.instructions` function assembles prompts via f-string or
  concatenation — it must use data from Deps or load from `core/prompts/`

**See also:** ADR-026 (Capability-Based Prompt Injection Pattern)

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

**Cross-feature contracts:** When a feature consumes data from another feature
(e.g., a writing feature reads KB entities), an Integration Contract MUST define
the behaviour when the shared data is changed or deleted. The contract documents:
- What data is shared and in which direction
- What happens on data change (propagated, stale, blocked?)
- What happens on data deletion (cascade, nullify, block?)
- Which version/schema of the shared data is expected

Integration Contracts live in the consumer feature's spec or in a dedicated
`integration_contracts.py` file at the domain boundary. They are enforced during
Stage 2.5 (Semantic Review).

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

## 4. Implementation Quality Rules

### RULE-20 · No half-implementations. Build it properly or don't build it.

Every feature must be implemented completely and correctly. Shortcuts, partial
implementations, "Phase 1 only" without Phase 2, and "we'll add the real
implementation later" are FORBIDDEN.

**What this means in practice:**

1. **No "good enough for now" architectures.** If the correct solution requires
   an embedding store, build the embedding store — don't fake it with keyword
   search and promise to add embeddings "later".

2. **No stub implementations that pass tests.** If a service needs real logic,
   write real logic. A function that returns a hardcoded list passes unit tests
   but is not an implementation.

3. **No missing error handling "for simplicity".** Every production path needs
   proper error handling, retry logic, and graceful degradation from day one.

4. **No skipped migrations.** Every schema change gets its migration, its tests,
   and its rollback path in the same task.

5. **No feature flags for incomplete features.** If a feature isn't complete
   enough to use, don't ship it behind a flag and call it done.

6. **No deferred streaming.** If the backend has SSE streaming infrastructure
   for an AI feature, the frontend MUST use SSE too. REST-only "for now" with
   "SSE later" is a half-implementation — the SSE endpoint already exists,
   the `connectSSE()` client already exists, and not using them is dead code.
   Streaming is not an upgrade; it's the core UX pattern for AI interaction.

**The incremental path is acceptable**, but each increment must be a complete,
working, tested subsystem — not a skeleton.

| Approach | Verdict |
|----------|---------|
| Correct implementation now | ✅ REQUIRED |
| Incremental path where each step is complete | ✅ ACCEPTABLE |
| "Phase 1 only" with missing infrastructure | ❌ FORBIDDEN |
| Stub that passes tests but lacks real logic | ❌ FORBIDDEN |
| Feature flag hiding an incomplete feature | ❌ FORBIDDEN |
| Missing error handling "will add later" | ❌ FORBIDDEN |

**Why:** Every half-implementation becomes a permanent shortcut. The "later"
never comes because the shortcut works "well enough" — until it breaks in
production, or blocks the next feature, or creates coupling that can't be
undone. Building it properly the first time is always cheaper than fixing a
half-implementation while maintaining backward compatibility with its mistakes.

**Examples:**

| Half-Implementation (WRONG) | Proper Implementation (RIGHT) |
|------------------------------|-------------------------------|
| Keyword search "instead of" embeddings | Full embedding store with pgvector, background generation, hybrid ranking |
| Session state in memory "for now" | Redis-backed session with TTL and persistence |
| Hardcoded scoring weights | Configurable scoring with learning from feedback |
| Skip migration, add column directly | Alembic migration + rollback test + schema regression test |
| Single agent prompt "good enough" | Structured output with Union types, proper tool definitions, context assembly |
| Mock embedding results in tests only | Real embedding pipeline with cascade resolver, fallback, and error recovery |
| REST-only frontend for SSE-capable backend | Full SSE streaming from day one — `connectSSE()` exists |
| "Phase 1: REST, Phase 2: SSE" | Single implementation: REST for CRUD, SSE for AI streaming |

---

### RULE-21 · Architecture review is invalidated by material plan changes.

Every architecture review applies only to the specific plan that was presented.
If the coordinator materially changes the plan after the review, the review
becomes invalid — the new plan must be re-reviewed.

**What counts as a material change:**
- Adding new files or modules
- Changing module boundaries (e.g., moving responsibility to a different module)
- Adding new external dependencies
- Changing constructor signatures or DI wiring
- Changing the public API of an existing module

**What does NOT count as material:**
- Cosmetic changes (typos, formatting, rewording)
- Line count corrections
- Reordering implementation steps without changing scope

**Workflow:**
```
1. Coordinator creates plan
2. → Architecture Specialist reviews → PASS/CONCERN/REJECT
3. Coordinator addresses concerns (must NOT materially change scope/architecture)
4. → Back to Architecture Specialist for re-review ONLY if material change was needed
5. → User approval
6. → Implementation
```

**The coordinator must include a `CHANGES FROM PREVIOUS REVIEW` section when
resubmitting a plan after a material change.** This section must list every
deviation from the reviewed plan with a justification.

**Why:** Without this rule, the Architecture Gate is a rubber stamp. A reviewed
plan that later evolves without re-review bypasses the entire quality check.
The AI can change plans faster than humans can read them — this rule prevents
"death by a thousand small changes."

| Violation | Consequence |
|-----------|-------------|
| Material change without re-review | Plan is invalid — must restart from Architecture |
| Missing `CHANGES FROM PREVIOUS REVIEW` section | Re-review is blocked until provided |
| Coordinator bypass (presenting unreviewed plan to user) | Escalation — user must decide |

---

### RULE-22 · Cross-Feature Coherence Gate

Every feature that shares data with other features must pass a cross-feature
coherence check before merge.

**Scope:** Any feature that reads, writes, or modifies data owned by another
feature (KB, Storyboard, Frontmatter, wiki, memory/preferences, prompt registry,
project settings, etc.).

**Checklist (before merge):**

1. **Shared data identification**: Identify all data sources this feature shares
   with other features. List each source explicitly.
2. **Change/deletion behaviour**: For each shared source, define what happens
   when the shared data is changed or deleted. Is the change propagated? Cached?
   Does it break the consuming feature?
3. **Intent/prompt semantic check**: For any new `LLMIntent` or prompt mode:
   verify no existing intent/prompt has the same ID with a different semantic
   scope. If a match is found, reuse or rename.
4. **Variable registration**: Register new template variables in
   `_SYSTEM_VARS` or `_USER_CONTENT_VARS` in `variable_engine.py`. No unregistered
   variables in prompt templates.
5. **i18n parity / prompt language policy**: Treat UI i18n and prompt-template
   language as separate concerns:
   - **UI i18n**: UI strings and `packages/web/messages/{locale}/` namespaces
     continue to require en/de/fr parity (see RULE-16).
   - **Bundled feature system prompts**: New bundled feature prompt templates
     default to EN-only. Output/writing language must be controlled through
     variables, Context, Deps, or preferences such as `{{writing_language}}`,
     not by duplicating the bundled template per locale.
   - **Localized prompt families**: If the spec declares an
     architecture-approved localized prompt family, all declared locales for
     that family must exist and keep variables in sync.
   - **Validation requirement**: EN-only bundled feature prompts are valid only
     when relevant output-language variables/context are present and validated.
6. **User-content variable registration**: Any new variable that contains
   user-authored content MUST be added to `_USER_CONTENT_VARS` and wrapped
   in XML tags in the prompt template.

**Why:** Cross-feature data dependencies are invisible at the individual feature
level. A new feature might read KB data, but only the KB feature knows its data
model. When the KB changes its schema or deletion semantics, the consuming feature
breaks silently. This rule forces explicit documentation of cross-feature contracts
before the integration exists.

**Enforcement:** Architecture Specialist during Stage 2 (Specification). The
cross-feature coherence checklist is part of every feature spec that shares data
with other features. The Semantic Review (Stage 2.5) verifies completion.

---

## 5. Future-Compatibility Rules

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

## 6. Enforcement Summary

| Rule | Enforced by |
|------|-------------|
| RULE-01b Agent/Model imports | `check_architecture.py` — import scan (agent + model checks) |
| RULE-01b Agent instantiation | `check_architecture.py` — AST scan (Agent(), .run(), .run_sync()) |
| RULE-01b LLM URLs | `check_architecture.py` — string scan |
| RULE-02 Prompt building | `check_architecture.py` — AST scan |
| RULE-02a Prompt content categories | `check_architecture.py` — AST scan (Capability f-string check) + PR review |
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
| RULE-20 No half-implementations | PR review by Architecture Agent + test coverage audit |
| RULE-22 Cross-Feature Coherence Gate | Stage 2.5 Semantic Review by Architecture Specialist |
| All rules | PR review by Architecture Agent |

---

## 7. Approved Exceptions Register

The **authoritative exception register** is `pyproject.toml [tool.narrare.architecture.exceptions]`.
This section mirrors that register in human-readable form. Both sources MUST be kept in sync.

> **Canonical source:** `pyproject.toml` is the machine-readable source consumed by
> `scripts/check_architecture.py`. `CONSTRAINTS.md` is the human-readable documentation.
> When adding or modifying exceptions, update BOTH files. Details in `pyproject.toml`
> take precedence in case of conflicts.

Every exception MUST be:
1. **Registered in `pyproject.toml`** — for auditability and machine-readability
2. **Documented in this section** — for human readability
3. **Inlined in the source file** — as a `# narrare: allow` comment at the violation site

See ADR-028 for the SSOT decision and checker enforcement specification.

### All Approved Exceptions

| # | Rule | File | Reason | Approved By | Date |
|---|------|------|--------|-------------|------|
| 1 | RULE-01 | `packages/core/narrare_core/llm/embedding_providers.py` | Batch embedding API requires direct client access for performance | architecture-review | 2026-05-27 |
| 2 | RULE-01 | `packages/core/narrare_core/memory/mem0_client.py` | mem0 AsyncMemory requires direct LLM client for memory extraction | generation-prompt-memory-foundation | 2026-05-15 |
| 4 | RULE-01b | `packages/core/narrare_core/planning/remap.py` | Injected agent, not instantiated here | architecture-review | 2026-06-03 |
| 5 | RULE-01 | `packages/core/narrare_core/wiki/agent.py` | WikiGenerationAgent uses RunContext for pydantic_ai internals | architecture-review | 2026-06-03 |
| 6 | RULE-01 | `packages/core/narrare_core/wiki/agent_chapter.py` | WikiChapterGenerator wraps internal PydanticAgent (ADR-015) | ADR-015 | 2026-06-03 |
| 7 | RULE-01b | `packages/core/narrare_core/wiki/agent_chapter.py` | WikiChapterGenerator wraps internal PydanticAgent (ADR-015) | ADR-015 | 2026-06-03 |
| 11 | RULE-TEST-01 | `tests/unit/api/metrics/test_metrics_router.py` | Mocking SQLAlchemy Engine — no domain contract | architecture-review | 2026-06-03 |
| 12 | RULE-01b | `packages/core/narrare_core/llm/gateway.py` | Gateway._make_agent() is the approved boundary crossing | ADR-015 | 2026-05-20 |
| 13 | RULE-01 | `apps/api/narrare/setup/provider_service.py` | Setup-phase provider validation requires direct import of pydantic_ai Agent | ADR-015 | 2026-05-20 |
| 14 | RULE-01b | `apps/api/narrare/setup/provider_service.py` | Setup-phase provider validation requires direct pydantic-ai Agent | ADR-015 | 2026-05-20 |

### Detailed Exception Justifications

#### Exception #1: Batch embedding API in `core/llm/embedding_providers.py`

The embedding provider requires direct client access for batch embedding operations.
Performance considerations make going through the full Gateway intent routing
impractical for high-volume embedding generation.

#### Exception #2: mem0 LLM client in `core/memory/mem0_client.py`

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

#### Exceptions #4–7: Wiki agents (ADR-015)

The wiki module agents wrap internal `PydanticAgent` instances and use
`RunContext` for pydantic_ai internals. These are architecturally approved
boundary crossings per ADR-015 (agent framework integration). The planning
remap module receives an injected agent rather than instantiating one.

#### Exception #11: Metrics router test mocking (RULE-TEST-01)

The metrics router unit test mocks SQLAlchemy's Engine object for the `/ready`
health-check endpoint. SQLAlchemy Engine is a third-party library type with no
domain contract — creating a Fake class would add maintenance burden for no
architectural benefit.

#### Exceptions #12–14: Gateway and setup (ADR-015)

`Gateway._make_agent()` is the approved boundary crossing where the LLM Gateway
creates pydantic_ai Agent instances — this is its design purpose per ADR-015.
The setup provider validation service similarly requires direct Agent access
for validating user-configured providers during initial setup.

*Every exception is a debt that should be paid down. Revisit when the Gateway
supports infrastructure-level calls with different routing rules.*

---

## 8. Single Source of Truth (SSOT) — Documentation Hierarchy

This section defines which document is authoritative when multiple sources
address the same topic. **When a derived source contradicts the authoritative
source, the authoritative source wins.**

Derived sources MAY reference the authoritative source ("See CONSTRAINTS.md
RULE-02") but MUST NOT reproduce, paraphrase, or contradict its rules.

### Authority Table

| Topic | Authoritative Source | Derived Sources (reference only) |
|-------|---------------------|----------------------------------|
| Architecture rules (RULE-XX) | `docs/_shared/CONSTRAINTS.md` (this file) | `AGENTS.md`, `.opencode/context/`, `coding-standards.md`, `.claude/rules/` |
| Technology versions | `docs/_shared/TECH_STACK.md` | README, `deployment-guide.md`, devcontainer config |
| Architecture decisions | `docs/architecture/decisions/ADR-*.md` | `AGENTS.md`, feature specs |
| Feature specifications | `docs/features/{domain}/{id}.md` | Implementation code |
| Coding standards | `docs/development/coding-standards.md` | `.opencode/context/examples/`, `.claude/rules/` |
| Testing standards | `docs/development/testing-standards.md` | `.opencode/context/examples/`, `.claude/rules/` |
| UI principles | `docs/development/ui-principles.md` | `.opencode/context/concepts/` |
| Glossary | `docs/_shared/GLOSSARY.md` | All other docs |
| Module structure | `docs/reference/directory-structure.md` | `AGENTS.md`, `.opencode/context/domain/module-map.md` |
| Agent instructions | Root `AGENTS.md` | `apps/api/AGENTS.md`, `packages/core/AGENTS.md`, `tests/AGENTS.md` |

### Rules for Derived Sources

1. **Reference, don't reproduce.** Write "See CONSTRAINTS.md RULE-02 for prompt
   building rules" — do not re-state the rule in your own words.
2. **Never contradict.** If a derived source's guidance conflicts with the
   authoritative source, the derived source is wrong and must be corrected.
3. **Code examples are illustrative.** Code snippets in `AGENTS.md` files are
   examples for context — they do not override or relax rules from the
   authoritative source. If an example shows a pattern that contradicts a RULE-XX,
   the example is wrong, not the rule.
4. **Scoped additions only.** Sub-`AGENTS.md` files (e.g. `apps/api/AGENTS.md`)
   may add context-specific guidance that the authoritative source does not cover
   (e.g. "Here is how dependency injection works in the API layer"). They may NOT
   relax, narrow, or reinterpret rules from the authoritative source.
5. **Path references must be correct.** When a derived source references another
   document, the path must resolve correctly from the derived source's location.

### Enforcement

- Manual: Architecture Specialist reviews documentation changes for SSOT compliance.
- CI (future): Automated drift detection between authoritative and derived sources
  (planned as AUFG-NEW-01 in Wave 3).

---

> Last updated: 2026-06-04 — RULE-22 prompt language policy aligned with ADR-026 Phase 5; §7 synchronized with pyproject.toml; §8 SSOT hierarchy added
> Maintained by: Architecture Agent
> Review cycle: every major milestone
