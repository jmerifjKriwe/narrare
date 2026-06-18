"""Unit-test isolation fixtures.

RULE-20: Unit tests must never create real external resources — no
file-system locks, no local Qdrant databases, no real mem0 clients.

The autouse fixture ``_no_real_mem0_clients`` below prevents the
preference-service DI path from creating real ``mem0.AsyncMemory``
instances. Without this guard, any unit test that calls
``get_composer()`` or ``get_invocation_pipeline()`` would reach
``create_memory_client_sync()`` (because mem0 IS installed in the test
environment and ``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` /
``ANTHROPIC_API_KEY``), creating a real ``AsyncMemory`` backed by local
Qdrant. Those clients were never closed, leaking:

- ``~/.mem0/migrations_qdrant/.lock``  (unclosed file handle)
- ``/tmp/qdrant/.lock``                (unclosed file handle)
- sqlite connections                   (mem0 history store)
- ``QdrantClient.__del__`` tracebacks at interpreter shutdown

This fixture mocks ``is_mem0_available()`` to ``False`` so that
``_get_preference_service_instance()`` short-circuits before reaching
``create_memory_client_sync()``.

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

    Targets the re-imported ``is_mem0_available`` reference in
    ``narrare._app.dependencies_prompts`` — the module that gates the
    preference-service DI singleton. This covers all callers:
    ``get_composer()``, ``get_invocation_pipeline()``, and any future
    DI provider that delegates to ``_get_preference_service_instance()``.

    Does NOT affect ``narrare_core.memory.availability.is_mem0_available``
    directly — ``tests/unit/core/memory/test_availability.py`` tests the
    original function and continues to work.
    """
    monkeypatch.setattr(
        "narrare._app.dependencies_prompts.is_mem0_available",
        lambda: False,
    )
    yield
