# Narrare — Architecture Constraints

> **This document is the constitution of the codebase.**
> Every rule here is machine-enforced via `scripts/check_architecture.py` (pre-commit + CI).
> Changes require an explicit entry in `docs/architecture/decisions/ (add new entry)`
> and must be approved via PR review — never unilaterally.

---

## 1. The Cardinal Rules

These four rules are absolute. No exception without a documented, reviewed decision.

### RULE-01 · LLM calls go through the Gateway. Always.

No module outside `core/llm/` may import or instantiate an LLM client.
No module outside `core/llm/` may make HTTP calls to LLM provider endpoints.

**Forbidden everywhere except `core/llm/`:**
```python
import openai
import anthropic
from pydantic_ai import Agent
openai.AsyncOpenAI()
httpx.post("https://api.openai.com/...")
httpx.post("https://api.anthropic.com/...")
```

**Required everywhere else:**
```python
from core.llm.gateway import LLMGateway  # injected, never instantiated locally
result = await gateway.run(intent=LLMIntent.WRITE, content=..., context=...)
```

**Why:** Retry logic, cost tracking, model selection, error classification,
telemetry — none of these can be guaranteed if calls are scattered.
One bypass means one silent failure with no metrics and no fallback.

**Approved exceptions:** Listed in `pyproject.toml [tool.narrare.architecture]`.
Each exception requires the inline comment `# narrare: allow-direct-llm  reason="..."`.

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
| RULE-01 LLM Gateway | `check_architecture.py` — import scan |
| RULE-01 LLM URLs | `check_architecture.py` — string scan |
| RULE-02 Prompt building | `check_architecture.py` — AST scan |
| RULE-04 File size | `check_architecture.py` — line count |
| RULE-06 Router purity | `check_architecture.py` — complexity heuristic |
| RULE-09 Type signatures | `mypy --strict` in CI |
| RULE-10 Test coverage | `pytest --cov` with minimum thresholds |
| RULE-11 Silent failures | `check_architecture.py` — bare except scan |
| RULE-14 Model-migration consistency | Integration tests + PR review |
| All rules | PR review by Architecture Agent |

---

## 6. Approved Exceptions Register

Current approved exceptions to the above rules.
Each entry requires: rule, location, reason, approved-by, date.

```toml
# pyproject.toml
[tool.narrare.architecture.exceptions]
# Example format:
# [[tool.narrare.architecture.exceptions.entries]]
# rule = "RULE-01"
# file = "core/llm/embeddings.py"
# reason = "Batch embedding API requires direct client for performance"
# approved_by = "architecture-review"
# date = "2026-01-01"
```

*No exceptions registered at project start. Every exception added here
is a debt that should be paid down.*

---

> Last updated: project initialization
> Maintained by: Architecture Agent
> Review cycle: every major milestone
