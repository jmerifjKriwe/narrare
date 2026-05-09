"""
Root test configuration and shared fixtures.
"""

from __future__ import annotations

import os

# Ensure test environment is set before any imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")


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
