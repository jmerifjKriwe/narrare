"""
Narrare test suite.

Structure:
  tests/unit/        — Fast, no I/O, no DB, no LLM. Mock everything external.
  tests/integration/ — Real DB, mocked LLM.
  tests/e2e/         — Full stack (post-MVP).

Run: just test
"""
