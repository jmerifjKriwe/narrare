---
paths:
  - "tests/unit/**/*.py"
---

# Unit Test Rules

## Every public method gets tested
- Happy path: correct input, expected output
- Domain error: invalid input, correct error raised
- Edge case: at least one boundary condition

## Use MockLLMGateway
```python
@pytest.fixture
def mock_gateway() -> MockLLMGateway:
    return MockLLMGateway()

mock_gateway.returns("Generated text...")
mock_gateway.raises(LLMGatewayError("timeout"))
mock_gateway.assert_called_with_intent(LLMIntent.WRITE)
```

## Naming
```
test_<what>_<condition>_<expected_result>

test_write_chapter_with_valid_request_returns_draft
test_write_chapter_when_llm_fails_raises_writing_error
```

Full documentation: docs/development/testing-standards.md
