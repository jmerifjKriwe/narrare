"""WebSocket direction-message transport dispatcher (ADR-052).

Spawns the streaming turn as a decoupled ``asyncio.Task`` registered in
the :class:`ActiveTurnRegistry`, then returns immediately so the receive
loop is free to accept the next message (including ``stop_generation``).

The streaming task:
- Registers the active turn in :class:`SessionTurnStateStore`.
- Wraps the ``turn_service.stream_turn`` iterator with a
  :class:`StreamChunkRecorder` that records chunk text.
- Pushes DTOs to the transport sink via :func:`send_stream_chunks`.
- On ``CancelledError`` (stop): marks ``StreamStatus.STOPPED``, preserves
  partial prose.
- On error: marks ``StreamStatus.FAILED``, sends an error message.
- On completion: persists the assistant message, marks
  ``StreamStatus.COMPLETED``, emits ``text_done``.

See: ADR-052, ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12/RULE-20.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.writing.ws_sink import WebSocketSink
from narrare.writing.ws_streaming import StreamChunkRecorder, StreamSendResult, send_stream_chunks
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_context import WritingSessionContext
    from narrare.writing.ws_streaming import StreamSender
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.writing._enums import StreamStatus
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore

logger = structlog.get_logger(__name__)


class _RegistryBackedSink:
    """Sink that resolves the current session transport for every send.

    ADR-052 recovery requires ``ActiveTurnRegistry.rebind_sink`` to have a
    real transport effect while a stream is already running. Holding the
    original WebSocket would keep writing to the dead socket after reattach;
    this adapter follows the registry pointer on every chunk instead.
    """

    def __init__(self, registry: ActiveTurnRegistry, session_id: str) -> None:
        self._registry = registry
        self._session_id = session_id

    async def send_json(self, data: Mapping[str, object]) -> None:
        """Send through the currently bound sink for this session."""
        await self._registry.get_sink(self._session_id).send_json(data)


class WritingDirectionDispatcher:
    """Dispatch ``user_direction`` messages over the WebSocket transport.

    Spawns streaming as a background task registered in the
    :class:`ActiveTurnRegistry` (ADR-052 Decision 1). The receive loop
    is never blocked by streaming.

    Args:
        session_manager: Session state manager for transcript persistence.
        turn_state: In-process store for active-turn partial prose.
        registry: Active-turn registry for cancellable task handles.
        turn_service: Transport-agnostic writing turn orchestrator.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        turn_state: SessionTurnStateStore,
        registry: ActiveTurnRegistry,
        turn_service: WritingTurnService,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._turn_state = turn_state
        self._registry = registry
        self._turn_service = turn_service
        self._api_key = api_key
        self._base_url = base_url

    async def dispatch(
        self,
        websocket: StreamSender,
        context: WritingSessionContext,
        content: str,
    ) -> UUID | None:
        """Store a user direction and spawn the streaming turn.

        Returns the ``invocation_id`` on success, or ``None`` if a
        generation is already in progress (busy guard).

        Args:
            websocket: Transport with an async ``send_json`` method.
            context: Connection-scoped identifiers and session mode.
            content: User direction text.
        """
        session_id_str = str(context.session_id)

        # Busy guard — one active turn per session (ADR-052)
        if self._registry.get(session_id_str) is not None:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "A generation is already in progress. "
                    "Stop it before sending a new direction.",
                },
            )
            return None

        await self._session_manager.add_message(context.session_id, "user", content)

        invocation_id = uuid4()
        await self._turn_state.register_active_turn(
            session_id_str,
            str(invocation_id),
        )
        await self._mark_stream_status(context.session_id, "streaming")

        sink = WebSocketSink(websocket)
        task = asyncio.ensure_future(
            self._run_stream(context, content, invocation_id),
        )
        self._registry.register(
            session_id_str,
            str(invocation_id),
            task=task,
            sink=sink,
        )

        return invocation_id

    # ------------------------------------------------------------------
    # Streaming task body
    # ------------------------------------------------------------------

    async def _run_stream(
        self,
        context: WritingSessionContext,
        content: str,
        invocation_id: UUID,
    ) -> str | None:
        """Run the streaming turn as a decoupled task.

        Handles cancellation, errors, and completion. Returns the full
        text on completion, ``None`` otherwise.
        """
        session_id_str = str(context.session_id)
        try:
            result = await self._stream_into_sink(context, content)
        except asyncio.CancelledError:
            # stop_generation → Task.cancel() propagated here (RULE-20).
            # Partial prose was already read by the control service via
            # turn_state.cancel_active_turn; finalize the turn state.
            await self._turn_state.finalize_turn(
                session_id_str,
                status=self._resolve_status("stopped"),
            )
            await self._mark_stream_status(context.session_id, "stopped")
            self._registry.unregister(session_id_str)
            logger.info(
                "direction_stream_cancelled",
                session_id=session_id_str,
                invocation_id=str(invocation_id),
            )
            raise
        except WritingError as e:
            logger.error(
                "direction_generation_failed",
                session_id=session_id_str,
                error=str(e),
            )
            await self._send_to_current_sink(
                context.session_id, {"type": "error", "message": str(e)}
            )
            await self._turn_state.finalize_turn(
                session_id_str,
                status=self._resolve_status("failed"),
            )
            await self._mark_stream_status(context.session_id, "failed")
            self._registry.unregister(session_id_str)
            return None
        except Exception as e:
            logger.error(
                "direction_generation_failed",
                session_id=session_id_str,
                error=str(e),
            )
            await self._send_to_current_sink(
                context.session_id,
                {"type": "error", "message": f"Generation failed: {e}"},
            )
            await self._turn_state.finalize_turn(
                session_id_str,
                status=self._resolve_status("failed"),
            )
            await self._mark_stream_status(context.session_id, "failed")
            self._registry.unregister(session_id_str)
            return None

        # Success
        await self._turn_state.finalize_turn(
            session_id_str,
            final_text=result.full_text,
        )
        await self._mark_stream_status(context.session_id, "completed")

        if result.full_text:
            await self._session_manager.add_message(
                context.session_id,
                "assistant",
                result.full_text,
            )
            message: dict[str, object] = {
                "type": "text_done",
                "text": result.full_text,
            }
            if result.usage is not None:
                message["usage"] = {
                    "prompt_tokens": result.usage.prompt_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "total_tokens": result.usage.total_tokens,
                }
            await self._send_to_current_sink(context.session_id, message)

        self._registry.unregister(session_id_str)

        return result.full_text

    async def _stream_into_sink(
        self,
        context: WritingSessionContext,
        content: str,
    ) -> StreamSendResult:
        """Build the recorder-wrapped stream and send chunks via the adapter."""
        session_id_str = str(context.session_id)
        recorder = StreamChunkRecorder(self._turn_state, session_id_str)
        upstream = self._turn_service.stream_turn(
            content=content,
            session_mode=context.mode,
            user_id=context.user_id,
            project_id=context.project_id,
            chapter_id=context.chapter_id,
            session_id=context.session_id,
            api_key=self._api_key,
            base_url=self._base_url,
        )
        return await send_stream_chunks(
            _RegistryBackedSink(self._registry, session_id_str),
            recorder.wrap(upstream),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _mark_stream_status(
        self,
        session_id: UUID,
        status: str,
    ) -> None:
        """Best-effort update of ``stream_status`` on the cached SessionState.

        Failures are logged at debug — stream status is observability
        metadata, not a correctness requirement.
        """
        try:
            state = await self._session_manager._load(session_id)  # pyright: ignore[reportPrivateUsage]
            if state is not None:
                state.stream_status = self._resolve_status(status)
                await self._session_manager._persist(state)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            logger.debug(
                "stream_status_update_failed",
                session_id=str(session_id),
                status=status,
            )

    @staticmethod
    def _resolve_status(status: str) -> StreamStatus:
        """Resolve a status string to a StreamStatus enum value."""
        from narrare_core.writing._enums import StreamStatus

        return StreamStatus(status)

    async def _send_to_current_sink(
        self,
        session_id: UUID,
        data: dict[str, object],
    ) -> None:
        """Send a DTO through the registry's currently bound sink."""
        await self._registry.get_sink(str(session_id)).send_json(data)
