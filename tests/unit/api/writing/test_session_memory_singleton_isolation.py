"""Regression guard: session-memory singleton must not create real mem0 clients.

Bug history (ADR-068 follow-up #1): the ``get_session_memory_instance()``
singleton in :mod:`narrare.writing._session_memory_deps` follows the same
module-level caching pattern as ``_get_preference_service_instance()`` and
``get_consistency_feedback_memory_instance()``. PR #126 fixed the
consistency-feedback singleton but the writing singleton had the **same
latent bug**: the ``is_mem0_available`` / ``detect_provider_from_env``
imports lived inside the function body, so the autouse
``_no_real_mem0_clients`` test guard (which patches the module-level
re-imported reference) could not short-circuit the singleton.

Because mem0 IS installed in the test environment and
``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``,
calling the singleton reached ``create_memory_client_sync()`` and created
a real ``mem0.AsyncMemory`` instance backed by local Qdrant. Those
clients were never closed, leaking:

- ``~/.mem0/migrations_qdrant/.lock``  (file handle)
- ``/tmp/qdrant/.lock``                (file handle)
- sqlite connections                   (mem0 history store)
- ``QdrantClient.__del__`` tracebacks at interpreter shutdown
- ``RuntimeError: Task got Future attached to a different loop`` at test teardown
  when the cached client's async resources survive across pytest-asyncio event loops

Root cause: the in-function import made the module-level reference absent,
so the ``_no_real_mem0_clients`` test guard's
``monkeypatch.setattr("narrare.writing._session_memory_deps.is_mem0_available", ...)``
patched a name that did not exist (or silently bound a new attribute the
function never read), leaving the singleton free to proceed past the
availability gate.

Fix (ADR-068 Decision 1 + Decision 3): (1) ``_session_memory_deps.py``
imports ``is_mem0_available`` / ``detect_provider_from_env`` at MODULE
LEVEL so the test guard can patch the re-imported reference (matches
``_feedback_memory_deps.py`` and ``dependencies_prompts.py``); (2) the
autouse ``_no_real_mem0_clients`` fixtures in ``tests/unit/conftest.py``
and ``tests/integration/conftest.py`` extend the patch to cover
``narrare.writing._session_memory_deps.is_mem0_available`` too.

Follow-up #2 (RULE-04): the singleton was extracted from
``deps_writing.py`` into its own ``_session_memory_deps.py`` module so
``deps_writing.py`` could stay under the 200-line size limit while keeping
the module-level availability imports. The patch target and reset
attributes moved with the singleton.

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
def _reset_session_memory_singleton() -> Any:  # pyright: ignore[reportUnusedFunction]
    """Reset the module-level singleton + init flag before each test.

    Ensures each test observes a fresh init path (not a cached result from
    an earlier test in the same process).
    """
    from narrare.writing import _session_memory_deps as sm_mod

    sm_mod._session_memory_instance = None
    sm_mod._session_memory_init_tried = False
    yield
    # Restore to the pre-init state after the test as well so this fixture
    # never leaks a real client into subsequent tests if the spy patch fails.
    sm_mod._session_memory_instance = None
    sm_mod._session_memory_init_tried = False


class TestNoRealMem0InSessionMemorySingleton:
    """Regression guard: the session-memory singleton must not create real mem0 clients.

    Mirrors ``TestNoRealMem0InConsistencyFeedbackSingleton`` in
    ``tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py`` —
    the same RULE-20 isolation discipline applied to the writing singleton.
    """

    def test_singleton_does_not_call_create_memory_client_sync(self) -> None:
        """``get_session_memory_instance()`` must not create a real client.

        Spies on ``create_memory_client_sync`` — if the singleton's mem0
        availability check is not properly mocked by the autouse
        ``_no_real_mem0_clients`` fixture, this spy fires and the assertion
        fails.
        """
        from narrare.writing._session_memory_deps import get_session_memory_instance

        with patch("narrare_core.memory.mem0_client.create_memory_client_sync") as spy_create:
            result = get_session_memory_instance()

        # The singleton must return None (graceful degradation) and never
        # reach create_memory_client_sync.
        assert result is None, (
            "Singleton returned a non-None instance even though "
            "is_mem0_available() should be mocked to False in tests. "
            "A real mem0/Qdrant client would be created. "
            "Unit tests must never create real external resources (RULE-20)."
        )
        assert not spy_create.called, (
            "get_session_memory_instance() triggered "
            "create_memory_client_sync() — a real mem0/Qdrant client would "
            "be created. Ensure the autouse _no_real_mem0_clients fixture "
            "in tests/conftest.py patches "
            "narrare.writing._session_memory_deps.is_mem0_available to False."
        )

    def test_module_level_imports_present(self) -> None:
        """Guard against regression: imports MUST stay at module level.

        If a future refactor moves ``is_mem0_available`` /
        ``detect_provider_from_env`` back inside the function, the
        ``_no_real_mem0_clients`` test guard (which patches the
        module-level re-imported reference) would silently stop working,
        reintroducing the leak.

        This test pins the architectural decision by asserting the names
        are module-level attributes of ``_session_memory_deps``.
        """
        import narrare.writing._session_memory_deps as sm_mod

        # The autouse _no_real_mem0_clients fixture patches these
        # module-level bindings — if they're missing, the patch target
        # would silently point at a different module's binding.
        assert hasattr(sm_mod, "is_mem0_available"), (
            "is_mem0_available must be imported at module level in "
            "_session_memory_deps.py so the _no_real_mem0_clients "
            "test guard can patch this module's reference. Moving it "
            "inside the function silently breaks the test guard."
        )
        assert hasattr(sm_mod, "detect_provider_from_env"), (
            "detect_provider_from_env must be imported at module level in "
            "_session_memory_deps.py (same rationale as is_mem0_available)."
        )
