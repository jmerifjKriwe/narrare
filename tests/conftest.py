"""
Root test configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Add apps/api to Python path so tests can import `narrare.*`
_api_path = Path(__file__).parent.parent / "apps" / "api"
if str(_api_path) not in sys.path:
    sys.path.insert(0, str(_api_path))

# Add packages/core to Python path so tests can import `narrare_core.*`
_core_path = Path(__file__).parent.parent / "packages" / "core"
if str(_core_path) not in sys.path:
    sys.path.insert(0, str(_core_path))

# Ensure test environment is set before any imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
# NOTE: NARRARE_TEST_MODE is intentionally NOT set here. It was previously
# set globally, which leaked the CSRF bypass into unit tests that explicitly
# test OriginValidationMiddleware rejection behaviour. The env var is now set
# only by the session-scoped ``_set_test_mode`` fixture in
# ``tests/integration/conftest.py``, so it applies to integration tests only.

# Set dummy API keys for LLM providers to prevent import errors in unit tests.
# Unit tests mock the gateway's _make_agent method, so real API calls are never made.
# These are only needed because pydantic-ai validates API keys at import time.
os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-anthropic-key"
os.environ["OPENAI_API_KEY"] = "sk-test-dummy-openai-key"

# Block ALL real LLM API calls in tests.
# If a test accidentally creates a real pydantic-ai Agent and calls .run(),
# this raises a clear RuntimeError instead of silently hitting the network.
# narrare: allow reason="global test guard — blocks real LLM API calls"
from pydantic_ai import (  # noqa: E402
    models,
)

models.ALLOW_MODEL_REQUESTS = False


# ---------------------------------------------------------------------------
# Pytest hooks: marker registration and auto-tagging
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for --strict-markers compatibility."""
    config.addinivalue_line("markers", "unit: unit tests (fast, no I/O, mocked dependencies)")
    config.addinivalue_line("markers", "integration: integration tests (real DB, mocked LLM)")
    config.addinivalue_line("markers", "requires_db: marks tests requiring database connection")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-tag tests based on directory path.

    - tests/unit/ → unit
    - tests/integration/ → integration + requires_db
    - tests/e2e/ → e2e
    """
    for item in items:
        nodeid = item.nodeid
        if "tests/unit/" in nodeid:
            item.add_marker(pytest.mark.unit)
        elif "tests/integration/" in nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.requires_db)
        elif "tests/e2e/" in nodeid:
            item.add_marker(pytest.mark.e2e)


# ---------------------------------------------------------------------------
# Architecture constraint test
# ---------------------------------------------------------------------------


def test_architecture_constraints() -> None:
    """
    RULE-01, RULE-02, RULE-04, RULE-11:
    Verify all architecture constraints pass.
    This test ensures the CI and local pre-commit hooks are consistent.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/check_architecture.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Architecture violations found:\n{result.stdout}\n{result.stderr}"
    )
