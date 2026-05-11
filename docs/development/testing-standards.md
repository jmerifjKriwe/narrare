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
└── e2e/            ← Full stack. Real services including LLM (cheapest model).
                      Run only on main branch CI.
                      Run time target: < 5 minutes total.
                      Tool: Playwright (planned for Phase 5).
                      Status: Not yet implemented.
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

```python
@pytest.fixture(scope="session")
async def db_engine() -> AsyncEngine:
    """Real Postgres engine via Docker Compose."""
    ...

@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Transaction-wrapped session — rolls back after each test."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(conn) as session:
            yield session
            await conn.rollback()
```

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

**MSW Handlers:** `packages/web/mocks/handlers.ts`
**Test Data:** `packages/web/mocks/data.ts`
**Setup:** `packages/web/setupTests.ts`

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

E2E tests will use **Playwright** (planned for Phase 5).

**Location:** `tests/e2e/`
**Status:** Not yet implemented.
**CI:** Run only on main branch with full stack including LLM (cheapest model).
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
