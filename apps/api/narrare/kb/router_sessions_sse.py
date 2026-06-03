"""KB session SSE routes — streaming endpoint for session events.

Extracted from ``router_sessions.py`` for RULE-04 compliance (max 150 lines).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — needed at runtime for FastAPI path parameter resolution

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.observability import enrich_sse_data
from narrare.kb.dependencies import get_kb_session_service

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from narrare.kb.session_service import KBSessionService

router = APIRouter(tags=["kb-sessions"])


def _sse_event(event: str, data: dict[str, object]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/novels/{novel_id}/kb/sessions/{session_id}/stream")
async def stream_session(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> StreamingResponse:
    """SSE endpoint for streaming AI responses during a session."""

    async def _event_stream() -> AsyncGenerator[str]:
        """Yield SSE events wrapping session state."""
        session = await service.get_session(session_id)
        if session is None:
            yield _sse_event("error", {"detail": "Session not found"})
            return
        yield _sse_event(
            "session_state",
            enrich_sse_data(session.model_dump(mode="json")),
        )

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
