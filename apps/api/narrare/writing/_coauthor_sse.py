"""SSE event stream for co-author. Extracted from router_coauthor.py for RULE-04."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from narrare._app.observability import enrich_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any
    from uuid import UUID

    from narrare.writing.schemas_coauthor import CoAuthorRequest


async def coauthor_event_stream(
    service: Any,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
    request: CoAuthorRequest,
) -> AsyncIterator[str]:
    """SSE event generator for co-author streaming response.

    Yields ``text/event-stream`` formatted strings.  Extracted from the
    ``coauthor_chapter`` route to keep ``router_coauthor.py`` under
    RULE-04's 150-line limit.

    **SSE Event Stream:**

    1. ``context_meta`` event (CR-07 pattern) with KB context data.
    2. Text chunks: ``{"text": "..."}``
    3. Final event (last text chunk):
       - ``is_final: True``
       - ``usage: {prompt_tokens, completion_tokens, total_tokens}``
       - ``changes: [...]`` — list of change details
       - ``total_changes: N``
       - ``has_changes: True/False``
    4. ``data: [DONE]`` termination signal.

    Args:
        service: CoAuthorService instance.
        chapter_id: Chapter containing the selection to revise.
        novel_id: Novel the chapter belongs to.
        user_id: Authenticated user identifier.
        request: Co-author-specific parameters (selection_text,
            context, focus, etc.).

    Yields:
        SSE-formatted event strings.
    """
    async for chunk in service.stream_coauthor(
        chapter_id,
        novel_id,
        user_id,
        request,
    ):
        # CR-07 context metadata event — always the first chunk from
        # the pipeline (is_final=False, context_meta has KB context data).
        if chunk.context_meta is not None and not chunk.is_final:
            meta_data: dict[str, Any] = {"type": "context_meta"}
            meta_data.update(chunk.context_meta)
            yield f"data: {json.dumps(enrich_sse_data(meta_data))}\n\n"
            continue

        # Normal text chunk (includes the final chunk with diff metadata)
        data: dict[str, Any] = {"text": chunk.text}
        if chunk.is_final:
            data["is_final"] = True
            # Co-author diff metadata from pipeline_coauthor
            if chunk.context_meta is not None:
                for key in (
                    "changes",
                    "total_changes",
                    "has_changes",
                    "reasoning",
                    "request_id",
                ):
                    if key in chunk.context_meta:
                        data[key] = chunk.context_meta[key]
        if chunk.usage is not None:
            data["usage"] = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
        yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
    yield "data: [DONE]\n\n"
