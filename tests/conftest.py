"""
Root test configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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

# Set dummy API keys for LLM providers to prevent import errors in unit tests.
# Unit tests mock the gateway's _make_agent method, so real API calls are never made.
# These are only needed because pydantic-ai validates API keys at import time.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-dummy-anthropic-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-openai-key")


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
