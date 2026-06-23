"""Factory for wiring WebSocket writing-session transport components.

Keeps FastAPI routes and ``WritingSessionHandler`` free of turn-service and
streaming-adapter construction details while preserving constructor injection
for each focused component.

See: ADR-045, ADR-052, CONSTRAINTS.md RULE-04/RULE-06/RULE-12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore


def build_writing_session_handler(
    *,
    session_manager: SessionManager,
    registry: ActiveTurnRegistry,
    turn_state: SessionTurnStateStore,
    control_service: WritingSessionControlService,
    model_registry: ModelRegistry,
    composer: PromptComposer,
    config: ResolvedModelConfig,
    invocation_pipeline: InvocationPipeline | None,
    run_limit_resolver: DefaultRunLimitResolver,
    api_key: str | None = None,
    base_url: str | None = None,
    mode: str = "interactive_session",
    ws_idle_timeout: int = 1800,
) -> WritingSessionHandler:
    """Build a WebSocket writing session handler and focused collaborators.

    Args:
        session_manager: Session state manager for the connection.
        registry: Active-turn registry for cancellable streaming tasks.
        turn_state: In-process store for active-turn partial prose.
        control_service: Session control service for stop/reattach.
        model_registry: Model registry for turn and draft streaming.
        composer: Prompt composer used by invocation-contract services.
        config: Resolved model configuration.
        invocation_pipeline: Invocation pipeline for prepare/finalize.
        run_limit_resolver: Runtime output-budget resolver.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
        mode: Session mode for the handler.
        ws_idle_timeout: Idle timeout in seconds.

    Returns:
        A fully wired :class:`WritingSessionHandler`.
    """
    from narrare.writing.ws_direction_dispatch import WritingDirectionDispatcher
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare.writing.ws_message_router import WritingSessionMessageRouter
    from narrare.writing.ws_turn_service import WritingTurnService

    turn_service = WritingTurnService(
        composer=composer,
        invocation_pipeline=invocation_pipeline,
        registry=model_registry,
        config=config,
        run_limit_resolver=run_limit_resolver,
    )
    direction_dispatcher = WritingDirectionDispatcher(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=registry,
        turn_service=turn_service,
        api_key=api_key,
        base_url=base_url,
    )
    message_router = WritingSessionMessageRouter(
        session_manager=session_manager,
        direction_dispatcher=direction_dispatcher,
        control_service=control_service,
        registry=model_registry,
        composer=composer,
        config=config,
        invocation_pipeline=invocation_pipeline,
        run_limit_resolver=run_limit_resolver,
        api_key=api_key,
        base_url=base_url,
    )
    return WritingSessionHandler(
        session_manager=session_manager,
        control_service=control_service,
        message_router=message_router,
        mode=mode,
        ws_idle_timeout=ws_idle_timeout,
    )
