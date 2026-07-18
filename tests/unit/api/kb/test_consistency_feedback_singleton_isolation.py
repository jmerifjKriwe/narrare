"""Regression guard: consistency-feedback singleton must not create real mem0 clients.

Bug history (CR-AUFG-03-10): the new ``get_consistency_feedback_memory_instance()``
singleton in :mod:`narrare.kb._feedback_memory_deps` follows the same module-level
caching pattern as ``_get_preference_service_instance()``. Because mem0 IS installed
in the test environment and ``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` /
``ANTHROPIC_API_KEY``, calling the singleton would reach
``create_memory_client_sync()`` and create a real ``mem0.AsyncMemory`` instance
backed by local Qdrant. Those clients were never closed, leaking:

- ``~/.mem0/migrations_qdrant/.lock``  (file handle)
- ``/tmp/qdrant/.lock``                (file handle)
- sqlite connections                   (mem0 history store)
- ``QdrantClient.__del__`` tracebacks at interpreter shutdown
- ``RuntimeError: Task got Future attached to a different loop`` at test teardown
  when the cached client's async resources survive across pytest-asyncio event loops

Root cause: ``is_mem0_available()`` returned ``True`` in tests and the singleton's
in-function import made the existing ``_no_real_mem0_clients`` test guard
(inapplicable — the guard patches the module-level re-imported reference).

Fix: (1) ``_feedback_memory_deps.py`` imports ``is_mem0_available`` /
``detect_provider_from_env`` at MODULE LEVEL so the test guard can patch the
re-imported reference (matches ``dependencies_prompts.py``); (2) the autouse
``_no_real_mem0_clients`` fixture in ``tests/conftest.py`` extends the patch to
cover ``narrare.kb._feedback_memory_deps.is_mem0_available`` too.

These tests verify both layers of the fix:
- ``test_singleton_does_not_call_create_memory_client_sync`` — the test guard
  short-circuits the singleton before it reaches ``create_memory_client_sync``.
- ``test_module_level_imports_present`` — guards against a future refactor
  moving the imports back inside the function (which would silently break the
  test guard pattern again).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_consistency_feedback_singleton() -> Any:  # pyright: ignore[reportUnusedFunction]
    """Reset the module-level singleton + init flag before each test.

    Ensures each test observes a fresh init path (not a cached result from
    an earlier test in the same process).
    """
    from narrare.kb import _feedback_memory_deps as fb_mod

    fb_mod._consistency_feedback_instance = None
    fb_mod._consistency_feedback_init_tried = False
    yield
    # Restore to the pre-init state after the test as well so this fixture
    # never leaks a real client into subsequent tests if the spy patch fails.
    fb_mod._consistency_feedback_instance = None
    fb_mod._consistency_feedback_init_tried = False


class TestNoRealMem0InConsistencyFeedbackSingleton:
    """Regression guard: the consistency-feedback singleton must not create real mem0 clients.

    Mirrors ``TestNoRealMem0InUnitTests`` in
    ``tests/unit/api/_app/test_dependencies_prompts.py`` — the same RULE-20
    isolation discipline applied to the new singleton.
    """

    def test_singleton_does_not_call_create_memory_client_sync(self) -> None:
        """``get_consistency_feedback_memory_instance()`` must not create a real client.

        Spies on ``create_memory_client_sync`` — if the singleton's mem0
        availability check is not properly mocked by the autouse
        ``_no_real_mem0_clients`` fixture, this spy fires and the assertion
        fails.
        """
        from narrare.kb._feedback_memory_deps import (
            get_consistency_feedback_memory_instance,
        )

        with patch("narrare_core.memory.mem0_client.create_memory_client_sync") as spy_create:
            result = get_consistency_feedback_memory_instance()

        # The singleton must return None (graceful degradation) and never
        # reach create_memory_client_sync.
        assert result is None, (
            "Singleton returned a non-None instance even though "
            "is_mem0_available() should be mocked to False in tests. "
            "A real mem0/Qdrant client would be created. "
            "Unit tests must never create real external resources (RULE-20)."
        )
        assert not spy_create.called, (
            "get_consistency_feedback_memory_instance() triggered "
            "create_memory_client_sync() — a real mem0/Qdrant client would "
            "be created. Ensure the autouse _no_real_mem0_clients fixture "
            "in tests/conftest.py patches "
            "narrare.kb._feedback_memory_deps.is_mem0_available to False."
        )

    def test_module_level_imports_present(self) -> None:
        """Guard against regression: imports MUST stay at module level.

        If a future refactor moves ``is_mem0_available`` /
        ``detect_provider_from_env`` back inside the function, the
        ``_no_real_mem0_clients`` test guard (which patches the
        module-level re-imported reference) would silently stop working,
        reintroducing the leak.

        This test pins the architectural decision by asserting the names
        are module-level attributes of ``_feedback_memory_deps``.
        """
        import narrare.kb._feedback_memory_deps as fb_mod

        # The autouse _no_real_mem0_clients fixture patches these
        # module-level bindings — if they're missing, the patch target
        # would silently point at a different module's binding.
        assert hasattr(fb_mod, "is_mem0_available"), (
            "is_mem0_available must be imported at module level in "
            "_feedback_memory_deps.py so the _no_real_mem0_clients "
            "test guard can patch this module's reference. Moving it "
            "inside the function silently breaks the test guard."
        )
        assert hasattr(fb_mod, "detect_provider_from_env"), (
            "detect_provider_from_env must be imported at module level in "
            "_feedback_memory_deps.py (same rationale as is_mem0_available)."
        )
