"""Regression test: no real mem0 clients constructed during the integration session.

Guards ADR-068 Decision 2 — the session-scoped ``_no_real_mem0_clients`` guard
(in ``tests/integration/conftest.py``) must prevent any mem0-backed singleton
from creating a real ``mem0.AsyncMemory`` client during the integration test
session. The session-scope (vs the previous function-scope) is necessary
because the integration suite has a session-scoped ``_prewarm_composer``
fixture that calls ``get_composer()`` → ``_get_preference_service_instance()``
once at session start, BEFORE any function-scoped guard could activate.

APPROACH — module-state inspection (NOT caplog):

The original handoff suggested a ``caplog``-based assertion that no
``*_initialized`` log events fire. That approach is unreliable here for
two reasons:

1. ``caplog`` is function-scoped — it captures records emitted DURING the
   test function's execution. The bug being caught fires events during
   SESSION SETUP (when ``_prewarm_composer`` runs), before any test
   function starts. By the time this test runs, ``caplog`` would have
   already missed the relevant window.
2. The ``*_initialized`` events are emitted via ``structlog.get_logger()``
   which only routes through stdlib ``logging`` (where ``caplog`` hooks)
   AFTER ``configure_logging()`` runs (via the FastAPI lifespan).
   ``_prewarm_composer`` runs at session start, before the ``app``
   fixture (which triggers lifespan) is built — so structlog defaults
   to its ``PrintLoggerFactory`` (stdout), bypassing ``caplog``
   entirely.

Inspecting the singleton modules' state directly is more robust: each
singleton caches its init result in module-level ``*_init_tried`` /
``*_instance`` slots, so the state IS the historical record of what
happened during session setup. If the session guard ran before
``_prewarm_composer``, each ``*_init_tried`` flag is ``True`` (the
singleton was invoked) but the corresponding ``*_instance`` slot is
``None`` (it short-circuited via the patched ``is_mem0_available()``).
If the guard ran AFTER, the ``*_instance`` slot holds a real client —
and the assertion fails.
"""

from __future__ import annotations


def test_no_mem0_singletons_hold_real_clients_during_session() -> None:
    """No mem0-backed singleton may hold a real client instance.

    Forces each singleton's init path explicitly (idempotent — these are
    no-ops if ``_prewarm_composer`` or any other session fixture already
    invoked them, because ``*_init_tried`` caches the first call's result).
    Then asserts each singleton short-circuited to ``None`` via the
    patched ``is_mem0_available()``.

    Failure of any assertion means the session-scoped
    ``_no_real_mem0_clients`` guard did NOT run before the singleton init
    path — i.e., the ADR-068 Decision 2 ordering invariant is broken
    (either the guard is function-scoped again, or the explicit
    ``_prewarm_composer(_no_real_mem0_clients: None)`` dependency was
    removed).
    """
    # Force each singleton's init path. With the session guard active,
    # is_mem0_available() returns False at each module's re-imported
    # reference → the singleton short-circuits → *_instance stays None.
    from narrare._app.dependencies_prompts import (
        _get_preference_service_instance,
    )
    from narrare.kb._feedback_memory_deps import (
        get_consistency_feedback_memory_instance,
    )
    from narrare.writing._session_memory_deps import (
        get_session_memory_instance,
    )

    preference_result = _get_preference_service_instance()
    consistency_result = get_consistency_feedback_memory_instance()
    session_result = get_session_memory_instance()

    # All three singletons must short-circuit to None (graceful
    # degradation path). A non-None result means a real mem0 client
    # was constructed during this call OR during an earlier session
    # fixture's call (cached in the singleton's module-level slot).
    assert preference_result is None, (
        "PreferenceService holds a real mem0 client — the session-scoped "
        "_no_real_mem0_clients guard did not patch "
        "narrare._app.dependencies_prompts.is_mem0_available before "
        "_prewarm_composer (or another session-scoped fixture) triggered "
        "singleton init. See ADR-068 Decision 2."
    )
    assert consistency_result is None, (
        "ConsistencyFeedbackService holds a real mem0 client — the "
        "session-scoped _no_real_mem0_clients guard did not patch "
        "narrare.kb._feedback_memory_deps.is_mem0_available before "
        "a session-scoped fixture triggered singleton init. "
        "See ADR-068 Decision 2."
    )
    assert session_result is None, (
        "SessionMemoryService holds a real mem0 client — the "
        "session-scoped _no_real_mem0_clients guard did not patch "
        "narrare.writing._session_memory_deps.is_mem0_available before "
        "a session-scoped fixture triggered singleton init. "
        "See ADR-068 Decision 2."
    )


def test_session_guard_ran_before_preference_singleton_init() -> None:
    """Pin the ADR-068 Decision 2 ordering invariant specifically.

    The original regression: ``_prewarm_composer`` (session-scoped, calls
    ``get_composer()`` → ``_get_preference_service_instance()``) ran
    BEFORE the function-scoped ``_no_real_mem0_clients`` guard. Inspect
    the cached singleton state — if ``_preference_service_init_tried`` is
    True (the singleton was invoked, e.g. by ``_prewarm_composer``), then
    ``_preference_service_instance`` MUST be None (the patched
    ``is_mem0_available()`` short-circuited the init path).

    This is a stronger check than the result-None assertion above: it
    catches the case where the singleton was already initialised by a
    session-scoped fixture BEFORE this test ran (and our explicit
    re-invocation returns the cached None).
    """
    import narrare._app.dependencies_prompts as prefs_mod

    # If the preference singleton was never invoked during this session,
    # there is nothing to verify for the ordering invariant (no fixture
    # triggered the path). Otherwise, the instance MUST be None.
    if prefs_mod._preference_service_init_tried:  # pyright: ignore[reportPrivateUsage]
        assert prefs_mod._preference_service_instance is None, (  # pyright: ignore[reportPrivateUsage]
            "PreferenceService was initialised during the integration "
            "session (init_tried=True) and holds a real mem0 client "
            "(instance is not None). The session-scoped "
            "_no_real_mem0_clients guard ran too late — ADR-068 "
            "Decision 2 ordering is broken."
        )
