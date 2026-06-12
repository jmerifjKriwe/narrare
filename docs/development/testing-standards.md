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

class TestChapterSummaryService:
    async def test_returns_summary_on_success(
        self, service: ChapterSummaryService, fake_repo: FakeChapterRepository
    ) -> None:
        chapter = make_chapter(content="Once upon a time...")
        fake_repo.seed(chapter)

        result = await service.summarize(chapter.id)

        assert result.summary != ""
        assert result.word_count > 0

    async def test_skips_empty_chapter(
        self, service: ChapterSummaryService, fake_repo: FakeChapterRepository
    ) -> None:
        chapter = make_chapter(content="")
        fake_repo.seed(chapter)

        result = await service.summarize(chapter.id)

        assert result.summary == ""

    async def test_raises_on_missing_chapter(
        self, service: ChapterSummaryService
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.summarize(uuid4())
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

*Ausnahme: Agents/LLM-Dependencies werden mit TestModel/FunctionModel gemockt — nicht mit Fake-Klassen.*

```
tests/fakes/
├── __init__.py
├── fake_repositories.py      ← FakeChapterRepo, FakeNovelRepo, etc.
├── fake_services.py          ← FakeNovelService, FakeAuthService, etc.
└── fake_setup.py             ← FakeProviderService, FakeDemoLoader
```

### What IS allowed

```python
# ✅ Fake classes for domain dependencies
from tests.fakes import FakeChapterRepository

fake_repo = FakeChapterRepository()
fake_repo.seed(make_chapter(id=uuid4()))

# ✅ TestModel for agent-level LLM mocking
from pydantic_ai.models.test import TestModel
model = TestModel(custom_output_text="Summary text")

# ✅ patch() for external functions that are not dependencies
with patch("narrare.auth.service.hash_password", return_value="hashed"):
    await service.register(request)

# ✅ AsyncMock() on Fake objects for individual method overrides
fake_repo.get_by_id = AsyncMock(return_value=None)
```

### What is FORBIDDEN

```python
# ❌ Bare MagicMock() without spec=
session = MagicMock()
repo = MagicMock()

# ❌ MagicMock as replacement for a domain dependency
service._repo = MagicMock()  # Use FakeChapterRepository instead

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
| **LLM/Agent testing** | TestModel statt Fake — TestModel testet den echten pydantic-ai Code-Path | MagicMock umgeht den Agent komplett |

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
| Service unit tests | `TestModel` (via fixture) | Service instantiates agents |
| Gateway unit tests | `TestModel` / `FunctionModel` | Tests the real agent code path |
| Agent-level tests | `TestModel` + `capture_run_messages` | Asserts tool call behavior |
| Integration tests | `TestModel` + dependency override | End-to-end through HTTP |
| E2E tests | Playwright route mocking | Full browser stack |

### `TestModel` — Deterministic Agent Responses

`TestModel` (from `pydantic_ai.models.test`) replaces the real LLM with deterministic responses.

```python
async def test_summary_agent_returns_structured_output() -> None:
    model = TestModel(custom_output_text="A short summary.")
    agent = ChapterSummaryAgent(model=model)
    deps = SummaryDeps(language="en", chapter_title="Ch 1")
    result = await agent.run(prompt="Summarize this.", deps=deps)
    assert result.summary == "A short summary."
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

### What CHANGED — Testing Migration Notes

**Service-Level Tests**: Services instantiieren jetzt Agents direkt.
Der LLM-Aufruf wird über `TestModel` gemockt — nicht mehr über `FakeLLMGateway`.

**Agent-Level Tests**: Agents werden mit `TestModel` oder `FunctionModel`
getestet (siehe Tabelle oben).

**Integration Tests**: `TestModel` wird via Dependency Injection eingespielt.
Keine echten LLM-API-Calls — `ALLOW_MODEL_REQUESTS = False` in conftest.py verhindert das.

**Fake-Klassen existieren weiterhin** für Repository/Service-Protokolle.
Nur für Agent/LLM-Dependencies werden jetzt TestModel/FunctionModel verwendet.

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
def test_model() -> TestModel:
    """Pydantic AI TestModel — deterministische LLM-Responses."""
    return TestModel(custom_output_text="Default response.")

@pytest.fixture
def fake_chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()

# Per-domain fixtures in test subdirectories:
# tests/unit/api/chapters/conftest.py
@pytest.fixture
def service(fake_chapter_repo, test_model, registry, config) -> ChapterSummaryService:
    return ChapterSummaryService(
        registry=registry,
        config=config,
        chapter_repo=fake_chapter_repo,
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

### Auto-Tagging — RULE-TEST-03

Tests are automatically tagged based on their directory path. No manual markers needed.

**Mechanism:** `pytest_collection_modifyitems` hook in `tests/conftest.py` assigns markers:

| Directory | Auto-assigned Markers |
|-----------|----------------------|
| `tests/unit/` | `unit` |
| `tests/integration/` | `integration`, `requires_db` |
| `tests/e2e/` | `e2e` |

**What this means for developers:**
- New tests automatically get the correct markers — no `pytestmark` needed
- `--strict-markers` is safe to use (all markers registered in `pytest_configure`)
- Select tests by marker: `pytest -m unit`, `pytest -m integration`, `pytest -m e2e`
- Exclude tests: `pytest -m "not e2e"`

**When you still need manual markers:**
- Cross-cutting concerns like `@pytest.mark.filterwarnings` or `@pytest.mark.parametrize`
- Special markers for specific test behaviors (e.g., `@pytest.mark.timeout(30)`)

**Do NOT add** `pytestmark = pytest.mark.requires_db` to integration test files — auto-tagging handles this.

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

### Fast Developer Feedback (Pytest Collection Fastpath)

Full pytest collection gathers ~6,600+ tests across unit, integration, and e2e
directories. For the local developer loop, unit-only testing is the primary
fast-feedback path:

| Command | Scope | Collection time | Run time |
|---------|-------|----------------|----------|
| `just test-unit` | `tests/unit/` only (~6,160 tests) | ~14s | ~2.5min |
| `just test` | `tests/` all levels (~6,670 tests) | ~17s | varies |

**Integration and E2E tests are separate explicit gates**, not mixed into the
unit test loop. They run in CI (`test-integration` and `test-e2e` jobs) or
locally via explicit commands:

```bash
just test-integration   # Requires Docker services
just test-e2e           # Requires full stack (main branch CI only)
```

**Pre-merge checklist**: `just test-unit` passes locally → CI runs
architecture, lint, typecheck, security, unit + integration + e2e.

### Coverage Run Guidance

When running coverage locally, use the `just` recipes — they work from any
directory and match the allowed opencode bash permission patterns:

| Command | Scope | Use |
|---------|-------|-----|
| `just test-cov` | All tests | Full coverage report with HTML output |
| `just test-unit-cov` | Unit tests only | Fast coverage feedback (no Docker needed) |
| `uv run pytest tests/ --cov --cov-report=term-missing` | All tests | Same as `just test-cov` but without HTML |

**Avoid** environment variable prefixes like `COVERAGE_FILE=/tmp/.coverage uv run pytest tests/ --cov` — these do not match allowed bash patterns (`just*` and `uv*` are allowed, but `COVERAGE_FILE=... uv*` is not).

**Permission model:** The opencode bash permission system allows `just*` and
`uv*` command patterns. All commands above use these prefixes. If a different
coverage command pattern is needed, it must be added to the global opencode
permission config (outside this project's scope).

### Eval Types (Pydantic Evals)

| Type | Secrets needed | When | CI location |
|------|---------------|------|-------------|
| Smoke | None (deterministic) | Every PR | `architecture` job |
| Runtime | Provider API key | Nightly / manual | Separate workflow |
| Judge | LLM judge model key | Nightly / manual | Separate workflow |

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
**Environment:** happy-dom
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

### Runtime Baseline and Vitest Configuration

Frontend tests are expected to complete in **<120 seconds** for the full suite.
The current stable baseline is 186 test files / 1,683 tests passing in
`112.43s`, `115.04s`, and `111.95s` across three consecutive runs.

Vitest uses `happy-dom`, `pool: threads`, and `maxWorkers: 6` to keep the browser-like
environment lightweight while preserving parallelism. Do not switch back to heavier
DOM environments or single-threaded execution unless a specific test requires it and
the runtime baseline is revalidated.

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

### Snapshot Testing Rules — RULE-TEST-04

Snapshot tests capture component render output and compare against a stored baseline.
While convenient, they create maintenance burden if overused.

**When snapshot tests ARE appropriate:**
- Very static UI elements (icons, static layouts, error states)
- Email/notification templates
- API response schemas that rarely change

**When snapshot tests are FORBIDDEN:**
- Components with dynamic content (user-generated text, dates, timestamps)
- Components with randomized output (shuffle, UUIDs, animations)
- As a substitute for meaningful assertions — snapshot != tested behavior

**Rules:**
1. Every snapshot must have a descriptive name explaining WHAT it verifies
2. Review snapshot diffs carefully during updates — never blindly accept
3. If a snapshot changes frequently (>3 times in a sprint), convert to explicit assertions
4. Keep snapshot files small — test individual components, not entire pages

**Pattern for snapshot testing:**
```typescript
import { render } from "@testing-library/react"
import { StaticElement } from "./StaticElement"

it("renders status badge correctly", () => {
  const { container } = render(<StaticElement status="active" />)
  expect(container).toMatchSnapshot()
})
```

**Anti-pattern:**
```typescript
// ❌ BAD: Snapshotting dynamic content
it("renders user profile", () => {
  const { container } = render(<UserProfile user={dynamicUser} />)
  expect(container).toMatchSnapshot() // Will break on every user change
})

// ✅ GOOD: Explicit assertions on dynamic content
it("displays user name and email", () => {
  render(<UserProfile user={testUser} />)
  expect(screen.getByText(testUser.name)).toBeInTheDocument()
  expect(screen.getByText(testUser.email)).toBeInTheDocument()
})
```

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

> **Location:** `tests/e2e/`
> **Tool:** Playwright (Python sync API)
> **CI:** Main branch only — full stack (API + Frontend + PostgreSQL + Redis)
> **Run time target:** < 5 minutes total
> **Current status:** 16 tests passing, implemented in Phase 5

### Infrastructure — `NARRARE_E2E_TEST` Mode

The environment variable `NARRARE_E2E_TEST=1` overrides **all** LLM provider factories in
`registry.py` to return `pydantic_ai.TestModel()`. This prevents server-side LLM calls from
hitting real providers with invalid API keys.

| Aspect | Detail |
|--------|--------|
| Env var | `NARRARE_E2E_TEST=1` |
| Effect | All `get_*_model()` factories return `TestModel()` |
| Local start | `just dev-e2e` — starts API with the env var set |
| CI | `NARRARE_E2E_TEST` is set in the `test-e2e` job environment |
| Scope | Server-side only — does **not** affect browser-side requests |

**Why Playwright route mocks alone aren't enough:** `page.route()` intercepts browser-side
requests only. Server-side calls (API → LLM provider) bypass the browser entirely, so the
env var override is essential.

### Key Patterns

#### Auth Proxy Pattern (`authenticated_page` fixture)

Do **not** use `page.route()` mocks that return fake tokens — fake tokens cause `401` on
subsequent real API calls. Instead, proxy API requests with a real `Authorization` header:

```python
# conftest.py — authenticated_page fixture (simplified)
def _api_route_handler(real_token: str):
    async def handle(route: Route):
        headers = {**route.request.headers, "Authorization": f"Bearer {real_token}"}
        response = await route.fetch(headers=headers)
        await route.fulfill(response=response)
    return handle

page.route("**/api/v1/**", _api_route_handler(token))
```

Additionally, the `narrare_auth` cookie must be set via `page.add_init_script()` for
Next.js middleware (server-side route protection).

#### Wizard Step 4 Robustness

Step 4 requires careful handling due to dynamic content:

| Issue | Solution |
|-------|----------|
| Text detection fails | Use `page.inner_text("body")` — not `.bg-card.border` selector |
| Button state unknown | Always call `_click_next()` **outside** conditional blocks at Step 4 |
| Partial text match | Check for `"provider"`, `"openai"`, AND `"api key"` in step text |
| Button not ready | Wait for Next button enabled via `wait_for_function` before clicking |

The `_click_next()` call is **idempotent** — safe to call unconditionally at Step 4.

#### Editor Content Persistence

Programmatic `editor.commands.insertContent()` does **not** reliably trigger TipTap's
autosave debounce. For deterministic persistence:

1. Use the explicit **Save button** click instead of relying on autosave.
2. **Store the novel URL** before navigating away.
3. Use the stored URL for back-navigation — don't search for links on what might be the
   login page.

This follows **RULE-04** (hard limits enforce decomposition) and **RULE-06** (one
responsibility) — editor helpers are in `test_helpers.py`, not inline in tests.

#### Warmup Fixture

`warmup_api()` is a session-scoped fixture that pre-warms the asyncpg connection pool
(~30 s cold start). Per **RULE-11**, it uses `contextlib.suppress(Exception)` instead of
bare `except Exception: pass`:

```python
@pytest.fixture(scope="session")
def warmup_api():
    with contextlib.suppress(Exception):
        requests.get(f"{API_BASE}/healthz", timeout=60)
```

### File Structure

```
tests/e2e/
├── conftest.py           ← Fixtures: fresh_page, authenticated_page, warmup_api, register_unique_user
├── test_helpers.py       ← Shared helpers: _click_next, _wait_for_wizard_ready, setup_dashboard_api_mocks
├── mocks/
│   └── llm_responses.py  ← Canned LLM responses + Playwright route handlers
├── test_auth_flow.py          ← Registration + login
├── test_setup_wizard.py       ← Wizard steps 1-4
├── test_wizard_completion.py  ← Wizard completion + redirect
├── test_editor_autosave.py    ← Editor autosave
├── test_editor_persistence.py ← Editor content persistence
├── test_novel_dashboard.py    ← Dashboard display + navigation
├── test_kb_worldbuilding.py   ← KB + worldbuilding
└── test_hero_flow.py          ← End-to-end hero flow
```

### Running E2E Tests

```bash
# Start stack in E2E mode (API uses TestModel for all LLM calls)
just dev-e2e

# Run all E2E tests
just test-e2e

# Run specific test
uv run pytest tests/e2e/test_auth_flow.py -v -m e2e --timeout=60
```

---

## LLM Prompt Evaluation — Pydantic Evals

> **Scope:** Qualitative evaluation of LLM prompt outputs.
> **Python-native eval layer** — may share fixtures with runtime code, but keeps a
> separate eval cadence from deterministic pytest gates.
> **Reference:** ADR-032

### Why a Separate System

Evaluating prompt quality is fundamentally different from testing code correctness:

| Aspect | pytest (Code Tests) | Pydantic Evals |
|--------|---------------------|--------------------------|
| LLM calls | Mocked (TestModel) | **Real or judged**, depending on suite |
| Result | Pass/Fail | **Score (0–1)** |
| Determinism | Deterministic | **Non-deterministic** |
| Cadence | Every commit | Nightly / Manual |
| Comparison | Current vs. Expected | **Before vs. After** |

### Location

```
evals/
├── __main__.py          # python -m evals
├── runner.py            # CLI runner
├── models.py            # typed case input/output models
├── datasets/            # code-first Dataset/Case definitions
│   └── ...
├── evaluators/          # custom Evaluator implementations
│   └── ...
├── tasks/               # smoke and runtime task entrypoints
│   └── ...
├── baselines/           # drift baselines
└── results/             # JSON reports uploaded by CI
```

### Running Evals

```bash
# Smoke mode — deterministic, no provider secrets needed
uv run python -m evals run --suite all --mode smoke

# Runtime mode — needs a configured model
uv run python -m evals run --suite kb_extraction --mode runtime
```

### Writing New Test Cases

1. Create or extend a Python dataset/case in `evals/datasets/`.
2. Exercise Narrare's actual agent, `PromptComposer`, and `ModelRegistry` paths.
3. Add evaluators for qualitative scoring, guardrails, and structured-output checks.
4. Set an explicit threshold appropriate to the suite.
5. Store CI-readable results under `evals/results/` or the configured artifact path.

### Assertion Types

| Evaluator | Use for |
|-----------|---------|
| LLM judge evaluator | Qualitative narrative quality (tone, style, structure) |
| Similarity/baseline evaluator | Similarity against golden outputs where useful |
| Guardrail evaluator | Prohibited phrases, refusal leakage, scope violations |
| Structured-output evaluator | Schema validity and validator policy checks |
| Custom Python evaluator | Domain-specific scoring functions |

### CI Integration

- **PR CI (architecture job):** Smoke evals run as a blocking gate — deterministic, no secrets needed
- **Nightly:** Runtime evals run automatically at 3 AM UTC on main branch (needs provider secrets)
- **Manual:** `workflow_dispatch` with optional test case filter
- **Drift check:** `check_eval_drift.py` runs in PR CI (warning-only initially)
- **Results:** Uploaded as GitHub Actions artifacts (30-day retention)
- **Runtime evals are NOT in the PR CI pipeline** — they need real API keys

### Baseline Strategy

Baselines are versioned golden outputs committed to the repository.
When prompts change intentionally:
1. Run evals with new prompt
2. Review output quality
3. Create new baseline version (`writing-v2.json`)
4. Keep old baselines for historical comparison

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
