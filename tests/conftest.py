"""
Root test configuration and shared fixtures.
"""

from __future__ import annotations

import inspect
import os
import sys
from typing import TYPE_CHECKING

import pytest

from tests._schema_guard import scan_for_schema_mutation

# Class-root structlog isolation (autouse, every test): re-exported here so
# pytest registers the fixture for the whole tests/ tree — unit, integration
# and e2e alike. Import-based registration (instead of pytest_plugins, which
# pytest >= 8 forbids in non-top-level conftests) mirrors the
# tests/integration/_fixtures/network_guards.py precedent.
from tests._structlog_isolation import (  # noqa: F401 — re-exported for pytest fixture registration
    _isolate_structlog_config,
)

if TYPE_CHECKING:
    from types import ModuleType

# NOTE: Python path resolution (apps/api, packages/core) is handled by the
# `pythonpath` setting in [tool.pytest.ini_options] in pyproject.toml.

# Force test environment BEFORE any narrare import. ``setdefault`` is too
# weak — a developer shell that exported/sourced ``ENVIRONMENT=development``
# (the justfile no longer auto-loads ``.env`` via dotenv-load) would leak it
# into the pytest subprocess. With
# ``environment != "test"``, ``Settings.is_test`` returns False and the
# app lifespan (``apps/api/narrare/_app/lifespan.py``) runs production
# code paths that do not compose with per-test ``TestClient`` portal
# event loops: ``_run_stale_cleanup`` (asyncpg pool — ``lifespan.py:140``),
# and ``dispose_database()``. These bind asyncpg resources to whatever
# loop is current at lifespan startup; when the ``TestClient`` portal
# closes and a later WS test starts a fresh portal, asyncpg
# ``do_terminate`` raises
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
    """Auto-tag tests based on directory path + enforce schema_mutating guard.

    - tests/unit/ → unit
    - tests/integration/ → integration + requires_db
    - tests/e2e/ → e2e

    Schema-mutation guard: any integration test whose module source contains
    schema-mutating patterns (alembic downgrade, create_all/drop_all, SQL DDL)
    MUST carry ``@pytest.mark.schema_mutating``. Unmarked mutants fail
    collection loudly so the two-phase serial mitigation cannot silently lapse.
    Unit tests are exempt (they mock all DB access per testing standards).
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

    _enforce_schema_mutating_guard(items)


# Module-level cache: module file path → matched patterns (or [] if clean).
# Avoids re-parsing the same module for every test item it contains.
_schema_scan_cache: dict[str, list[str]] = {}


def _enforce_schema_mutating_guard(items: list[pytest.Item]) -> None:
    """Fail collection if any schema-mutating integration test lacks the marker."""
    violations: list[str] = []
    for item in items:
        if "tests/integration/" not in item.nodeid:
            continue
        # Defensive: unit-test fakes (FakeItem in test_auto_tagging.py) lack
        # get_closest_marker; real pytest.Items always have it. Skip items we
        # can't introspect — they'll also fail the module lookup below.
        get_marker = getattr(item, "get_closest_marker", None)
        if get_marker is not None and get_marker("schema_mutating"):
            continue

        module: ModuleType | None = getattr(item, "module", None)
        if module is None:
            func = getattr(item, "function", None)
            if func is not None:
                module = inspect.getmodule(func)
        if module is None:
            continue

        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue

        if module_file not in _schema_scan_cache:
            try:
                source = inspect.getsource(module)
            except OSError, TypeError:
                source = ""
            _schema_scan_cache[module_file] = scan_for_schema_mutation(source)

        patterns = _schema_scan_cache[module_file]
        if patterns:
            violations.append(f"  {item.nodeid}  (patterns: {', '.join(sorted(set(patterns)))})")

    if violations:
        pytest.exit(
            "schema_mutating guard — unmarked schema-mutating integration "
            "tests found:\n\n"
            + "\n".join(violations)
            + "\n\nThese tests mutate the shared test-DB schema but lack "
            "@pytest.mark.schema_mutating. Add the marker (runs serially in "
            "test phase 2) or refactor to not mutate schema (RULE-14).\n"
            "See: docs/development/testing-standards.md (schema_mutating).",
            returncode=1,
        )


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
