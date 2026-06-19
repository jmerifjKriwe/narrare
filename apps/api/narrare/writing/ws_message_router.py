"""Message router for WebSocket writing sessions.

Routes validated WebSocket messages to focused transport dispatchers. It owns
message-type branching only; prompt/model-call orchestration lives in the turn
service and draft generator.

See: ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket

    from narrare.writing.ws_direction_dispatch import WritingDirectionDispatcher
    from narrare.writing.ws_session_context import WritingSessionContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.session_manager import SessionManager


class WritingSessionMessageRouter:
    """Route WebSocket messages for an active writing session.

    Args:
        session_manager: Session state manager for non-LLM operations and
            draft persistence.
        direction_dispatcher: Dispatcher for ``user_direction`` turns.
        registry: Model registry used by interview draft generation.
        composer: Prompt composer used by interview draft generation.
        config: Resolved model configuration.
        invocation_pipeline: Invocation pipeline for draft generation.
        run_limit_resolver: Runtime output-budget resolver.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        direction_dispatcher: WritingDirectionDispatcher,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None,
        run_limit_resolver: DefaultRunLimitResolver,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._direction_dispatcher = direction_dispatcher
        self._registry = registry
        self._composer = composer
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._api_key = api_key
        self._base_url = base_url

    async def route(
        self,
        websocket: WebSocket,
        context: WritingSessionContext,
        data: dict[str, object],
    ) -> None:
        """Route a parsed WebSocket message to the appropriate dispatcher.

        Args:
            websocket: Active WebSocket connection.
            context: Connection-scoped identifiers and session mode.
            data: Parsed JSON message payload.
        """
        msg_type = data.get("type")

        if msg_type == "user_direction":
            await self._route_direction(websocket, context, data)
        elif msg_type == "user_feedback":
            from narrare.writing._ws_session_handlers import handle_feedback

            await handle_feedback(
                websocket,
                context.session_id,
                data,
                self._session_manager,
            )
        elif msg_type == "save_to_chapter":
            from narrare.writing._ws_session_handlers import handle_save

            await handle_save(websocket, context.session_id, self._session_manager)
        elif msg_type == "generate_draft" and context.mode == "interview_assisted":
            await self._route_generate_draft(websocket, context)
        elif msg_type == "end_session":
            await websocket.close()
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }
            )

    async def _route_direction(
        self,
        websocket: WebSocket,
        context: WritingSessionContext,
        data: dict[str, object],
    ) -> None:
        """Validate and dispatch a ``user_direction`` message."""
        content = data.get("content", "")
        if isinstance(content, str) and content.strip():
            await self._direction_dispatcher.dispatch(websocket, context, content)
            return
        await websocket.send_json(
            {
                "type": "error",
                "message": "Empty direction provided",
            }
        )

    async def _route_generate_draft(
        self,
        websocket: WebSocket,
        context: WritingSessionContext,
    ) -> None:
        """Dispatch interview draft generation for the active context."""
        from narrare.writing._ws_draft_dispatch import dispatch_interview_draft

        await dispatch_interview_draft(
            websocket=websocket,
            session_id=context.session_id,
            user_id=context.user_id,
            project_id=context.project_id,
            chapter_id=context.chapter_id,
            session_manager=self._session_manager,
            registry=self._registry,
            composer=self._composer,
            config=self._config,
            invocation_pipeline=self._invocation_pipeline,
            run_limit_resolver=self._run_limit_resolver,
            api_key=self._api_key,
            base_url=self._base_url,
        )
