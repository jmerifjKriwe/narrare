"""Writing module dependency injection — WebSocket session factories.

Creates the :class:`WritingTurnService` with wired invocation pipeline,
run-limit resolver, and shared registries (ADR-045 Decision 6).

ADR-052 binds writing-session lifecycle singletons on ``app.state`` during
FastAPI lifespan startup. WebSocket routes pass ``websocket.app`` here so
all connections share the same session cache, manager, turn registry, and
control service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from narrare._app.dependencies import (
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)

if TYPE_CHECKING:
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.session_manager import SessionCacheProtocol, SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore


class _StatefulApp(Protocol):
    """Minimal app surface needed by WebSocket dependency accessors."""

    state: Any


def get_writing_turn_service(
    config: ResolvedModelConfig,
) -> WritingTurnService:
    """Create a WritingTurnService for a WebSocket session.

    Wires the shared invocation pipeline, model registry, and a fresh
    run-limit resolver for per-connection streaming turns.

    Args:
        config: The per-request resolved model configuration.

    Returns:
        Configured :class:`WritingTurnService`.
    """
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    return WritingTurnService(
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        registry=get_model_registry(),
        config=config,
        run_limit_resolver=DefaultRunLimitResolver(),
    )


def _state_value(app: _StatefulApp, name: str) -> object:
    """Return a required value from ``app.state`` or raise a clear error."""
    value = getattr(app.state, name, None)
    if value is None:
        raise RuntimeError(f"app.state.{name} is not bound; lifespan did not initialize")
    return value


def get_session_cache(app: _StatefulApp) -> SessionCacheProtocol:
    """Return the shared writing-session cache bound on ``app.state``."""
    # Cast is safe: lifespan binds a SessionCacheProtocol implementation.
    return cast("SessionCacheProtocol", _state_value(app, "session_cache"))


def get_session_manager(app: _StatefulApp) -> SessionManager:
    """Return the shared writing SessionManager bound on ``app.state``."""
    # Cast is safe: lifespan binds SessionManager at startup.
    return cast("SessionManager", _state_value(app, "session_manager"))


def get_active_turn_registry(app: _StatefulApp) -> ActiveTurnRegistry:
    """Return the shared ActiveTurnRegistry bound on ``app.state``."""
    # Cast is safe: lifespan binds ActiveTurnRegistry at startup.
    return cast("ActiveTurnRegistry", _state_value(app, "active_turn_registry"))


def get_turn_state(app: _StatefulApp) -> SessionTurnStateStore:
    """Return the shared SessionTurnStateStore bound on ``app.state``."""
    # Cast is safe: lifespan binds SessionTurnStateStore at startup.
    return cast("SessionTurnStateStore", _state_value(app, "turn_state"))


def get_session_control_service(
    app: _StatefulApp,
    *,
    session_manager: SessionManager | None = None,
    registry: ActiveTurnRegistry | None = None,
    turn_state: SessionTurnStateStore | None = None,
) -> WritingSessionControlService:
    """Return or build the writing-session control service.

    If explicit collaborators are provided, a fresh service is returned for
    tests/route-local wiring. Otherwise the app-state singleton is reused.
    """
    if session_manager is None and registry is None and turn_state is None:
        existing = getattr(app.state, "writing_session_control_service", None)
        if existing is not None:
            # Cast is safe: lifespan binds WritingSessionControlService.
            return cast("WritingSessionControlService", existing)

    from narrare.writing.ws_session_control_service import WritingSessionControlService

    return WritingSessionControlService(
        session_manager=session_manager or get_session_manager(app),
        turn_state=turn_state or get_turn_state(app),
        registry=registry or get_active_turn_registry(app),
    )
