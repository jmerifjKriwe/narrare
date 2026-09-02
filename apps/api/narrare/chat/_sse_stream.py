"""Chat agent→SSE stream bridge (RULE-04 extraction from chat_service).

Owns the single responsibility of mapping ``ChatAgent.run_stream()``
events to chat SSE dict events: meta/token/done emission, ProcessHistory
tracking for conversational continuity (ADR-034), and persistence of the
full assistant response (including the partial text accumulated before a
failure — RULE-11, no silent errors).

Extracted from ``chat_service.py`` for RULE-04 compliance — the service
was at the 300-line hard limit; modularise, never compress.

See:
    ADR-024 (ChatAgent), ADR-034 (ProcessHistory), ADR-045/ADR-048,
    RULE-04 (Modularise, never compress), RULE-11 (no silent errors).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from narrare.chat._response_helpers import save_assistant_response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.agents.process_history import ProcessHistory
    from narrare_core.chat.chat_agent import ChatAgent
    from narrare_core.chat.chat_deps import ChatDeps

logger = structlog.get_logger(__name__)


async def stream_agent_events(
    *,
    agent: ChatAgent,
    deps: ChatDeps,
    prompt: str,
    message_history: list[Any] | None,
    stream_kwargs: dict[str, object],
    conv_id: UUID,
    history: ProcessHistory,
    histories: dict[UUID, ProcessHistory],
    store: SQLAlchemyConversationStore,
) -> AsyncIterator[dict[str, object]]:
    """Run the agent stream and yield chat SSE dict events.

    Yields the ``meta`` event first, then maps agent ``token``/``done``
    events to SSE dicts. Updates ``histories[conv_id]`` when the agent
    returns new messages (ADR-034) and persists the full response — or
    the partial response on failure — via ``save_assistant_response``.
    Errors are logged and re-raised, never swallowed (RULE-11).

    Args:
        agent: The ChatAgent to stream from.
        deps: ChatDeps carrying the enriched context (ADR-048 Mode 2).
        prompt: The user-channel prompt (ADR-046 — system prompt is
            injected via the agent constructor, never concatenated here).
        message_history: Prior-turn pydantic-ai messages (ADR-034);
            ``None`` on the first turn. Opaque pydantic-ai message type
            (mirrors ``ProcessHistory.messages``).
        stream_kwargs: Resolved run-limit kwargs (ADR-045 Decision 4).
        conv_id: The conversation UUID.
        history: This conversation's ProcessHistory (mutated on done).
        histories: The service-level conversation→history registry.
        store: The conversation store for response persistence.
    """
    # Yield meta event with conversation ID
    yield {
        "type": "meta",
        "conversation_id": str(conv_id),
        "request_id": str(uuid4()),
    }

    # Stream agent response. ADR-046: only composed.user (user channel) is
    # passed as prompt; the system prompt is injected via the constructor.
    full_response = ""
    try:
        async for event in agent.run_stream(
            prompt=prompt,
            deps=deps,
            message_history=message_history,
            **stream_kwargs,
        ):
            if event.type == "token":
                yield {"type": "token", "text": event.text}
                full_response += event.text
            elif event.type == "done":
                # Update ProcessHistory with new messages from this turn
                if event.new_messages:
                    history.add(event.new_messages)
                    histories[conv_id] = history

                yield {
                    "type": "done",
                    "usage": event.usage or {},
                }
                # Use the complete text from the done event
                if event.text:
                    full_response = event.text
    except Exception as exc:
        logger.error(
            "chat_stream_failed",
            conversation_id=str(conv_id),
            error=str(exc),
            exc_info=True,
        )
        await save_assistant_response(store, conv_id, full_response)
        raise

    await save_assistant_response(store, conv_id, full_response)
