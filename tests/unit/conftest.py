"""Unit-test isolation fixtures.

RULE-20: Unit tests must never create real external resources — no
file-system locks, no local Qdrant databases, no real mem0 clients.

The autouse fixture ``_no_real_mem0_clients`` below prevents the
preference-service DI path and the consistency-feedback singleton from
creating real ``mem0.AsyncMemory`` instances. Without this guard, any unit
test that calls ``get_composer()``, ``get_invocation_pipeline()``, or
``get_consistency_feedback_memory_instance()`` would reach
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

from typing import Any

import pytest


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

    Does NOT affect ``narrare_core.memory.availability.is_mem0_available``
    directly — ``tests/unit/core/memory/test_availability.py`` tests the
    original function and continues to work.

    Requires the singletons to import ``is_mem0_available`` at MODULE
    LEVEL (not inside the function body) so the re-imported reference
    exists as a patchable attribute. The regression test
    ``tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py``
    pins this architectural decision.
    """
    monkeypatch.setattr(
        "narrare._app.dependencies_prompts.is_mem0_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "narrare.kb._feedback_memory_deps.is_mem0_available",
        lambda: False,
    )
    yield
