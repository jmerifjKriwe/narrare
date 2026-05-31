<!-- Context: narrare-dev/processes/quality-gates | Priority: high | Source: docs/development/testing-standards.md | Updated: 2026-05-31 -->

# Quality Gates

What must pass before code is considered "done." Every gate must pass for a feature to reach `status: stable`.

---

## Gate 1: Test Level Gates

| Level | Location | Scope | Time Target | Requirement |
|-------|----------|-------|-------------|-------------|
| **Unit** | `tests/unit/` | Fast, pure, no I/O | < 5s total | Every public service method: 3+ tests (happy path, domain error, edge case) |
| **Integration** | `tests/integration/` | Real DB + Redis, mocked LLM | < 60s total | Every repository method + router endpoint (200/201 schema validation, 401, 404, 422) |
| **E2E** | `tests/e2e/` | Full stack, Playwright | < 5min total | Critical user flows. Main branch CI only |

**Never** use a real DB in unit tests. **Never** mock the DB in integration tests.

---

## Gate 2: Coverage Minimums

| Module | Level | Min | Target |
|--------|-------|-----|--------|
| `core/llm/`, `core/prompts/` | Unit | 95% | 100% |
| All other `core/` | Unit | 90% | 95% |
| `apps/api/*/service.py` | Unit | 85% | 90% |
| `apps/api/*/repository.py` | Integration | 80% | 90% |
| `apps/api/*/router*.py` | Integration | 80% | 85% |
| i18n namespace registry | Integration | 100% | 100% |

Coverage below minimum = CI failure. No exceptions.

---

## Gate 3: Architecture Constraint Gate

- Runs `scripts/check_architecture.py` as a pytest test
- Enforces: RULE-01b, 02, 04, 06, 09, 11, 15, 19
- Fails on: wrong import locations, file size violations, bare except, wrong `middleware.ts`

---

## Gate 4: Fake Conformance Gate

- Location: `tests/unit/test_fake_conformance.py`
- Every Fake class verified via `isinstance()` against its `@runtime_checkable` Protocol
- When adding a new Fake, add a conformance test

---

## Gate 5: Cross-Layer Contract Gates

| Test | Rule | File Pattern | What It Catches |
|------|------|-------------|-----------------|
| i18n namespace registry | RULE-16 | `packages/web/__tests__/i18n-namespace-registry.test.ts` | Missing namespace in `request.ts` |
| API response contracts | RULE-17 | `tests/unit/api/test_*_contract.py` | Frontend/backend field name drift |
| Router configuration | RULE-18 | `tests/unit/api/test_*_router_contract.py` | Hardcoded provider/model strings |

---

## Gate 6: Type Checking

- `mypy --strict` + `pyright` in CI (RULE-09)
- No untyped public functions
- `Any` forbidden except in approved adapters

---

## Gate 7: CI Summary

The full CI pipeline runs these gates in order:

1. `ruff` format + lint
2. `check_architecture.py` (constraint enforcement)
3. `mypy --strict` + `pyright` (type checking)
4. `pytest -m unit` (unit tests + coverage)
5. `pytest -m integration` (integration tests + coverage)
6. `pnpm test` (frontend tests)
7. `bandit` (security scan)

All gates must pass. No skipping, no `--no-cov` workarounds.

---

## Running Locally

```bash
just check          # Architecture + lint + type check
just test           # Parallel unit + integration (xdist)
just test-unit      # Unit tests only
just test-single    # Single-threaded for debugging
pnpm test           # Frontend tests
```

**Reference**: `docs/development/testing-standards.md` (1224 lines)
**Related**: narrare-dev/guides/testing · narrare-dev/examples/testing-patterns · narrare-dev/constraints/rules
