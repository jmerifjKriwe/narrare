"""Tests for writing-session singleton binding in application lifespan."""

from __future__ import annotations

from types import SimpleNamespace

from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore


class _App:
    """Tiny FastAPI-like app double exposing only ``state``."""

    def __init__(self) -> None:
        self.state = SimpleNamespace()


def test_bind_writing_session_singletons_sets_shared_app_state() -> None:
    """Startup binds one shared session stack on app.state."""
    from narrare._app.lifespan import bind_writing_session_singletons

    app = _App()

    bind_writing_session_singletons(app)  # type: ignore[arg-type]

    assert isinstance(app.state.session_manager, SessionManager)
    assert isinstance(app.state.turn_state, SessionTurnStateStore)
    assert isinstance(app.state.active_turn_registry, ActiveTurnRegistry)
    assert isinstance(
        app.state.writing_session_control_service,
        WritingSessionControlService,
    )
