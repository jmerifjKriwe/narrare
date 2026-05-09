---
paths:
  - "tests/integration/**/*.py"
---

# Integration Test Rules

## Every HTTP endpoint gets tested
- Success: 200/201 with correct response schema
- Unauthorized: 401 when auth missing
- Not found: 404 for missing resources
- Validation error: 422 for invalid input

## Real services
- Real PostgreSQL (test database)
- Real Redis
- Mocked LLM (use MockLLMGateway)

Full documentation: docs/development/testing-standards.md
