"""Tests for scripts/check_streaming_compliance.py.

Verifies SSE endpoint discovery, frontend consumer detection,
and violation reporting.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from check_streaming_compliance import (
    ComplianceResult,
    FrontendConsumer,
    SSEEndpoint,
    _extract_router_prefix,
    _extract_sse_routes,
    _extract_url_patterns,
    _url_patterns_match,
    format_json,
    format_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/writing", tags=["writing"])

    @router.post("/chapters/{chapter_id}/extend")
    async def extend_chapter(chapter_id: str) -> StreamingResponse:
        async def event_stream():
            yield "data: chunk\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @router.get("/status")
    async def get_status():
        return {"status": "ok"}
""")

SAMPLE_ROUTER_NO_PREFIX = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(tags=["chat"])

    @router.post("")
    async def chat_stream() -> StreamingResponse:
        async def event_stream():
            yield "data: chunk\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
""")

SAMPLE_FRONTEND_SSE = textwrap.dedent("""\
    import { connectSSE } from "./streaming";

    export async function extendChapter(chapterId: string) {
      return connectSSE({
        url: `/api/v1/writing/chapters/${chapterId}/extend`,
      });
    }
""")

SAMPLE_FRONTEND_REST = textwrap.dedent("""\
    export async function extendChapter(chapterId: string) {
      const response = await fetch(`/api/v1/writing/chapters/${chapterId}/extend`, {
        method: "POST",
      });
      return response.json();
    }
""")


# ---------------------------------------------------------------------------
# Tests: Router prefix extraction
# ---------------------------------------------------------------------------


class TestExtractRouterPrefix:
    def test_extracts_prefix_from_valid_source(self) -> None:
        prefix = _extract_router_prefix(SAMPLE_ROUTER)
        assert prefix == "/writing"

    def test_returns_empty_for_no_prefix(self) -> None:
        prefix = _extract_router_prefix(SAMPLE_ROUTER_NO_PREFIX)
        assert prefix == ""

    def test_returns_empty_for_no_router(self) -> None:
        prefix = _extract_router_prefix("# just a comment\n")
        assert prefix == ""


# ---------------------------------------------------------------------------
# Tests: SSE route extraction
# ---------------------------------------------------------------------------


class TestExtractSSERoutes:
    def test_extracts_sse_routes(self) -> None:
        routes = _extract_sse_routes(
            SAMPLE_ROUTER,
            "/writing",
            Path("writing/router_extend.py"),
        )
        assert len(routes) == 1
        assert routes[0].route == "/api/v1/writing/chapters/{chapter_id}/extend"
        assert routes[0].method == "POST"
        assert routes[0].name == "writing/router_extend"

    def test_ignores_non_sse_routes(self) -> None:
        routes = _extract_sse_routes(
            SAMPLE_ROUTER,
            "/writing",
            Path("writing/router_extend.py"),
        )
        # Only the extend route returns StreamingResponse, not the status route
        route_paths = [r.route for r in routes]
        assert "/api/v1/writing/status" not in route_paths

    def test_handles_empty_prefix(self) -> None:
        routes = _extract_sse_routes(
            SAMPLE_ROUTER_NO_PREFIX,
            "",
            Path("chat/router.py"),
        )
        assert len(routes) == 1
        assert routes[0].route == "/api/v1"


# ---------------------------------------------------------------------------
# Tests: Frontend consumer detection
# ---------------------------------------------------------------------------


class TestExtractUrlPatterns:
    def test_detects_sse_consumer(self) -> None:
        consumers = _extract_url_patterns(
            SAMPLE_FRONTEND_SSE,
            Path("lib/api/extend.ts"),
        )
        assert len(consumers) >= 1
        sse_consumers = [c for c in consumers if c.uses_sse]
        assert len(sse_consumers) >= 1
        assert "/api/v1/writing/chapters/" in sse_consumers[0].url_fragment

    def test_detects_rest_consumer(self) -> None:
        consumers = _extract_url_patterns(
            SAMPLE_FRONTEND_REST,
            Path("lib/api/extend.ts"),
        )
        rest_consumers = [c for c in consumers if not c.uses_sse]
        assert len(rest_consumers) >= 1


# ---------------------------------------------------------------------------
# Tests: URL pattern matching
# ---------------------------------------------------------------------------


class TestUrlPatternsMatch:
    def test_matches_extend_endpoint(self) -> None:
        assert _url_patterns_match(
            "/api/v1/writing/chapters/{chapter_id}/extend",
            "/api/v1/writing/chapters/123/extend",
        )

    def test_matches_stream_endpoint(self) -> None:
        assert _url_patterns_match(
            "/api/v1/writing/generation/{request_id}/stream",
            "/api/v1/writing/generation/abc/stream",
        )

    def test_rejects_different_domains(self) -> None:
        assert not _url_patterns_match(
            "/api/v1/writing/chapters/{chapter_id}/extend",
            "/api/v1/novels/{novel_id}/chapters",
        )

    def test_rejects_different_suffix(self) -> None:
        assert not _url_patterns_match(
            "/api/v1/writing/chapters/{chapter_id}/extend",
            "/api/v1/writing/chapters/{chapter_id}/rewrite",
        )

    def test_rejects_very_different_lengths(self) -> None:
        assert not _url_patterns_match(
            "/api/v1/writing/generation/{request_id}/stream",
            "/api/v1/novels/{novel_id}/kb/sessions/{session_id}/stream",
        )

    def test_matches_chat_endpoint(self) -> None:
        assert _url_patterns_match(
            "/api/v1/chat",
            "/api/v1/chat",
        )


# ---------------------------------------------------------------------------
# Tests: Report formatting
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_pass_report(self) -> None:
        result = ComplianceResult(
            sse_endpoints=[
                SSEEndpoint(
                    file=Path("writing/router.py"),
                    route="/api/v1/writing/generation/{}/stream",
                    method="GET",
                    prefix="/writing",
                    name="Generation",
                )
            ],
            consumers=[
                FrontendConsumer(
                    file=Path("lib/api/generation.ts"),
                    line=10,
                    uses_sse=True,
                    url_fragment="/api/v1/writing/generation/{}/stream",
                )
            ],
            passes=["Generation uses connectSSE via api/generation.ts"],
        )
        report = format_report(result)
        assert "SSE endpoints found: 1" in report
        assert "✅ PASS: Generation uses connectSSE" in report

    def test_violation_report(self) -> None:
        result = ComplianceResult(
            violations=["Chat uses fetch instead of connectSSE"],
        )
        report = format_report(result)
        assert "❌ VIOLATION: Chat uses fetch" in report

    def test_all_compliant(self) -> None:
        result = ComplianceResult()
        report = format_report(result)
        assert "All SSE-capable endpoints use streaming" in report


class TestFormatJson:
    def test_json_output_structure(self) -> None:
        result = ComplianceResult(
            sse_endpoints=[
                SSEEndpoint(
                    file=Path("writing/router.py"),
                    route="/api/v1/writing/generation/{}/stream",
                    method="GET",
                    prefix="/writing",
                    name="Generation",
                )
            ],
            violations=["violation1"],
        )
        output = json.loads(format_json(result))
        assert "sse_endpoints" in output
        assert "violations" in output
        assert output["compliant"] is False
        assert len(output["sse_endpoints"]) == 1
