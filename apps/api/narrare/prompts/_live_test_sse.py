"""SSE event stream for PROMPT-003 live test — extracted for RULE-04.

Mirrors ``apps/api/narrare/writing/_coauthor_sse.py``. Yields
``text/event-stream`` frames for the optional prompt live test.

**SSE Event Stream:**

1. ``event: meta`` — full ``LiveTestStartedResponse`` (trace context enriched).
2. Text chunks: ``{"text": "..."}`` (zero or more delta events).
3. ``event: done`` — ``{"is_final": true}`` on successful completion.
4. ``data: [DONE]`` — termination signal.

On error (RULE-11 — no silent failures):
   ``event: error`` — ``{"error": "...", "error_type": "...", "is_final": true}``
   followed by ``data: [DONE]``. The error is logged before emission so the
   server-side observability stack always sees it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from narrare._app.observability import enrich_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

    from narrare.prompts.schemas_prompt_ux import LiveTestStartedResponse

logger = structlog.get_logger(__name__)


async def live_test_event_stream(
    chunks: AsyncIterator[str],
    *,
    metadata: LiveTestStartedResponse,
) -> AsyncIterator[str]:
    """Yield ``text/event-stream`` frames for the live-test output.

    Args:
        chunks: Async iterator of text chunks from the live-test agent.
        metadata: Validated start metadata emitted as the first meta event.

    Yields:
        SSE-formatted event strings. Terminates with ``data: [DONE]``.
    """
    # 1. Meta event — always first, carries the validated start metadata for
    #    client correlation and UI state (RULE-17 API/frontend contract).
    meta_data: dict[str, Any] = metadata.model_dump(mode="json")
    yield f"event: meta\ndata: {json.dumps(enrich_sse_data(meta_data))}\n\n"

    # 2. Delta events — one per chunk. Errors are surfaced as an error event,
    #    not silently swallowed (RULE-11). M2 (Core Spec Review): even if the
    #    agent's error classification is bypassed, the SSE layer catches and
    #    converts to a typed error frame so the client always sees termination.
    try:
        async for chunk in chunks:
            data: dict[str, Any] = {"text": chunk}
            yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
    except Exception as exc:
        logger.error(
            "prompt_live_test_stream_error",
            prompt_id=metadata.prompt_id,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        error_data: dict[str, Any] = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "is_final": True,
        }
        yield f"event: error\ndata: {json.dumps(enrich_sse_data(error_data))}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 3. Done event + termination signal.
    done_data: dict[str, Any] = {"is_final": True}
    yield f"event: done\ndata: {json.dumps(enrich_sse_data(done_data))}\n\n"
    yield "data: [DONE]\n\n"
