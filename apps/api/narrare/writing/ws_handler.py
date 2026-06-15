"""WebSocket handler for interactive writing sessions.

Handles the full lifecycle of a WebSocket-based writing session:
connection acceptance, message routing, LLM interaction, and cleanup.

Supports two modes:
- ``interactive_session``: Collaborative writing — LLM generates prose,
  user steers direction.
- ``interview_assisted``: Structured interview — LLM asks questions,
  user answers, then LLM generates a draft.  Draft generation is
  delegated to :class:`InterviewDraftGenerator`.

All LLM calls go through :class:`ModelRegistry` (RULE-01).
All prompts built through :class:`PromptComposer` (RULE-02).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.result import StreamChunk
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.pipeline import WritingPipeline
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class WritingSessionHandler:
    """Handles WebSocket connections for interactive writing sessions.

    Supports ``interactive_session`` and ``interview_assisted`` modes.
    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        pipeline: WritingPipeline,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None,
        run_limit_resolver: DefaultRunLimitResolver,
        api_key: str | None = None,
        base_url: str | None = None,
        mode: str = "interactive_session",
        ws_idle_timeout: int = 1800,
    ) -> None:
        self._session_manager = session_manager
        self._pipeline = pipeline
        self._registry = registry
        self._composer = composer
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._api_key = api_key
        self._base_url = base_url
        self._mode = mode
        self._ws_idle_timeout = ws_idle_timeout
        # Connection-scoped identifiers — populated by ``handle()`` and
        # threaded into the invocation contract (ADR-045 Decision 6).
        self._ctx_user_id: UUID | None = None
        self._ctx_project_id: UUID | None = None
        self._ctx_chapter_id: UUID | None = None

    async def handle(
        self,
        websocket: WebSocket,
        chapter_id: UUID,
        user_id: str,
        project_id: UUID,
    ) -> None:
        """Handle a WebSocket session lifecycle.

        Accepts the connection, creates a session, and enters the
        message loop.  Cleans up on disconnect or timeout.
        """
        await websocket.accept()

        # Connection-scoped identifiers — threaded into the invocation
        # contract for draft generation (ADR-045 Decision 6). The handler
        # instance is per-connection, so this is safe single-use state.
        self._ctx_user_id = UUID(user_id)
        self._ctx_project_id = project_id
        self._ctx_chapter_id = chapter_id

        session_id: UUID | None = None
        try:
            session_id = await self._session_manager.create_session(
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=UUID(user_id),
            )

            # Mode-aware greeting
            if self._mode == "interview_assisted":
                await websocket.send_json(
                    {
                        "type": "greeting",
                        "mode": "interview",
                        "session_id": str(session_id),
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "greeting",
                        "message": "What would you like to write today?",
                        "session_id": str(session_id),
                    }
                )

            # Message loop with configurable idle timeout
            while True:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=self._ws_idle_timeout,
                )
                await self._route_message(websocket, session_id, data)

        except WebSocketDisconnect:
            logger.info(
                "session_disconnected",
                session_id=str(session_id),
                chapter_id=str(chapter_id),
            )
        except TimeoutError:
            await self._handle_timeout(websocket, session_id)
        except Exception as e:
            logger.error(
                "session_error",
                session_id=str(session_id),
                error=str(e),
            )
            await self._safe_send(
                websocket,
                {
                    "type": "error",
                    "message": "Internal session error",
                },
            )
        finally:
            if session_id is not None:
                await self._session_manager.end_session(session_id)

    # ------------------------------------------------------------------
    # Message routing
    # ------------------------------------------------------------------

    async def _route_message(
        self,
        websocket: WebSocket,
        session_id: UUID,
        data: dict[str, object],
    ) -> None:
        """Route incoming WebSocket messages to handlers."""
        msg_type = data.get("type")

        if msg_type == "user_direction":
            content = data.get("content", "")
            if isinstance(content, str) and content.strip():
                await self._handle_direction(websocket, session_id, content)
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Empty direction provided",
                    }
                )
        elif msg_type == "user_feedback":
            from narrare.writing._ws_session_handlers import handle_feedback

            await handle_feedback(websocket, session_id, data, self._session_manager)
        elif msg_type == "save_to_chapter":
            from narrare.writing._ws_session_handlers import handle_save

            await handle_save(websocket, session_id, self._session_manager)
        elif msg_type == "generate_draft" and self._mode == "interview_assisted":
            await self._handle_generate_draft(websocket, session_id)
        elif msg_type == "end_session":
            await websocket.close()
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }
            )

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_direction(
        self,
        websocket: WebSocket,
        session_id: UUID,
        content: str,
    ) -> None:
        """Handle user direction — generate text and stream back.

        In ``interactive_session`` mode, generates prose directly.
        In ``interview_assisted`` mode, asks follow-up questions.
        """
        await self._session_manager.add_message(session_id, "user", content)

        # Determine prompt mode based on session mode
        prompt_mode = "interview" if self._mode == "interview_assisted" else "interactive_session"

        # Stream generated response
        accumulated: list[str] = []
        final_chunk: StreamChunk | None = None
        try:
            from narrare_core.llm.intents import LLMIntent
            from narrare_core.prompts.context import PromptContext

            ctx = PromptContext(
                language="en",
                mode=prompt_mode,
                author_instructions=content,
            )
            intent = LLMIntent.CHAT if self._mode == "interview_assisted" else LLMIntent.WRITE
            prompt = await self._composer.build(intent, ctx)

            async for chunk in self._registry.stream(
                intent=intent,
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            ):
                if chunk.is_final:
                    final_chunk = chunk
                    break
                accumulated.append(chunk.text)
                await websocket.send_json(
                    {
                        "type": "text_chunk",
                        "text": chunk.text,
                    }
                )

        except Exception as e:
            logger.error(
                "direction_generation_failed",
                session_id=str(session_id),
                error=str(e),
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Generation failed: {e}",
                }
            )
            return

        full_text = "".join(accumulated)
        if full_text:
            await self._session_manager.add_message(
                session_id,
                "assistant",
                full_text,
            )
            msg: dict[str, object] = {"type": "text_done", "text": full_text}
            if final_chunk is not None and final_chunk.usage is not None:
                msg["usage"] = {
                    "prompt_tokens": final_chunk.usage.prompt_tokens,
                    "completion_tokens": final_chunk.usage.completion_tokens,
                    "total_tokens": final_chunk.usage.total_tokens,
                }
            await websocket.send_json(msg)

    async def _handle_generate_draft(
        self,
        websocket: WebSocket,
        session_id: UUID,
    ) -> None:
        """Generate a full draft from collected interview answers.

        Delegates to :func:`dispatch_interview_draft`, which runs the
        transport-agnostic generator through the invocation contract and
        maps the result to WebSocket DTOs (ADR-045 Decision 6/7).
        """
        from narrare.writing._ws_draft_dispatch import dispatch_interview_draft

        # Connection identifiers are set in ``handle()`` before the message
        # loop; this handler is only reachable from the loop.
        assert self._ctx_user_id is not None
        assert self._ctx_project_id is not None
        assert self._ctx_chapter_id is not None

        await dispatch_interview_draft(
            websocket=websocket,
            session_id=session_id,
            user_id=self._ctx_user_id,
            project_id=self._ctx_project_id,
            chapter_id=self._ctx_chapter_id,
            session_manager=self._session_manager,
            registry=self._registry,
            composer=self._composer,
            config=self._config,
            invocation_pipeline=self._invocation_pipeline,
            run_limit_resolver=self._run_limit_resolver,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def _handle_timeout(
        self,
        websocket: WebSocket,
        session_id: UUID | None,
    ) -> None:
        """Handle idle timeout gracefully."""
        logger.info(
            "session_timeout",
            session_id=str(session_id),
        )
        await self._safe_send(
            websocket,
            {
                "type": "timeout",
                "message": "Session timed out due to inactivity",
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _safe_send(
        websocket: WebSocket,
        data: dict[str, object],
    ) -> None:
        """Send JSON without raising on disconnect."""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.debug("ws_send_failed", hint="client likely disconnected")
