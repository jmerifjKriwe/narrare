"""Tests for multi-line decorator extraction in check_streaming_compliance.py.

These tests verify that _extract_sse_routes correctly handles AST-based
multi-line decorator patterns (a blind-spot the original regex approach
could not handle).

Extracted from test_check_streaming_compliance.py to comply with RULE-04
(no file exceeds 400 lines).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_streaming_compliance import _extract_sse_routes  # noqa: E402


class TestExtractSSERoutesMultiline:
    """Multi-line decorator detection (AST-based extraction)."""

    def test_multi_line_decorator_detected(self) -> None:
        """A multi-line @router.post(...) with StreamingResponse is detected."""
        source = textwrap.dedent("""\
            from fastapi.responses import StreamingResponse
            from fastapi import APIRouter, Depends

            router = APIRouter(prefix="/analysis")

            @router.post(
                "/voice-check/{chapter_id}",
                dependencies=[Depends(auth)],
            )
            async def voice_check(chapter_id: str) -> StreamingResponse:
                async def event_stream():
                    yield "data: chunk\\n\\n"
                return StreamingResponse(event_stream(), media_type="text/event-stream")
        """)
        routes = _extract_sse_routes(source, "/analysis", Path("analysis/router_voice.py"))
        assert len(routes) == 1
        assert routes[0].route == "/api/v1/analysis/voice-check/{chapter_id}"
        assert routes[0].method == "POST"

    def test_multi_line_decorator_no_sse_ignored(self) -> None:
        """A multi-line decorator without StreamingResponse is ignored."""
        source = textwrap.dedent("""\
            from fastapi import APIRouter, Depends

            router = APIRouter(prefix="/analysis")

            @router.post(
                "/voice-check/{chapter_id}",
                dependencies=[Depends(auth)],
            )
            async def voice_check(chapter_id: str):
                return {"status": "ok"}
        """)
        routes = _extract_sse_routes(source, "/analysis", Path("analysis/router_voice.py"))
        assert len(routes) == 0

    def test_multi_line_decorator_with_get_method(self) -> None:
        """A multi-line @router.get(...) with StreamingResponse is detected."""
        source = textwrap.dedent("""\
            from fastapi.responses import StreamingResponse
            from fastapi import APIRouter

            router = APIRouter(prefix="/planning")

            @router.get(
                "/timeline/{project_id}/events",
                tags=["timeline"],
            )
            async def get_timeline_events(project_id: str) -> StreamingResponse:
                async def event_stream():
                    yield "data: event\\n\\n"
                return StreamingResponse(event_stream(), media_type="text/event-stream")
        """)
        routes = _extract_sse_routes(source, "/planning", Path("planning/router_timeline.py"))
        assert len(routes) == 1
        assert routes[0].route == "/api/v1/planning/timeline/{project_id}/events"
        assert routes[0].method == "GET"

    def test_multi_line_decorator_complex_args(self) -> None:
        """A multi-line decorator with many keyword args and StreamingResponse."""
        source = textwrap.dedent("""\
            from fastapi.responses import StreamingResponse
            from fastapi import APIRouter, Depends, status

            router = APIRouter(prefix="/analysis")

            @router.post(
                "/deep-check/{chapter_id}",
                dependencies=[Depends(auth), Depends(rate_limiter)],
                status_code=status.HTTP_200_OK,
                tags=["analysis", "deep"],
                summary="Deep analysis of a chapter",
            )
            async def deep_check(chapter_id: str) -> StreamingResponse:
                async def event_stream():
                    yield "data: chunk\\n\\n"
                return StreamingResponse(event_stream(), media_type="text/event-stream")
        """)
        routes = _extract_sse_routes(source, "/analysis", Path("analysis/router_deep.py"))
        assert len(routes) == 1
        assert routes[0].route == "/api/v1/analysis/deep-check/{chapter_id}"
        assert routes[0].method == "POST"
