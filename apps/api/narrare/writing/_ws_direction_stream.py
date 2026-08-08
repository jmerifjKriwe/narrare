"""WebSocket direction-message streaming task helper (ADR-052).

Owns the complete streaming-turn lifecycle spawned by
:class:`WritingDirectionDispatcher` as a decoupled ``asyncio.Task``:

- Wraps the ``turn_service.stream_turn`` iterator with a
  :class:`StreamChunkRecorder` that records chunk text.
- Pushes DTOs to the transport sink via :func:`send_stream_chunks`.
- On ``CancelledError`` (stop): marks ``StreamStatus.STOPPED``, preserves
  partial prose.
- On error: marks ``StreamStatus.FAILED``, sends an error message.
- On completion: persists the assistant message, marks
  ``StreamStatus.COMPLETED``, emits ``text_done``.

end_session race (PR #157 follow-up): the success tail is exception-safe
with ``unregister`` in a ``finally`` — the registry entry is cleaned up
unconditionally. The benign end_session ``ValueError`` from
``add_message`` (session already evicted) is deliberately dropped: the
assistant message is not persisted, ``text_done`` is skipped, and the
race is logged at info as ``direction_stream_session_ended``.
:func:`on_stream_done` is the last-resort safety net attached at the
dispatch site: it retrieves any escaped exception (logged at error as
``direction_stream_task_failed``) and guarantees registry cleanup.

See: ADR-052, ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12/RULE-20.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.writing.ws_streaming import StreamChunkRecorder, StreamSendResult, send_stream_chunks
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_context import WritingSessionContext
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


async def run_direction_stream(
    *,
    session_manager: SessionManager,
    turn_state: SessionTurnStateStore,
    registry: ActiveTurnRegistry,
    turn_service: WritingTurnService,
    api_key: str | None,
    base_url: str | None,
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
        result = await _stream_into_sink(
            turn_state=turn_state,
            registry=registry,
            turn_service=turn_service,
            api_key=api_key,
            base_url=base_url,
            context=context,
            content=content,
        )
    except asyncio.CancelledError:
        # stop_generation → Task.cancel() propagated here (RULE-20).
        # Partial prose was already read by the control service via
        # turn_state.cancel_active_turn; finalize the turn state.
        await turn_state.finalize_turn(
            session_id_str,
            status=_resolve_status("stopped"),
        )
        await mark_stream_status(session_manager, context.session_id, "stopped")
        registry.unregister(session_id_str)
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
        await _send_to_current_sink(
            registry, context.session_id, {"type": "error", "message": str(e)}
        )
        await turn_state.finalize_turn(
            session_id_str,
            status=_resolve_status("failed"),
        )
        await mark_stream_status(session_manager, context.session_id, "failed")
        registry.unregister(session_id_str)
        return None
    except Exception as e:
        logger.error(
            "direction_generation_failed",
            session_id=session_id_str,
            error=str(e),
        )
        await _send_to_current_sink(
            registry,
            context.session_id,
            {"type": "error", "message": f"Generation failed: {e}"},
        )
        await turn_state.finalize_turn(
            session_id_str,
            status=_resolve_status("failed"),
        )
        await mark_stream_status(session_manager, context.session_id, "failed")
        registry.unregister(session_id_str)
        return None

    # Success — exception-safe tail (PR #157 follow-up). The registry
    # entry must be cleaned up unconditionally, even if a body step
    # raises, and the benign end_session race must not surface as an
    # unretrieved task exception.
    try:
        await turn_state.finalize_turn(
            session_id_str,
            final_text=result.full_text,
        )
        await mark_stream_status(session_manager, context.session_id, "completed")

        if result.full_text:
            try:
                await session_manager.add_message(
                    context.session_id,
                    "assistant",
                    result.full_text,
                )
            except ValueError as e:
                # Benign end_session/expiry race: end_session evicted the
                # cache while this turn was streaming, so _load_or_raise
                # in add_message raises "Session ... not found or
                # expired." — the ONLY ValueError source in this path
                # (verified against session_manager.py). The session was
                # intentionally ended: the assistant message is
                # deliberately dropped and the transport is already
                # closed, so there is no text_done listener either.
                logger.info(
                    "direction_stream_session_ended",
                    session_id=session_id_str,
                    invocation_id=str(invocation_id),
                    error=str(e),
                )
            else:
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
                await _send_to_current_sink(registry, context.session_id, message)
    finally:
        # Unconditional last act of the success path — never leak the
        # registry entry, whatever the body did.
        registry.unregister(session_id_str)

    return result.full_text


async def _stream_into_sink(
    *,
    turn_state: SessionTurnStateStore,
    registry: ActiveTurnRegistry,
    turn_service: WritingTurnService,
    api_key: str | None,
    base_url: str | None,
    context: WritingSessionContext,
    content: str,
) -> StreamSendResult:
    """Build the recorder-wrapped stream and send chunks via the adapter."""
    session_id_str = str(context.session_id)
    recorder = StreamChunkRecorder(turn_state, session_id_str)
    upstream = turn_service.stream_turn(
        content=content,
        session_mode=context.mode,
        user_id=context.user_id,
        project_id=context.project_id,
        chapter_id=context.chapter_id,
        session_id=context.session_id,
        api_key=api_key,
        base_url=base_url,
    )
    return await send_stream_chunks(
        _RegistryBackedSink(registry, session_id_str),
        recorder.wrap(upstream),
    )


async def mark_stream_status(
    session_manager: SessionManager,
    session_id: UUID,
    status: str,
) -> None:
    """Best-effort update of ``stream_status`` on the cached SessionState.

    Failures are logged at debug — stream status is observability
    metadata, not a correctness requirement.
    """
    try:
        state = await session_manager._load(session_id)  # pyright: ignore[reportPrivateUsage]
        if state is not None:
            state.stream_status = _resolve_status(status)
            await session_manager._persist(state)  # pyright: ignore[reportPrivateUsage]
    except Exception:
        logger.debug(
            "stream_status_update_failed",
            session_id=str(session_id),
            status=status,
        )


def _resolve_status(status: str) -> StreamStatus:
    """Resolve a status string to a StreamStatus enum value."""
    from narrare_core.writing._enums import StreamStatus

    return StreamStatus(status)


async def _send_to_current_sink(
    registry: ActiveTurnRegistry,
    session_id: UUID,
    data: dict[str, object],
) -> None:
    """Send a DTO through the registry's currently bound sink."""
    await registry.get_sink(str(session_id)).send_json(data)


def on_stream_done(
    registry: ActiveTurnRegistry,
    session_id: str,
    task: asyncio.Task[str | None],
) -> None:
    """Done-callback for the decoupled streaming task (PR #157 follow-up).

    Last-resort safety net attached at the dispatch site: retrieves any
    exception that escaped the task body (so ``Task exception was never
    retrieved`` can never happen) and guarantees registry cleanup even
    if the body's own ``unregister`` was skipped. Idempotent — a no-op
    on the normal success/error/cancel paths.

    stop_generation path: ``registry.cancel`` pops and cancels the task;
    the body's ``CancelledError`` branch unregisters (no-op after the
    pop); this callback sees ``task.cancelled()`` and returns — no
    double handling.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "direction_stream_task_failed",
            session_id=session_id,
            error=str(exc),
            exc_info=exc,
        )
    # Idempotent — no-op on normal paths; last resort only.
    registry.unregister(session_id)
