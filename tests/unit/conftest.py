"""Unit-test isolation fixtures.

RULE-20: Unit tests must never create real external resources — no
file-system locks, no local Qdrant databases, no real mem0 clients.

The autouse fixture ``_no_real_mem0_clients`` below prevents the
preference-service DI path, the consistency-feedback singleton, and the
session-memory singleton from creating real ``mem0.AsyncMemory``
instances. Without this guard, any unit test that calls
``get_composer()``, ``get_invocation_pipeline()``,
``get_consistency_feedback_memory_instance()``, or
``get_session_memory_instance()`` would reach
``create_memory_client_sync()`` (because mem0 IS installed in the test
environment and ``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` /
``ANTHROPIC_API_KEY``), creating a real ``AsyncMemory`` backed by local
Qdrant. Those clients were never closed, leaking:

- ``~/.mem0/migrations_qdrant/.lock``  (unclosed file handle)
- ``/tmp/qdrant/.lock``                (unclosed file handle)
- sqlite connections                   (mem0 history store)
- ``QdrantClient.__del__`` tracebacks at interpreter shutdown
- ``RuntimeError: Task got Future attached to a different loop`` at test
  teardown when the cached client's async resources survive across
  pytest-asyncio event loops (the proximate cause of the regression fixed
  alongside this comment's extension to ``_feedback_memory_deps``)

This fixture mocks ``is_mem0_available()`` to ``False`` at each singleton
module's re-imported reference so the singletons short-circuit before
reaching ``create_memory_client_sync()``.

Tests that specifically verify the mem0-available path (e.g.
``TestPreferenceServiceNullClient``, ``TestPreferenceServiceSuccess``)
override ``is_mem0_available`` via their own ``monkeypatch.setattr``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pyrate_limiter import Limiter


@pytest.fixture(autouse=True)
def _no_real_mem0_clients(  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection, not direct call. Pyright false-positive.
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Prevent real mem0/QdrantClient creation in unit tests (RULE-20).

    Targets the re-imported ``is_mem0_available`` reference in each
    singleton module that gates mem0 client creation. This covers:

    - ``narrare._app.dependencies_prompts`` — preference-service DI
      singleton (covers all callers via ``get_composer()`` /
      ``get_invocation_pipeline()``).
    - ``narrare.kb._feedback_memory_deps`` — consistency-feedback DI
      singleton (covers ``get_dismissed_service`` /
      ``get_consistency_service`` callers).
    - ``narrare.writing._session_memory_deps`` — session-memory singleton
      (covers ``get_writing_service`` / coauthor/extend/rewrite callers).
      Lives in its own module per RULE-04 (extracted from
      ``deps_writing.py``); the singleton state and module-level
      availability imports move together.

    Does NOT affect ``narrare_core.memory.availability.is_mem0_available``
    directly — ``tests/unit/core/memory/test_availability.py`` tests the
    original function and continues to work.

    Requires the singletons to import ``is_mem0_available`` at MODULE
    LEVEL (not inside the function body) so the re-imported reference
    exists as a patchable attribute. The regression tests
    ``tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py``
    and
    ``tests/unit/api/writing/test_session_memory_singleton_isolation.py``
    pin this architectural decision.
    """
    monkeypatch.setattr(
        "narrare._app.dependencies_prompts.is_mem0_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "narrare.kb._feedback_memory_deps.is_mem0_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "narrare.writing._session_memory_deps.is_mem0_available",
        lambda: False,
    )
    yield


@pytest.fixture(autouse=True)
def _block_models_dev_network(  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection, not direct call. Pyright false-positive.
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Prevent real models.dev HTTP fetches in unit tests (RULE-20).

    ``narrare_core.llm.cost_rates._fetch_models`` performs a *real synchronous*
    ``httpx.Client.get("https://models.dev/api.json")`` whenever the on-disk
    metadata cache at ``~/.narrare/cache/models_cache.json`` is missing or stale.
    Several unit tests reach this path transitively without mocking it:

    - ``ModelRegistry.run()`` → ``result.cost_estimate_usd`` → ``get_rates``
      (e.g. ``tests/unit/core/llm/test_gateway.py``).
    - the WebSocket draft path → ``run_limits.resolve`` → ``get_model_limits``
      (e.g. ``tests/unit/api/writing/test_ws_draft_regression.py``).

    Because the call is synchronous it blocks the asyncio event loop, and under
    full-suite load it intermittently exceeded the 10 s per-test pytest-timeout
    → flaky ``Timeout`` failures. Worse, ``tests/unit/core/llm/test_cost_rates.py``'s
    ``isolate_cache`` autouse fixture reassigns the module-level ``CACHE_FILE``
    to a per-test ``tmp_path`` *without restoring it*, so once that file has run
    the global ``CACHE_FILE`` points at a since-deleted temp dir, forcing every
    later test in the session straight into the real fetch.

    This guard patches ``_fetch_models`` to raise. The cost-rates layer catches
    ``Exception`` for graceful degradation (returns ``DEFAULT_RATES`` /
    ``ModelLimits | None``), so unaffected tests keep working deterministically
    *offline*; tests that intentionally exercise the fetch path
    (``test_cost_rates.py``, ``test_provider_service.py``) override the symbol
    with their own ``unittest.mock.patch`` which takes precedence inside its
    ``with`` block. The blocked sentinel raises ``AssertionError`` so any
    accidental fetch attempt leaves a diagnostic ``models_fetch_failed`` warning
    in the log.

    Regression pin: ``tests/unit/core/llm/test_network_isolation_guard.py``.
    """

    def _blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "Unit test attempted a real network fetch from models.dev "
            "(narrare_core.llm.cost_rates._fetch_models). Unit tests must not "
            "perform network I/O (RULE-20). Mock _fetch_models explicitly if "
            "the fetch path must be exercised."
        )

    monkeypatch.setattr(
        "narrare_core.llm.cost_rates._fetch_models",
        _blocked,
    )
    yield


@pytest.fixture(autouse=True)
def _isolate_core_settings(  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection, not direct call. Pyright false-positive.
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Isolate CoreSettings from the project-root ``.env`` file in unit tests.

    ADR-071: ``CoreSettings`` reads the ``.env`` file in production. Unit tests
    control config via ``os.environ`` (``monkeypatch.setenv`` / ``delenv``)
    only — matching the pre-ADR-071 behaviour where Core read ``os.environ``
    directly. Disabling ``env_file`` here prevents ``.env`` values (e.g.
    ``NARRARE_E2E_TEST=1`` or a real ``NARRARE_ENCRYPTION_KEY``) from leaking
    into tests that ``delenv`` and expect the "unset" default.

    The cache is cleared before and after each test so every test sees a fresh
    ``CoreSettings`` construction reflecting the current ``os.environ``.
    """
    from narrare_core.settings import CoreSettings, get_core_settings

    monkeypatch.setitem(CoreSettings.model_config, "env_file", None)
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter_buckets() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection, not direct call. Pyright false-positive.
    """Flush every module-level rate-limiter bucket before each test.

    The API rate limiters are intentionally process-wide singletons
    (AR-05-02: ``Limiter`` must accumulate across requests, or limits
    would never trigger). In the unit-test process that same accumulation
    is a cross-test leak: CI assigns whole files to shared pytest-xdist
    workers (``pytest tests/unit/ -n auto --dist loadfile``), so any file
    that exercises a limiter-protected route consumes from the SAME
    in-memory bucket as every later file on that worker.
    ``AI_ANALYSIS_LIMITER`` allows 5 requests/minute, and e.g.
    ``tests/unit/api/kb/entity_resolution/test_router.py`` needs exactly
    5 — any upstream consumption (the series voice / voice-drift /
    consistency router tests alone fire 19) produces spurious ``429``
    responses whose presence depends on the pytest-randomly seed (CI:
    2 x ``assert 429 == 200``; same defect class as the known series
    voice-router flakiness).

    Flushing all singleton buckets per test restores file independence
    WITHOUT weakening enforcement tests: tests that verify rate limiting
    accumulate WITHIN a single test (auth 3→429 / 5→429 regression pins
    in ``tests/unit/api/auth/test_auth_rate_limits.py``) or construct
    local ``Limiter`` instances (``test_rate_limits.py``,
    ``test_rate_limiter_compat.py``). Regression pin:
    ``tests/unit/api/_app/test_rate_limiter_test_isolation.py``.
    """
    from narrare._app.rate_limits import (
        AI_ANALYSIS_LIMITER,
        AI_LIGHT_LIMITER,
        AI_PROMPT_LIVE_TEST_LIMITER,
        AI_WRITE_LIMITER,
        AI_WS_LIMITER,
        SETUP_MODELS_LIMITER,
    )
    from narrare.auth.router import _LOGIN_LIMITER, _REGISTER_LIMITER

    limiters: tuple[Limiter, ...] = (
        AI_WRITE_LIMITER.limiter,
        AI_ANALYSIS_LIMITER.limiter,
        AI_LIGHT_LIMITER.limiter,
        SETUP_MODELS_LIMITER.limiter,
        AI_PROMPT_LIVE_TEST_LIMITER.limiter,
        AI_WS_LIMITER,
        _REGISTER_LIMITER.limiter,
        _LOGIN_LIMITER.limiter,
    )
    for limiter in limiters:
        for bucket in limiter.buckets():
            bucket.flush()
    yield
