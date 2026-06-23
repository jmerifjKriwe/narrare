"""Tests for WebSocket app-state dependency accessors (ADR-052)."""

from __future__ import annotations

from types import SimpleNamespace

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore


class _App:
    """Tiny FastAPI-like app double exposing only ``state``."""

    def __init__(self) -> None:
        self.state = SimpleNamespace()


def test_deps_ws_return_app_state_singletons() -> None:
    """Accessors return exactly the shared objects bound on app.state."""
    from narrare.writing.deps_ws import (
        get_active_turn_registry,
        get_session_cache,
        get_session_manager,
        get_turn_state,
    )

    app = _App()
    app.state.session_cache = InMemorySessionCache()
    app.state.session_manager = SessionManager(cache=app.state.session_cache)
    app.state.active_turn_registry = ActiveTurnRegistry()
    app.state.turn_state = SessionTurnStateStore()

    assert get_session_cache(app) is app.state.session_cache
    assert get_session_manager(app) is app.state.session_manager
    assert get_active_turn_registry(app) is app.state.active_turn_registry
    assert get_turn_state(app) is app.state.turn_state


def test_get_session_control_service_reuses_bound_singleton() -> None:
    """The control-service accessor reuses the app.state singleton."""
    from narrare.writing.deps_ws import get_session_control_service

    app = _App()
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    turn_state = SessionTurnStateStore()
    registry = ActiveTurnRegistry()
    service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=registry,
    )
    app.state.writing_session_control_service = service

    assert get_session_control_service(app) is service
