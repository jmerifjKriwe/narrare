# Testing Standards — Narrare

> **Scope:** All test code in `tests/`. Test strategy for the whole project.
> **Mandate:** Every untested behavior is a bug waiting to happen.
>             Tests are not an afterthought. They are the proof that code works.
>
> Maintained by: Testing Agent

---

## Test Architecture

### Three Levels — Always Separate

```
tests/
├── unit/           ← Fast, pure, no I/O. Mock everything external.
│                     Run time target: < 5 seconds total.
│
├── integration/    ← Real DB, real Redis, mocked LLM.
│                     Docker Compose provides services.
│                     Run time target: < 60 seconds total.
│
└── e2e/            ← Full stack. LLM responses mocked via Playwright route interception.
                      Run only on main branch CI.
                      Run time target: < 5 minutes total.
                      Tool: Playwright (implemented in Phase 5).
                      Status: Implemented in Phase 5.
```

**The rule:** A test lives at the lowest level where it can be meaningful.
Unit tests for logic. Integration tests for DB interactions. E2E for user flows.

Never use a real DB in a unit test. Never mock the DB in an integration test.

---

## What Gets Tested

### Unit Tests — Services and Core Logic

Every public method on every **service** class gets a unit test.
Minimum cases per method:
1. Happy path — correct input, expected output
2. Domain error — invalid input, correct error raised
3. Edge case — at least one boundary condition

**Services use constructor-based dependency injection.** All dependencies
(Repositories, other Services, LLM Gateway) are passed as Protocol-typed
arguments to `__init__`. Tests inject Fakes through the constructor — never
by bypassing `__init__` with `__new__`.

**Repositories are NOT unit-tested.** Repository logic (SQL queries) is tested
exclusively in integration tests with a real database. Mocking an AsyncSession
to verify that `.execute()` was called tests nothing meaningful — a wrong
WHERE clause or missing JOIN passes the unit test but fails in production.

```python
# Example: tests/unit/api/chapters/test_chapter_service.py

class TestChapterServiceUpdateContent:
    async def test_returns_draft_on_success(
        self, service: ChapterService, fake_repo: FakeChapterRepository
    ) -> None:
        chapter = make_chapter()
        fake_repo.seed(chapter)

        result = await service.update_content(
            chapter.id, chapter.novel_id, user_id, request
        )

        assert result.content == "new content"

    async def test_raises_on_llm_failure(
        self, service: DraftService, fake_gateway: FakeLLMGateway
    ) -> None:
        fake_gateway.raises(LLMGatewayError("timeout"))
        with pytest.raises(WritingError, match="Generation failed"):
            await service.write(request=valid_write_request())

    async def test_uses_correct_intent(
        self, service: DraftService, fake_gateway: FakeLLMGateway
    ) -> None:
        await service.write(request=valid_write_request())
        fake_gateway.assert_called_with_intent(LLMIntent.WRITE)
```

### Integration Tests — Repositories and Router Endpoints

Integration tests cover TWO things:

**Repository tests** — every repository method with a real database:
1. Happy path — correct data returned
2. Not found — None or empty list for missing resources
3. Edge cases — pagination boundaries, ordering, constraints

**Router tests** — every HTTP endpoint via `httpx.AsyncClient`:
1. Success — 200/201 with correct response schema
2. Unauthorized — 401 when auth missing
3. Not found — 404 for missing resources
4. Validation error — 422 for invalid input

Every 200/201 response must validate the response body against its Pydantic
schema. This catches serialization bugs and schema drift:

```python
assert response.status_code == 201
data = response.json()
validated = ChapterResponse.model_validate(data)  # Schema validation
assert validated.title == "Chapter One"
```

**Rule:** Every 200/201 response in integration tests must include
`Schema.model_validate()`.

### Architecture Tests — Constraint Enforcement

The constraint checker runs as a test:
```python
# tests/conftest.py (embedded)
def test_architecture_constraints() -> None:
    result = subprocess.run(["python", "scripts/check_architecture.py"])
    assert result.returncode == 0
```

### Fake Conformance Tests — Protocol Verification

Every Fake class is verified against its corresponding Protocol in a dedicated
conformance test file. This is a safety net that catches missing methods when
Protocols are updated.

**Location:** `tests/unit/test_fake_conformance.py`

All Protocols in `contracts.py` are marked `@runtime_checkable`, enabling
`isinstance()` checks at test time:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ChapterRepositoryProtocol(Protocol):
    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> Chapter | None: ...
    async def create(self, novel_id: UUID, request: CreateChapterRequest, position: int) -> Chapter: ...
```

```python
# tests/unit/test_fake_conformance.py
from tests.fakes import FakeChapterRepository
from packages.core.chapters.contracts import ChapterRepositoryProtocol

def test_fake_chapter_repo_conforms():
    fake = FakeChapterRepository()
    assert isinstance(fake, ChapterRepositoryProtocol)
```

**Rule:** When adding a new Fake, add a conformance test. If the Protocol
changes, the conformance test fails immediately.

### Cross-Layer Contract Testing

> **Why this section exists:** Three bugs went undetected because our test
> standards didn't cover the boundaries between layers. Unit tests mock data,
> integration tests focus on single layers, and nothing validates that the
> frontend and backend agree on field names, that i18n namespaces are complete,
> or that routers don't hardcode configuration. Cross-layer contract tests close
> these gaps.
>
> **References:** RULE-16, RULE-17, RULE-18 in `docs/_shared/CONSTRAINTS.md`

#### i18n Namespace Completeness Tests — RULE-16

**The problem:** Components use `useTranslations("X")` but if `"X"` is not in
the `namespaces` array in `request.ts`, next-intl silently returns raw keys.
Unit tests mock translations and never catch this — the component renders
`"prompts.title"` instead of the actual translated string.

**Test pattern:**
```
packages/web/__tests__/i18n-namespace-registry.test.ts
```

Scans all `.ts`/`.tsx` source files for `useTranslations("X")` calls, extracts
the root namespace (before any dot), and asserts every namespace is registered
in the `request.ts` namespaces array.

```typescript
// packages/web/__tests__/i18n-namespace-registry.test.ts
import fs from "node:fs"
import path from "node:path"

describe("i18n namespace registry", () => {
  it("every useTranslations namespace is registered in request.ts", () => {
    const sourceDir = path.resolve(__dirname, "../src")
    const namespaces = extractUsedNamespaces(sourceDir)
    const registered = extractRegisteredNamespaces(
      path.resolve(__dirname, "../src/i18n/request.ts")
    )

    const missing = namespaces.filter(ns => !registered.includes(ns))
    expect(missing).toEqual([])
  })
})
```

**When to update:** New components using a new namespace must update
`request.ts` in the same commit. This test runs as part of `pnpm test` and will
fail CI if namespaces are missing.

**Reference:** RULE-16 in `docs/_shared/CONSTRAINTS.md`

---

#### API Response Contract Tests — RULE-17

**The problem:** Backend Pydantic schemas and frontend TypeScript types can
drift. When the backend returns `{"id": "..."}` but the frontend reads
`.prompt_id`, the result is `undefined` at runtime. Unit tests mock the data
and never see the mismatch. Integration tests validate the schema exists but
don't check whether the frontend expects the same field names.

**Test pattern:**
```
tests/unit/api/test_{domain}_contract.py
```

For each Pydantic response schema that the frontend consumes directly:

- Assert the expected field names exist (e.g., `prompt_id`, not `id`)
- Assert the field types match (e.g., `str`, not `int`)
- Assert forbidden field names are absent

```python
# tests/unit/api/test_prompt_contract.py
from pydantic import ValidationError
import pytest

from apps.api.prompts.schemas import PromptResponse, PromptListResponse


class TestPromptResponseContract:
    """Cross-layer contract: backend schema must match frontend expectations."""

    EXPECTED_FIELDS: dict[str, type] = {
        "prompt_id": str,
        "title": str,
        "category": str,
        "content": str,
        "is_default": bool,
    }

    FORBIDDEN_FIELDS: list[str] = [
        "id",  # Frontend expects prompt_id, not id
    ]

    def test_has_all_expected_fields(self) -> None:
        """Every field the frontend reads must exist with the correct type."""
        schema_fields = PromptResponse.model_fields
        for field_name, expected_type in self.EXPECTED_FIELDS.items():
            assert field_name in schema_fields, (
                f"Missing field '{field_name}' — frontend will get undefined"
            )
            # Check annotation is compatible (handle Optional, etc.)
            actual_type = schema_fields[field_name].annotation
            assert expected_type in _unwrap_types(actual_type), (
                f"Field '{field_name}' is {actual_type}, expected {expected_type}"
            )

    def test_no_forbidden_fields(self) -> None:
        """Fields the frontend does NOT expect must be absent."""
        schema_fields = PromptResponse.model_fields
        for forbidden in self.FORBIDDEN_FIELDS:
            assert forbidden not in schema_fields, (
                f"Forbidden field '{forbidden}' found — rename or remove"
            )
```

**When to add:** Every time a new response schema is created or an existing one
is modified, a contract test must accompany the change in the same PR.

**Reference:** RULE-17 in `docs/_shared/CONSTRAINTS.md`

---

#### Configuration Integrity Tests — RULE-18

**The problem:** Router endpoints that hardcode provider names, model IDs, or
other configuration work in development but crash for users with different
configurations. Tests that mock settings never catch hardcoded strings.

**Test pattern:**
```
tests/unit/api/test_{domain}_router_contract.py
```

Uses `inspect.getsource()` to read the factory function source and assert no
hardcoded configuration strings exist — all configuration must come from
DI/settings, not string literals.

```python
# tests/unit/api/test_prompt_router_contract.py
import inspect

from apps.api.prompts.router import get_prompt_service


class TestPromptRouterConfigurationContract:
    """Router must not hardcode config — all from DI/settings."""

    FORBIDDEN_STRINGS: list[str] = [
        "openai",
        "anthropic",
        "gpt-4",
        "claude",
        "localhost",
    ]

    def test_factory_no_hardcoded_config(self) -> None:
        """Factory function source must not contain hardcoded config strings."""
        source = inspect.getsource(get_prompt_service).lower()
        for forbidden in self.FORBIDDEN_STRINGS:
            assert forbidden not in source, (
                f"Hardcoded '{forbidden}' in router factory — "
                f"use DI/settings instead"
            )
```

**When to add:** Every new router that creates services via factory functions
should have a contract test verifying that configuration comes from
DI/settings, not hardcoded values.

**Reference:** RULE-18 in `docs/_shared/CONSTRAINTS.md`

---

## Mocking Standards — RULE-TEST-01

> **Enforced by:** `scripts/check_architecture.py` — bare MagicMock scan.
> **No exceptions without documented decision in CONSTRAINTS.md.**

### The Rule: Fake Classes instead of MagicMock

Every domain dependency (Repository, Service, LLM Gateway) gets a **Fake class**
that implements the corresponding Protocol from `contracts.py`.

```
tests/fakes/
├── __init__.py
├── fake_llm_gateway.py       ← FakeLLMGateway
├── fake_repositories.py      ← FakeChapterRepo, FakeNovelRepo, etc.
├── fake_services.py          ← FakeNovelService, FakeAuthService, etc.
└── fake_setup.py             ← FakeProviderService, FakeDemoLoader
```

### What IS allowed

```python
# ✅ Fake classes for domain dependencies
from tests.fakes import FakeChapterRepository, FakeLLMGateway

fake_repo = FakeChapterRepository()
fake_repo.seed(make_chapter(id=uuid4()))

fake_gateway = FakeLLMGateway()
fake_gateway.returns("Generated text")

# ✅ patch() for external functions that are not dependencies
with patch("narrare.auth.service.hash_password", return_value="hashed"):
    await service.register(request)

# ✅ patch.object() for private methods in core tests
with patch.object(gateway, "_make_agent", return_value=fake_agent):
    await gateway.run(...)

# ✅ AsyncMock() on Fake objects for individual method overrides
fake_repo.get_by_id = AsyncMock(return_value=None)
```

### What is FORBIDDEN

```python
# ❌ Bare MagicMock() without spec=
session = MagicMock()
repo = MagicMock()
gateway = MagicMock()

# ❌ MagicMock as replacement for a domain dependency
service._repo = MagicMock()  # Use FakeChapterRepository instead
service._gateway = MagicMock()  # Use FakeLLMGateway instead

# ❌ Nested mock chains
mock_result = MagicMock()
mock_result.data = "text"
mock_agent = MagicMock()
mock_agent.run = AsyncMock(return_value=mock_result)

# ❌ MagicMock(spec=...) as a shortcut when a Fake exists
# If tests/fakes/ has a Fake for it, use the Fake.
```

### Why Fakes are better

| Aspect | Fake Class | MagicMock |
|--------|-----------|-----------|
| **Contract safety** | Breaks at compile time when Protocol changes | Silently accepts any attribute |
| **Refactor safety** | Must update Fake → immediate feedback | Tests pass with stale interface |
| **Readability** | `fake_repo.seed(chapter)` — clear intent | `mock.get_by_id = AsyncMock(...)` — scattered setup |
| **Reusability** | Shared across all tests | Setup repeated per test file |
| **Documentation** | Fake IS the contract documentation | Mock hides the contract |

### Fake Class Pattern

Every Fake follows this structure. All corresponding Protocols in `contracts.py`
are `@runtime_checkable` — conformance tests use `isinstance()` to verify Fakes
implement their Protocol correctly.

```python
class FakeChapterRepository:
    """Fake that implements ChapterRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Chapter] = {}
        self.calls: list[CallRecord] = []

    # --- Seeding (test setup) ---
    def seed(self, *chapters: Chapter) -> None:
        for ch in chapters:
            self._store[ch.id] = ch

    # --- Protocol implementation ---
    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> Chapter | None:
        self.calls.append(CallRecord("get_by_id", chapter_id=chapter_id, novel_id=novel_id))
        return self._store.get(chapter_id)

    async def create(self, novel_id: UUID, request: CreateChapterRequest, position: int) -> Chapter:
        chapter = _build_from_request(novel_id, request, position)
        self._store[chapter.id] = chapter
        self.calls.append(CallRecord("create", novel_id=novel_id))
        return chapter

    # --- Call tracking ---
    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: object) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")
```

---

## LLM Testing — Pydantic AI Tools

> **Scope:** Tests that exercise the gateway→agent bridge or need deterministic LLM behavior.
> **No new dependencies** — uses pydantic-ai's built-in testing models.
> **Reference:** `tests/unit/core/llm/conftest.py` for fixture definitions.

### Global Guard — `ALLOW_MODEL_REQUESTS = False`

Set in `tests/conftest.py` — prevents **all** real LLM API calls in the test suite.
If a test accidentally creates a real pydantic-ai Agent and calls `.run()` without
mocking the model, pydantic-ai raises a clear `RuntimeError` instead of silently
hitting the network.

```python
# tests/conftest.py (already set)
from pydantic_ai import models

models.ALLOW_MODEL_REQUESTS = False
```

### Tool Hierarchy

Not all tests need the same level of LLM mocking. Use the right tool for the job:

| Test Level | Tool | Why |
|-----------|------|-----|
| Service unit tests | `FakeLLMGateway` | Service doesn't know about agents |
| Gateway unit tests | `TestModel` / `FunctionModel` | Tests the real Agent code path |
| Agent-level tests | `TestModel` + `capture_run_messages` | Asserts tool call behavior |
| Integration tests | `FakeLLMGateway` + dependency override | End-to-end through HTTP |
| E2E tests | Playwright route mocking | Full browser stack |

### `TestModel` — Deterministic Agent Responses

`TestModel` (from `pydantic_ai.models.test`) replaces the real LLM with deterministic responses.
Use the `gateway_with_test_model` fixture from `tests/unit/core/llm/conftest.py`:

```python
async def test_gateway_returns_result(
    self,
    gateway_with_test_model: LLMGateway,
    write_config: ResolvedModelConfig,
) -> None:
    # No mocking — TestModel is injected as the model
    result = await gateway_with_test_model.run(
        intent=LLMIntent.WRITE,
        system_prompt="System.",
        user_prompt="Write.",
        config=write_config,
        retry_config=NO_RETRY,
    )
    assert isinstance(result, LLMResult)
```

Custom response text: `TestModel(custom_output_text="Your response here")`.

### `FunctionModel` — Scenario-Specific Behavior

`FunctionModel` (from `pydantic_ai.models.function`) runs a Python function as the LLM.
Use when different inputs need different responses:

```python
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

def smart_mock(messages, info):
    last_msg = messages[-1]
    user_text = str(last_msg)
    if "error" in user_text.lower():
        raise ModelHTTPError(status_code=500, model_name="test")
    return ModelResponse(parts=[TextPart("All good.")])

# For streaming tests, also provide stream_function:
async def smart_mock_stream(messages, info):
    raise ModelHTTPError(status_code=500, model_name="test")
    yield  # makes this an async generator

error_model = FunctionModel(smart_mock, stream_function=smart_mock_stream)
```

**Important:** When testing the `stream()` path, `FunctionModel` requires a `stream_function`
parameter. Without it, pydantic-ai raises an `AssertionError` before the regular function runs.

### `capture_run_messages` — Tool Call Assertions

For agents with tools (future: writing sessions), use `capture_run_messages` to inspect
which tools were called and with what arguments:

```python
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.models.test import TestModel

agent = Agent("test", output_type=str)

@agent.tool
async def lookup_character(ctx, name: str) -> str:
    return f"Character: {name}"

test_model = TestModel()
with capture_run_messages() as messages:
    with agent.override(model=test_model):
        result = await agent.run("Write about Anna")

tool_calls = [
    part for msg in messages
    for part in msg.parts if hasattr(part, "tool_name")
]
assert any(tc.tool_name == "lookup_character" for tc in tool_calls)
```

### RULE-01 Exception Pattern for Test Files

Test files that import `pydantic_ai` must add `# narrare: allow reason="..."` as a
**standalone comment on the line immediately before** the import. This is because
`ruff format` wraps long lines, and the architecture checker looks at `lineno - 2` to `lineno`.

```python
# ✅ Correct — comment on line before import
# narrare: allow reason="gateway tests use TestModel instead of real LLM"
from pydantic_ai.models.test import TestModel

# ❌ Wrong — comment at end of import (ruff format may wrap it away)
from pydantic_ai.models.test import TestModel  # narrare: allow reason="..."
```

### What STAYS the Same

`FakeLLMGateway` (in `tests/fakes/`) remains the primary tool for **service-level** tests.
Services don't know about agents — they call `gateway.run()`. Inject `FakeLLMGateway`
through the constructor. This is the Protocol-first pattern from RULE-TEST-01.

`FakePydanticAgent` is kept for the streaming chunk test (TestModel doesn't produce
real streaming chunks). It will be removed once pydantic-ai's TestModel supports
configurable streaming behavior.

---

## Fixtures and Test Infrastructure

### Fake Fixtures

Services accept Protocol-typed dependencies through their constructor.
Fixtures wire Fakes into services via normal constructor calls.

**Rule: NEVER use `__new__()` to bypass `__init__`. Always pass dependencies
through the constructor.**

```python
# Service accepts Protocol-typed dependencies in constructor
class ChapterService:
    def __init__(
        self,
        repo: ChapterRepositoryProtocol,
        novel_service: NovelServiceProtocol,
    ) -> None:
        self._repo = repo
        self._novel_service = novel_service

# tests/conftest.py
@pytest.fixture
def fake_gateway() -> FakeLLMGateway:
    """Fake LLM gateway — configurable responses, call tracking."""
    return FakeLLMGateway()

@pytest.fixture
def fake_chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()

# Per-domain fixtures in test subdirectories:
# tests/unit/api/chapters/conftest.py
@pytest.fixture
def service(fake_chapter_repo, fake_novel_service) -> ChapterService:
    return ChapterService(
        repo=fake_chapter_repo,
        novel_service=fake_novel_service,
    )
```

### Database Fixtures (Integration Only)

Integration tests run **real Alembic migrations** (not `Base.metadata.create_all()`)
against the test database. This catches migration bugs that would otherwise be
invisible to CI — a missing import in `env.py` or a broken upgrade script is
detected at test time, not in production.

```python
# tests/integration/conftest.py — session-scoped engine setup
@pytest.fixture(scope="session")
async def test_engine() -> AsyncEngine:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Real migrations, not create_all — validates migration scripts
    await _run_test_migrations(TEST_DATABASE_URL)
    yield engine
    ...
```

**Rule:** Never use `Base.metadata.create_all()` in integration tests.
Always use `alembic upgrade head`. If a migration is broken, the test must fail.

### Post-Assertion Pattern — RULE-TEST-02

After any state-changing test (create, update, delete), verify the database
state directly in **all affected tables**. Do not rely solely on the API
response — the response may be correct while the DB state is wrong.

```python
async def test_setup_complete_creates_provider(db_session):
    """After setup, user_providers table must have a row."""
    await client.post("/api/v1/setup/complete", json=setup_payload, ...)

    # Verify DB state, not just API response
    result = await db_session.execute(select(UserProvider))
    providers = result.scalars().all()
    assert len(providers) == 1
    assert providers[0].provider_name == "openai"
    assert providers[0].encrypted_api_key is not None
```

This pattern catches bugs like "the API returns success but silently skips
writing to a secondary table."

### Environment Variable Fixtures

Integration tests that depend on environment variables (e.g., `NARRARE_ENCRYPTION_KEY`)
use `autouse` fixtures to set them:

```python
@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure NARRARE_ENCRYPTION_KEY is set for all integration tests."""
    from cryptography.fernet import Fernet
    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
```

**Scoping note:** Use function-scoped `autouse` fixtures (not session-scoped)
for env vars that must be isolated per test. Add negative tests (missing env var
→ expected error) where the behavior is security-relevant.

### Factory Helpers (not fixtures)

```python
# tests/factories.py — plain functions, not pytest fixtures
def make_chapter(**overrides) -> Chapter:
    """Create a Chapter with sensible defaults for testing."""
    ...

def make_novel(**overrides) -> Novel:
    """Create a Novel with sensible defaults for testing."""
    ...
```

### Pytest Plugins

| Plugin | Version | Purpose |
|--------|---------|---------|
| `pytest-xdist` | ≥3.6 | Parallel test execution (`-n auto`) |
| `pytest-randomly` | 4.1.0 | Random test order — catches hidden state dependencies |
| `pytest-timeout` | ≥2.3 | 10s timeout per test — prevents hanging tests |
| `hypothesis` | ≥6.100 | Property-based testing for pure functions |

### Running Tests

```bash
# justfile commands:
just test          # Parallel execution (xdist -n auto, randomly enabled)
just test-unit     # Parallel unit tests only
just test-single   # Single-threaded for debugging (disables randomly)
```

Use `just test-single` when:
- Debugging a test that fails only under random ordering
- Stepping through tests with a debugger
- Isolating a flaky test

---

## Coverage Standards

| Module | Level | Minimum | Target |
|--------|-------|---------|--------|
| `core/llm/` | Unit | 95% | 100% |
| `core/prompts/` | Unit | 95% | 100% |
| `core/context/` | Unit | 90% | 95% |
| All other `core/` | Unit | 90% | 95% |
| `apps/api/*/service.py` | Unit | 85% | 90% |
| `apps/api/*/repository.py` | **Integration** | 80% | 90% |
| `apps/api/*/router*.py` | Integration | 80% | 85% |
| i18n Namespace Registry | Integration | 100% | 100% |
| API Response Contracts | Unit | Per schema | Per schema |
| Router Configuration | Unit | Per router | Per router |

**Contract test file patterns:**

| Test Type | File Pattern |
|-----------|-------------|
| i18n Namespace Registry | `packages/web/__tests__/i18n-namespace-registry.test.ts` |
| API Response Contracts | `tests/unit/api/test_*_contract.py` |
| Router Configuration | `tests/unit/api/test_*_router_contract.py` |

Coverage below minimum = CI failure. No exceptions.

**What coverage does NOT mean:**
High coverage does not mean good tests. A test that calls a function without
asserting anything passes coverage. We check assertion quality in PR review.

---

## Frontend Tests — packages/web/

**Runner:** Vitest 3.x
**Environment:** jsdom
**Component Testing:** `@testing-library/react` + `@testing-library/user-event`
**API Mocking:** MSW v2.14.6 (Mock Service Worker)
**State Testing:** Direct Zustand store testing

**Test location:** `packages/web/**/*.test.{ts,tsx}`

**Commands:**
- `pnpm test` — run all frontend tests
- `pnpm test:watch` — watch mode
- `pnpm test -- --coverage` — run with coverage report

**MSW Handlers:** `packages/web/mocks/handlers.ts`
**Test Data:** `packages/web/mocks/data.ts`
**Setup:** `packages/web/setupTests.ts`

### What Gets Tested

**Utility functions** (`lib/utils.ts`, `lib/api/client.ts`):
- Every exported function gets a unit test
- Happy path + edge cases (empty input, boundary values, error cases)
- Time-dependent functions use `vi.useFakeTimers()`
- Example: `debounce`, `cn`, `formatWordCount`, `formatRelativeTime`, `truncate`

**Zustand stores** (`lib/stores/`):
- Test state transitions directly via `useStore.getState()` and `useStore.setState()`
- No need to render components — test the store as a plain object
- Verify initial state, action results, edge cases
- Example: `editorStore` — test `toggleFocusMode` restores sidebar

**UI Components** (`components/`):
- Render via Testing Library, assert on DOM structure and ARIA attributes
- Test user interactions via `@testing-library/user-event`
- Test variant rendering (different props → different classes/behavior)
- Test accessibility: ARIA labels, roles, live regions
- Example: Button — test variants, sizes, loading state, disabled state

**API Client** (`lib/api/client.ts`):
- Token management functions (`setAccessToken`, `getAccessToken`, `clearAccessToken`)
- Token refresh logic (requires MSW for HTTP mocking)
- Error handling (401 redirect, network errors)

### Frontend Coverage Targets

| Module | Minimum | Target |
|--------|---------|--------|
| `lib/utils.ts` | 90% | 95% |
| `lib/stores/` | 85% | 90% |
| `lib/api/` (token management) | 85% | 90% |
| `components/ui/` | 80% | 85% |
| `components/editor/` | 70% | 80% |
| `components/dashboard/` | 70% | 80% |

### Testing Patterns

**Store testing (no rendering needed):**
```typescript
import { useEditorStore } from "@/lib/stores/editorStore"

describe("editorStore", () => {
  beforeEach(() => useEditorStore.setState({
    activeChapterId: null, saveStatus: "idle", sidebarOpen: true,
    contextPanelOpen: false, focusMode: false,
  }))

  it("toggles focus mode and restores sidebar on exit", () => {
    const { toggleFocusMode } = useEditorStore.getState()
    toggleFocusMode()
    expect(useEditorStore.getState().focusMode).toBe(true)
    expect(useEditorStore.getState().sidebarOpen).toBe(false)
    toggleFocusMode()
    expect(useEditorStore.getState().sidebarOpen).toBe(true) // restored
  })
})
```

**Component testing (render + interact):**
```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

it("calls onClick when clicked", async () => {
  const user = userEvent.setup()
  const handleClick = vi.fn()
  render(<Button onClick={handleClick}>Click</Button>)
  await user.click(screen.getByRole("button", { name: "Click" }))
  expect(handleClick).toHaveBeenCalledOnce()
})
```

**Variant testing (assert on classes):**
```typescript
it("applies variant-specific Tailwind classes", () => {
  const { rerender } = render(<Button variant="primary">P</Button>)
  expect(screen.getByRole("button").className).toContain("bg-[var(--color-accent)]")

  rerender(<Button variant="danger">D</Button>)
  expect(screen.getByRole("button").className).toContain("bg-[var(--color-error)]")
})
```

### What NOT to Test

- **Next.js internals** — routing, layouts, middleware framework behavior
- **Third-party library behavior** — TipTap editor internals, Radix primitives
- **CSS styling** — visual appearance is verified manually or via E2E screenshots
- **Server components** — they have no client-side logic (`loading.tsx`, `page.tsx` wrappers)

---

## Property-Based Testing — Hypothesis

Pure functions in `core/` get property-based tests using Hypothesis.
These test that functions handle arbitrary input correctly.

**Location:** `tests/unit/core/**/*_hypothesis.py`
**Library:** `hypothesis>=6.100`

**Patterns:**
- **No-crash:** any input → never raises
- **Deterministic:** same input → same output
- **Round-trip:** `parse(build(x)) == x`

**When to use Hypothesis:**
- Pure functions (no I/O, no state)
- Parsing/serialization code
- Data transformation functions

**When NOT to use Hypothesis:**
- Async functions (use regular tests)
- File I/O functions
- Pydantic models (built-in validation is sufficient)

---

## E2E Tests

E2E tests use **Playwright** with route mocking for LLM responses.

**Location:** `tests/e2e/`
**Status:** Implemented in Phase 5. Uses Playwright with route mocking for LLM responses.
**CI:** Run only on main branch with full stack. LLM provider responses are mocked via Playwright route interception — no real LLM API calls.
**Run time target:** < 5 minutes total.

---

## Naming Conventions

```
test_<what>_<condition>_<expected_result>

test_write_chapter_with_valid_request_returns_draft
test_write_chapter_when_llm_fails_raises_writing_error
test_write_chapter_with_empty_content_raises_validation_error
test_gateway_run_with_intent_write_selects_correct_model
```

---

## What You Do NOT Do

- You do not write production code (Implementation Agent)
- You do not define what a feature should do (Architecture Agent)
- You do not configure test infrastructure like Docker Compose (Deployment Agent)

---

## Context You Load Automatically

```
docs/_shared/
├── CONSTRAINTS.md
└── GLOSSARY.md

docs/development/testing-
├── AGENT.md               ← this file
├── TEST_STRATEGY.md       ← detailed strategy per domain
├── PATTERNS.md            ← full fixture and assertion examples
└── COVERAGE_GOALS.md      ← per-module targets with rationale
```

---

## Session Closing Protocol

At the end of every testing session:

**1. Coverage delta** — what changed:
```
Before: writing/ → 62% | After: writing/ → 84%
Remaining gap: session_service.py — 3 methods untested (listed)
```

**2. Test quality notes** — anything that needs improvement:
```
WEAK TEST: test_write_chapter_success — asserts only status code, not response body.
Needs stronger assertion in next session.
```

**3. New fixtures added** — so Implementation Agent knows what's available.

---

> Maintained by: Architecture Agent
> Do not edit without Architecture session and DECISIONS.md entry
