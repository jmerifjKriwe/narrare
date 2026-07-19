"""
Root test configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys

import pytest

# NOTE: Python path resolution (apps/api, packages/core) is handled by the
# `pythonpath` setting in [tool.pytest.ini_options] in pyproject.toml.

# Force test environment BEFORE any narrare import. ``setdefault`` is too
# weak — ``justfile`` sets ``set dotenv-load := true``, so ``just
# test-integration`` exports every ``.env`` key (including
# ``ENVIRONMENT=development``) into the pytest subprocess; a developer
# shell with ``export ENVIRONMENT=development`` does the same. With
# ``environment != "test"``, ``Settings.is_test`` returns False and the
# app lifespan (``apps/api/narrare/_app/lifespan.py``) runs production
# code paths that do not compose with per-test ``TestClient`` portal
# event loops: ``broker.startup()/shutdown()`` (redis.asyncio),
# ``init_event_bus`` / ``shutdown_event_bus`` (redis.asyncio),
# ``_run_stale_cleanup`` (asyncpg pool — ``lifespan.py:140``), and
# ``dispose_database()``. These bind redis/asyncpg resources to whatever
# loop is current at lifespan startup; when the ``TestClient`` portal
# closes and a later WS test starts a fresh portal,
# ``broker.shutdown()`` and asyncpg ``do_terminate`` raise
# ``RuntimeError: Task got Future attached to a different loop`` at
# teardown — flakily, because pytest-randomly reorders the polluter.
# Direct assignment (not ``setdefault``) is required: this conftest is
# imported before ``narrare._app.database``, whose module-level
# ``_engine = _create_engine()`` (``database.py:56``) freezes
# ``get_settings()``'s ``@lru_cache`` on the first call. Once frozen,
# later env mutations have no effect.
os.environ["ENVIRONMENT"] = "test"
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
# More precisely, the keys are needed because pydantic-ai fetches provider
# credentials at provider *construction* time (not strict import) — and
# construction is widespread (every agent test, FakeModelRegistry, TestModel).
# Runtime calls are blocked separately via ALLOW_MODEL_REQUESTS = False below.
# This creates the API-key/mem0 tension documented in ADR-068 (mem0 test-
# isolation guard pattern); the _no_real_mem0_clients fixture in
# tests/unit/conftest.py and tests/integration/conftest.py is the accepted
# resolution.
os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-anthropic-key"
os.environ["OPENAI_API_KEY"] = "sk-test-dummy-openai-key"

# Block ALL real LLM API calls in tests.
# If a test accidentally creates a real pydantic-ai Agent and calls .run(),
# this raises a clear RuntimeError instead of silently hitting the network.
# narrare: allow reason="global test guard — blocks real LLM API calls"
from pydantic_ai import (
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
    config.addinivalue_line(
        "markers",
        "mutation_inert: static repo-structure test; cannot kill mutants, "
        "excluded from mutation runs",
    )

    # MutMut↔Hypothesis fix: MutMut's stats phase injects a StatsCollector
    # pytest plugin that the clean-tests/per-mutant phases do not, changing the
    # test "executor" fingerprint Hypothesis records → FailedHealthCheck:
    # differing_executors. Gated on MUTMUT_RUN (set by scripts/run_mutmut.py) so
    # normal CI keeps the health check sharp. Import is guarded so non-mutmut
    # runs pay zero cost and hypothesis stays unimported here.
    if os.environ.get("MUTMUT_RUN"):
        from hypothesis import HealthCheck, settings

        settings.register_profile(
            "mutmut",
            suppress_health_check=[HealthCheck.differing_executors],
        )
        settings.load_profile("mutmut")


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
    RULE-01b, RULE-02, RULE-04, RULE-11:
    Verify all architecture constraints pass.
    This test ensures the CI and local pre-commit hooks are consistent.
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/check_architecture.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Architecture violations found:\n{result.stdout}\n{result.stderr}"
    )
