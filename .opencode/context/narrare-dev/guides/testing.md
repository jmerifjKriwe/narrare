<!-- Context: narrare-dev/guides/testing | Priority: P1 | Source: docs/development/testing-standards.md | Updated: 2026-06-12 -->

# Testing Guide

Three-level test architecture with strict level separation. A test lives at the **lowest level** where it can be meaningful.

## Test Levels

| Level | Location | Scope | Time Target |
|-------|----------|-------|-------------|
| **Unit** | `tests/unit/` | Fast, pure, no I/O. Mock everything external. | < 5s total |
| **Integration** | `tests/integration/` | Real DB + Redis, mocked LLM. Docker Compose. | < 60s total |
| **E2E** | `tests/e2e/` | Full stack. LLM mocked via Playwright + env var. Main branch CI only. | < 5min total |

**Never** use a real DB in a unit test. **Never** mock the DB in an integration test.

## What Gets Tested Per Level

**Unit — Services & Core Logic**: Every public method gets ≥3 tests (happy path, domain error, edge case). Services use constructor-injected deps → tests inject Fakes. **Repositories are NOT unit-tested** — SQL logic is meaningless with mocked sessions.

**Integration — Repositories & Routers**: Repository methods with real DB. Router endpoints via `httpx.AsyncClient` (200/201 schema validation, 401, 404, 422). Every 200/201 response must include `Schema.model_validate(data)`.

**E2E — User Flows**: Full browser stack via Playwright. `NARRARE_E2E_TEST=1` overrides all LLM factories to `TestModel()`.

## Cross-Layer Contract Tests

Three contract test types catch bugs that per-layer tests miss:

| Test | Rule | File Pattern | What It Catches |
|------|------|-------------|-----------------|
| i18n namespace registry | RULE-16 | `packages/web/__tests__/i18n-namespace-registry.test.ts` | Missing namespace in `request.ts` |
| API response contracts | RULE-17 | `tests/unit/api/test_*_contract.py` | Frontend/backend field name drift |
| Router configuration | RULE-18 | `tests/unit/api/test_*_router_contract.py` | Hardcoded provider/model strings |

## Architecture Constraint Test

Runs `scripts/check_architecture.py` as a pytest test — catches RULE violations in CI.

## Fake Conformance Tests

Every Fake class is verified against its `@runtime_checkable` Protocol via `isinstance()` checks. Location: `tests/unit/test_fake_conformance.py`. When adding a new Fake, add a conformance test.

## Coverage Minimums

| Module | Level | Min |
|--------|-------|-----|
| `core/llm/`, `core/prompts/` | Unit | 95% |
| All other `core/` | Unit | 90% |
| `apps/api/*/service.py` | Unit | 85% |
| `apps/api/*/repository.py` | Integration | 80% |
| `apps/api/*/router*.py` | Integration | 80% |
| i18n namespace registry | Integration | 100% |

Coverage below minimum = CI failure. No exceptions.

## Running Tests

```bash
just test          # Parallel (xdist -n auto, randomly enabled)
just test-unit     # Parallel unit tests only
just test-single   # Single-threaded for debugging (disables randomly)
```

Auto-tagging: `tests/unit/` → `@unit`, `tests/integration/` → `@integration @requires_db`, `tests/e2e/` → `@e2e`. No manual markers needed.

**Reference**: `docs/development/testing-standards.md` (1224 lines)
**Related**: narrare-dev/examples/testing-patterns · narrare-dev/examples/python-patterns · narrare-dev/lookup/directory-structure
