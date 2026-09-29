"""Tests for WebSocket app-state dependency accessors (ADR-052)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ModelRegistry
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.prompts import PromptComposer
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
        get_session_manager,
        get_turn_state,
    )

    app = _App()
    app.state.session_cache = InMemorySessionCache()
    app.state.session_manager = SessionManager(cache=app.state.session_cache)
    app.state.active_turn_registry = ActiveTurnRegistry()
    app.state.turn_state = SessionTurnStateStore()

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


# ---------------------------------------------------------------------------
# Coverage gap: get_writing_turn_service (lines 37-60)
# ---------------------------------------------------------------------------


def test_get_writing_turn_service_wires_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_writing_turn_service creates WritingTurnService with wired deps."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.writing.deps_ws import get_writing_turn_service
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.llm.model_routing import ResolvedModel

    config = ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4000,
    )
    composer = MagicMock(spec=PromptComposer)
    pipeline = MagicMock(spec=InvocationPipeline)
    registry = MagicMock(spec=ModelRegistry)

    monkeypatch.setattr("narrare.writing.deps_ws.get_composer", lambda: composer)
    monkeypatch.setattr("narrare.writing.deps_ws.get_invocation_pipeline", lambda: pipeline)
    monkeypatch.setattr("narrare.writing.deps_ws.get_model_registry", lambda: registry)

    service = get_writing_turn_service(StaticModelResolution(ResolvedModel(config=config)))

    assert isinstance(service, WritingTurnService)
    assert service._composer is composer
    assert service._invocation_pipeline is pipeline
    assert service._registry is registry
    assert service._runtime_factory is not None
    assert service._run_limit_resolver is not None


# ---------------------------------------------------------------------------
# Coverage gap: _state_value RuntimeError path (line 67)
# ---------------------------------------------------------------------------


def test_state_value_raises_runtime_error_when_state_missing() -> None:
    """_state_value raises RuntimeError when app.state lacks the attribute."""
    from narrare.writing.deps_ws import _state_value

    app = _App()

    with pytest.raises(RuntimeError, match=r"app\.state.*is not bound"):
        _state_value(app, "nonexistent_key")


# ---------------------------------------------------------------------------
# Coverage gap: get_session_control_service fresh-service path (lines 113-118)
# ---------------------------------------------------------------------------


def test_get_session_control_service_with_explicit_manager_returns_new_service() -> None:
    """Passing explicit session_manager creates a new service (not singleton)."""
    from narrare.writing.deps_ws import get_session_control_service

    app = _App()
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    app.state.turn_state = SessionTurnStateStore()
    app.state.active_turn_registry = ActiveTurnRegistry()

    # Bind a singleton so we can prove a different instance is returned
    bound_service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=app.state.turn_state,
        registry=app.state.active_turn_registry,
    )
    app.state.writing_session_control_service = bound_service

    fresh_service = get_session_control_service(app, session_manager=session_manager)

    assert fresh_service is not bound_service
    assert isinstance(fresh_service, WritingSessionControlService)
