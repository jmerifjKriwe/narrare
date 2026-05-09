---
name: narrare-testing
description: Handle test strategy, write tests, and enforce coverage standards. Use when user asks about "tests", "testing", "coverage", "test quality", or specifies test-related work.
---

## Narrare Testing

Owns test quality, test architecture, and coverage standards. Every untested behavior is a bug waiting to happen.

### Purpose

Ensure all code is properly tested at the appropriate level (unit/integration/e2e) with good test quality and sufficient coverage.

### Steps

1. **Determine Test Level** — Three levels, always separate:
   - **Unit** (`tests/unit/`): Fast, pure, no I/O. Mock everything. < 5s total
   - **Integration** (`tests/integration/`): Real DB/Redis, mocked LLM. < 60s total
   - **E2E** (`tests/e2e/`): Full stack with real services. < 5min total

2. **Unit Tests** — Every public method:
   - Happy path: correct input, expected output
   - Domain error: invalid input, correct error raised
   - Edge case: at least one boundary condition

3. **Integration Tests** — Every HTTP endpoint:
   - Success: 200/201 with correct response schema
   - Unauthorized: 401 when auth missing
   - Not found: 404 for missing resources
   - Validation error: 422 for invalid input

4. **Use MockLLMGateway** — Always for unit tests:
   ```python
   @pytest.fixture
   def mock_gateway() -> MockLLMGateway:
       return MockLLMGateway()

   class MockLLMGateway:
       def returns(self, text: str) -> None: ...
       def raises(self, error: Exception) -> None: ...
       def assert_called_with_intent(self, intent: LLMIntent) -> None: ...
   ```

5. **Check Coverage** — Minimum thresholds:
   | Module | Minimum | Target |
   |--------|---------|--------|
   | `core/llm/` | 95% | 100% |
   | `core/prompts/` | 95% | 100% |
   | All other `core/` | 90% | 95% |
   | `apps/api/*/service.py` | 85% | 90% |
   | `apps/api/*/repository.py` | 80% | 90% |

### References

- `docs/development/testing-standards.md` — Full test strategy
- `docs/_shared/CONSTRAINTS.md` — RULE-10 (Tests are not optional)
- `tests/conftest.py` — Test fixtures

### Naming Convention

```
test_<what>_<condition>_<expected_result>

test_write_chapter_with_valid_request_returns_draft
test_write_chapter_when_llm_fails_raises_writing_error
test_gateway_run_with_intent_write_selects_correct_model
```

### What You Don't Do

- Write production code (Implementation Agent)
- Define what a feature should do (Architecture Agent)
- Configure test infrastructure like Docker (Deployment Agent)

### Token Efficiency Rules

- Start with `get_minimal_context(task="test ...")`
- Focus on the specific module being tested
- Read only relevant test fixtures
