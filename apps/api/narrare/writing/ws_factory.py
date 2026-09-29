"""Factory for wiring WebSocket writing-session transport components.

Keeps FastAPI routes and ``WritingSessionHandler`` free of turn-service and
streaming-adapter construction details while preserving constructor injection
for each focused component.

ADR-086 (L39): the factory wires LAZILY — it consumes a ``ModelResolution``
and builds the deferred runtime/config-provider compositions
(``_ws_turn_support``); no routing cascade or budget composition runs at
handler build. The frozen config and the ADR-082 budgets compose at the
first turn (``WritingTurnService.ensure_resolved``); the interview-draft
path resolves via the config provider at message time.

See: ADR-045, ADR-052, ADR-086, CONSTRAINTS.md RULE-04/RULE-06/RULE-12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
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
    model_resolution: ModelResolution,
    invocation_pipeline: InvocationPipeline | None,
    run_limit_resolver: DefaultRunLimitResolver,
    api_key: str | None = None,
    base_url: str | None = None,
    mode: str = "interactive_session",
    ws_idle_timeout: int = 1800,
    limits: TokenLimitOverrides | None = None,
) -> WritingSessionHandler:
    """Build a WebSocket writing session handler and focused collaborators.

    Args:
        session_manager: Session state manager for the connection.
        registry: Active-turn registry for cancellable streaming tasks.
        turn_state: In-process store for active-turn partial prose.
        control_service: Session control service for stop/reattach.
        model_registry: Model registry for turn and draft streaming.
        composer: Prompt composer used by invocation-contract services.
        model_resolution: Lazily-wired WRITE-intent resolution (ADR-086
            L39, ``resolve_ws_session_config`` output). Shared by the turn
            runtime and the interview-draft config provider — the routing
            cascade runs at most once per connection.
        invocation_pipeline: Invocation pipeline for prepare/finalize.
        run_limit_resolver: Runtime output-budget resolver.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
        mode: Session mode for the handler.
        ws_idle_timeout: Idle timeout in seconds.
        limits: Resolved handshake token limits (``resolve_ws_session_config``
            output). When given, the WS context assembler budgets with the
            SAME tier allocations as the HTTP writing paths (item E):
            ``limits.tier_percentages`` (FIND-012) plus the ADR-082
            model-capped ``writing_tier_base`` — composed at first use via
            :func:`build_turn_runtime_factory`. ``None`` (tests / legacy
            call sites) keeps the Core defaults (RULE-11).

    Returns:
        A fully wired :class:`WritingSessionHandler`.
    """
    from narrare.writing._ws_turn_support import (
        build_config_provider,
        build_turn_runtime_factory,
    )
    from narrare.writing.ws_direction_dispatch import WritingDirectionDispatcher
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare.writing.ws_message_router import WritingSessionMessageRouter
    from narrare.writing.ws_turn_service import WritingTurnService

    # ADR-086 L39: both closures share the connection's one resolution.
    config_provider = build_config_provider(model_resolution, limits)
    turn_service = WritingTurnService(
        composer=composer,
        invocation_pipeline=invocation_pipeline,
        registry=model_registry,
        runtime_factory=build_turn_runtime_factory(model_resolution, limits),
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
        config_provider=config_provider,
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
