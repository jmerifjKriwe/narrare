# ADR-030 — MagicMock-to-Fake Migration Plan for Memory Tests

> **Status:** 🔄 Proposed
> **Date:** 2026-06-04
> **Deciders:** Architecture Agent, Docs Specialist
> **Supersedes:** —

---

## Context

The memory module (`apps/api/narrare/memory/`) has unit tests that use patterns which are inconsistent with RULE-TEST-01 (Fake classes instead of MagicMock). A review of the three flagged test files reveals the following current state:

### Current State of Memory Test Files

| File | Mocking Pattern | Issue |
|------|----------------|-------|
| `tests/unit/api/memory/test_feedback_service.py` | `MagicMock(spec=FeedbackRepository)` on line 41 | spec'd mock, not a Protocol-conforming Fake |
| `tests/unit/api/memory/test_analysis_service.py` | Local inline Fakes (`FakeFeedbackRepo`, `FakeProfileRepo`) | Fakes exist but are local — not in `tests/fakes/`, no conformance tests |
| `tests/unit/api/memory/test_repository.py` | Local `FakeAsyncSession` | Tests repositories at unit level (per testing-standards, repos are integration-tested only) |

### Additional Observations

1. **Contracts exist but are incomplete.** `apps/api/narrare/memory/contracts.py` defines `FeedbackServiceProtocol`, `PreferenceServiceProtocol`, and `PreferenceAnalysisServiceProtocol` (all `@runtime_checkable`). However, there are **no Protocol definitions** for `FeedbackRepository` or `PreferenceProfileRepository` — these repositories are typed as concrete classes, not Protocols.

2. **`test_feedback_service.py` uses `MagicMock(spec=FeedbackRepository)`** — this provides interface safety via `spec=` but is still a MagicMock, not a Fake class. RULE-TEST-01 requires Fake classes implementing Protocol contracts.

3. **`test_analysis_service.py` has inline Fakes** that are close to correct but: (a) use `Any` typing instead of proper Protocol types, (b) are not in `tests/fakes/`, (c) have no conformance tests.

4. **`test_repository.py` unit-tests repositories** — testing-standards.md states "Repositories are NOT unit-tested" because "mocking an AsyncSession to verify that `.execute()` was called tests nothing meaningful." These tests should be integration tests with a real database.

### Why This Matters

RULE-TEST-01 exists because MagicMock-based tests silently pass when Protocols change. A Fake class that implements a `@runtime_checkable` Protocol will fail at test time when the Protocol adds or removes a method. This is the core safety benefit — contract enforcement through conformance.

---

## Decision Drivers

- **RULE-TEST-01 compliance** — all domain dependencies should use Fake classes
- **Conformance testing** — Fakes must pass `isinstance(fake, Protocol)` checks
- **No regressions** — migration must not change test semantics or reduce coverage
- **Pragmatism** — prioritize by impact; don't migrate what doesn't need it

---

## Options Considered

### Option A — Full Migration (3 phases)

Create Protocols for all repository interfaces, create Fakes in `tests/fakes/`, add conformance tests, migrate all three test files.

**Pros:**
- Full RULE-TEST-01 compliance for the memory module
- Conformance tests catch Protocol drift
- Fakes are reusable across test files

**Cons:**
- Requires adding Protocols for repositories (contracts.py changes)
- `test_repository.py` may need to become an integration test (larger change)
- Moderate effort

### Option B — Minimal Migration (feedback service only)

Only migrate `test_feedback_service.py` (the one using `MagicMock`), leave inline Fakes and repository tests as-is.

**Pros:**
- Smallest change, addresses the only true MagicMock usage
- No new Protocols needed

**Cons:**
- Incomplete RULE-TEST-01 compliance
- Inline Fakes still lack conformance tests
- Repository tests still violate testing-standards guidance

### Option C — Defer Entirely

Document as known tech debt, address when memory module undergoes significant changes.

**Pros:**
- No effort now
- Module is functional and tested

**Cons:**
- Accumulating test debt
- Inconsistency with other modules that follow RULE-TEST-01

---

## Decision

**We choose Option A: Full Migration in 3 phases**, with a note that Phase 3 (repository test restructuring) is the lowest priority and can be deferred.

The memory module is a core feature (preference learning, feedback analysis). It deserves the same test quality standards as other modules. The migration is straightforward because contracts already exist for service-level Protocols.

---

## Implementation Plan

### Phase 1: Complete Contracts — Estimated effort: S

**Goal:** Ensure all memory module dependencies have Protocol definitions.

**Tasks:**
1. Add `FeedbackRepositoryProtocol` to `apps/api/narrare/memory/contracts.py`
   - Methods: `create(event) -> FeedbackEventModel`, `get_event_count(user_id, project_id) -> int`, `get_events_batch(user_id, project_id, *, limit) -> list`
   - Mark `@runtime_checkable`
2. Add `PreferenceProfileRepositoryProtocol` to the same file
   - Methods: `upsert(profile) -> PreferenceProfileModel`, `get(user_id, project_id) -> PreferenceProfileModel | None`
   - Mark `@runtime_checkable`
3. Verify existing service Protocols match current implementations

**Files changed:** `apps/api/narrare/memory/contracts.py`

### Phase 2: Create Fakes and Conformance Tests — Estimated effort: M

**Goal:** Shared Fake classes in `tests/fakes/` with conformance verification.

**Tasks:**
1. Create `tests/fakes/fake_memory_repos.py`:
   - `FakeFeedbackRepository` — implements `FeedbackRepositoryProtocol`
   - `FakePreferenceProfileRepository` — implements `PreferenceProfileRepositoryProtocol`
   - Both with `seed()`, `call_count()`, `assert_called()` helpers (standard Fake pattern)
2. Move `FakeCoreFeedback` and `FakeEventPublisher` from `test_feedback_service.py` to `tests/fakes/fake_services.py` (or a new `fake_memory_services.py`)
3. Add conformance tests to `tests/unit/test_fake_conformance.py`:
   ```python
   def test_fake_feedback_repo_conforms():
       assert isinstance(FakeFeedbackRepository(), FeedbackRepositoryProtocol)

   def test_fake_preference_profile_repo_conforms():
       assert isinstance(FakePreferenceProfileRepository(), PreferenceProfileRepositoryProtocol)
   ```
4. Keep `FakeModelRegistry` and `FakeFeedbackEvent` as test-local helpers (they are test-specific, not shared domain Fakes)

**Files changed:** `tests/fakes/`, `tests/unit/test_fake_conformance.py`

### Phase 3: Migrate Test Files — Estimated effort: M

**Goal:** Replace all MagicMock and inline Fake usage with shared Fakes.

**Tasks for `test_feedback_service.py`:**
1. Replace `MagicMock(spec=FeedbackRepository)` with `FakeFeedbackRepository`
2. Replace inline `FakeCoreFeedback` / `FakeEventPublisher` with imports from `tests/fakes/`
3. Remove `# type: ignore[arg-type]` comments (Fakes implement Protocols)

**Tasks for `test_analysis_service.py`:**
1. Replace inline `FakeFeedbackRepo` with `FakeFeedbackRepository` from `tests/fakes/`
2. Replace inline `FakeProfileRepo` with `FakePreferenceProfileRepository` from `tests/fakes/`
3. Remove `# type: ignore[arg-type]` comments

**Tasks for `test_repository.py`:**
1. **Decision needed:** These tests unit-test repository SQL logic with a fake session.
   Per testing-standards.md, "Repositories are NOT unit-tested" — they should be integration tests.
   However, the current tests verify basic persistence semantics (add/flush/refresh), not SQL queries.
2. **Recommended approach:** Keep as unit tests for now (they test the thin wrapper, not SQL).
   Add integration tests for actual query behavior when the memory module gets integration test coverage.
3. Replace local `FakeAsyncSession` with a properly typed Fake if a `SessionProtocol` is ever defined.
   Until then, the local `FakeAsyncSession` is acceptable (infrastructure, not domain).

### Cleanup (after all phases):

Remove any architecture exception entries related to memory test mocking from:
- `docs/_shared/CONSTRAINTS.md` §7 (if exceptions were registered)
- `pyproject.toml [tool.narrare.architecture.exceptions]` (if entries exist)
- Inline `# narrare: allow` comments in the migrated test files (if present)

---

## Consequences

**Positive:**
- Full RULE-TEST-01 compliance for the memory module
- Better refactor safety — Protocol changes break Fakes immediately
- Reusable Fakes across all memory-related test files
- Conformance tests catch stale Fakes automatically
- Consistent with test patterns used by other modules (chapters, novels, etc.)

**Negative / Tradeoffs:**
- Short-term effort to create and maintain Fakes (2–3 new files)
- `test_repository.py` status is ambiguous — per standards it should be integration, but the tests are useful for basic smoke testing

**Risk:** Low — existing tests pass, and Fakes will produce equivalent behavior. The conformance tests provide a safety net.

---

## Exception #11 (Metrics Router) — Recommendation

`tests/unit/api/metrics/test_metrics_router.py` (exception #11) mocks SQLAlchemy's Engine object for a health-check endpoint. SQLAlchemy Engine is **infrastructure**, not domain — there is no Protocol to conform to. This exception should remain permanently.

**Recommendation:** Reclassify from "exception" to "accepted pattern" in the rules. Add a note to `docs/development/testing-standards.md` in the RULE-TEST-01 section:

> Infrastructure-level mocks (SQLAlchemy Engine, Redis client, HTTP transport) are an accepted pattern when no domain Protocol exists. This is not a RULE-TEST-01 violation — the rule applies to domain dependencies with defined Protocols.

---

## Review Trigger

- When memory module contracts change (new methods, renamed parameters)
- When testing-standards.md is updated regarding repository testing policy
- After 3 months: audit conformance tests are passing and Fakes are up to date

---

## Related

- `docs/_shared/CONSTRAINTS.md` §7 (Approved Exceptions Register)
- `docs/development/testing-standards.md` (RULE-TEST-01, Fake Class Pattern)
- `apps/api/narrare/memory/contracts.py` (existing Protocols)
- `tests/fakes/` (existing Fake classes for reference)
- ADR-028 (Architecture Exception SSOT)
- ADR-003 (Contracts Before Implementation)
