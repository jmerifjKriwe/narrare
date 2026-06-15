"""WebSocket session-state message handlers.

Handles non-LLM session operations (user feedback, save-to-chapter).
Extracted from ``ws_handler.py`` for RULE-04 compliance — keeps the
handler focused on message routing and LLM streaming.

These handlers are transport-specific (they send WebSocket DTOs) but
contain no LLM or prompt logic.

See: CONSTRAINTS.md RULE-04/RULE-06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from fastapi import WebSocket

    from narrare_core.writing.session_manager import SessionManager


async def handle_feedback(
    websocket: WebSocket,
    session_id: UUID,
    data: dict[str, object],
    session_manager: SessionManager,
) -> None:
    """Handle user feedback (accept/reject) on generated text.

    Args:
        websocket: The WebSocket to send the acknowledgement to.
        session_id: The active session identifier.
        data: The message dict with ``action`` and ``text`` keys.
        session_manager: Session state manager for prose persistence.
    """
    action = data.get("action", "")
    text = data.get("text", "")

    if action == "accept" and isinstance(text, str) and text.strip():
        await session_manager.append_prose(session_id, text)
        await websocket.send_json({"type": "feedback_acknowledged", "action": "accept"})
    elif action == "reject":
        await websocket.send_json({"type": "feedback_acknowledged", "action": "reject"})
    else:
        await websocket.send_json(
            {"type": "error", "message": f"Invalid feedback action: {action}"}
        )


async def handle_save(
    websocket: WebSocket,
    session_id: UUID,
    session_manager: SessionManager,
) -> None:
    """Save the prose buffer to the chapter.

    Args:
        websocket: The WebSocket to send the result to.
        session_id: The active session identifier.
        session_manager: Session state manager for chapter persistence.
    """
    try:
        content = await session_manager.save_to_chapter(session_id)
        await websocket.send_json(
            {
                "type": "saved",
                "content": content,
                "word_count": len(content.split()),
            }
        )
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
