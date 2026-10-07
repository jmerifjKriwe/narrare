"""Tests for media-type-aware SSE classification in the RULE-20 checker.

RULE-20 targets server-sent event streams. A ``StreamingResponse`` with an
explicit non-event-stream ``media_type`` (e.g. a CSV file download) must NOT
be flagged as an SSE endpoint lacking a frontend consumer. Classification is
fail-closed: routes whose media type is not statically resolvable stay
flagged.

Split from test_check_streaming_compliance.py to comply with RULE-04
(no file exceeds 400 lines).
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture.streaming_compliance import (  # noqa: E402
    SSE_MEDIA_TYPE,
    collect_media_type_literals,
    extract_route_decorators,
    route_is_sse_stream,
)
from scripts.check_streaming_compliance import _extract_sse_routes  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CSV_EXPORT_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter, Query
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/analytics", tags=["analytics"])

    @router.get("/costs/export")
    async def export_costs_csv(
        month: str | None = Query(default=None),
    ) -> StreamingResponse:
        return StreamingResponse(
            _iter_csv_lines(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="costs.csv"'},
        )
""")

OCTET_STREAM_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/files")

    @router.get("/{file_id}/download")
    async def download_file(file_id: str) -> StreamingResponse:
        return StreamingResponse(_chunks(), media_type="application/octet-stream")
""")

SSE_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/chat")

    @router.post("")
    async def chat_stream() -> StreamingResponse:
        async def event_stream():
            yield "data: chunk\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
""")

NO_MEDIA_TYPE_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/reports")

    @router.get("/stream")
    async def stream_report() -> StreamingResponse:
        return StreamingResponse(_rows())
""")

NON_LITERAL_MEDIA_TYPE_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/analytics")

    CSV_MEDIA_TYPE = "text/csv; charset=utf-8"

    @router.get("/costs/export")
    async def export_costs_csv() -> StreamingResponse:
        return StreamingResponse(_iter_csv_lines(), media_type=CSV_MEDIA_TYPE)
""")

MIXED_MEDIA_TYPE_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/dual")

    @router.get("/stream")
    async def stream_either() -> StreamingResponse:
        if _wants_events():
            return StreamingResponse(_events(), media_type="text/event-stream")
        return StreamingResponse(_rows(), media_type="text/csv")
""")


# ---------------------------------------------------------------------------
# Tests: end-to-end route extraction with media types
# ---------------------------------------------------------------------------


class TestMediaTypeAwareExtraction:
    def test_csv_download_route_is_not_flagged(self) -> None:
        """StreamingResponse + explicit text/csv media_type ⇒ not an SSE endpoint."""
        routes = _extract_sse_routes(
            CSV_EXPORT_ROUTER,
            "/analytics",
            Path("analytics/router.py"),
        )
        assert routes == []

    def test_octet_stream_download_route_is_not_flagged(self) -> None:
        routes = _extract_sse_routes(
            OCTET_STREAM_ROUTER,
            "/files",
            Path("files/router.py"),
        )
        assert routes == []

    def test_event_stream_route_is_still_flagged(self) -> None:
        routes = _extract_sse_routes(SSE_ROUTER, "/chat", Path("chat/router.py"))
        assert len(routes) == 1
        assert routes[0].route == "/api/v1/chat"

    def test_route_without_media_type_stays_flagged(self) -> None:
        """No statically resolvable media type ⇒ fail-closed, keep flagging."""
        routes = _extract_sse_routes(
            NO_MEDIA_TYPE_ROUTER,
            "/reports",
            Path("reports/router.py"),
        )
        assert len(routes) == 1

    def test_non_literal_media_type_stays_flagged(self) -> None:
        """A media_type from a variable is not statically resolvable ⇒ flagged."""
        routes = _extract_sse_routes(
            NON_LITERAL_MEDIA_TYPE_ROUTER,
            "/analytics",
            Path("analytics/router_export.py"),
        )
        assert len(routes) == 1

    def test_mixed_media_types_stay_flagged(self) -> None:
        """Any event-stream media_type on the route ⇒ stays in SSE scope."""
        routes = _extract_sse_routes(
            MIXED_MEDIA_TYPE_ROUTER,
            "/dual",
            Path("dual/router.py"),
        )
        assert len(routes) == 1


# ---------------------------------------------------------------------------
# Tests: classifier and literal collection in isolation
# ---------------------------------------------------------------------------


class TestRouteIsSSEStream:
    def test_empty_media_types_is_sse(self) -> None:
        assert route_is_sse_stream(())

    def test_event_stream_media_type_is_sse(self) -> None:
        assert route_is_sse_stream((SSE_MEDIA_TYPE,))

    def test_csv_media_type_is_not_sse(self) -> None:
        assert not route_is_sse_stream(("text/csv; charset=utf-8",))

    def test_octet_stream_media_type_is_not_sse(self) -> None:
        assert not route_is_sse_stream(("application/octet-stream",))

    def test_mixed_media_types_fail_closed_to_sse(self) -> None:
        assert route_is_sse_stream(("text/csv", SSE_MEDIA_TYPE))


class TestCollectMediaTypeLiterals:
    def test_collects_from_streaming_response_call(self) -> None:
        decorators = extract_route_decorators(CSV_EXPORT_ROUTER)
        assert len(decorators) == 1
        assert decorators[0].media_types == ("text/csv; charset=utf-8",)

    def test_collects_event_stream_media_type(self) -> None:
        decorators = extract_route_decorators(SSE_ROUTER)
        assert decorators[0].media_types == ("text/event-stream",)

    def test_empty_when_no_media_type(self) -> None:
        decorators = extract_route_decorators(NO_MEDIA_TYPE_ROUTER)
        assert decorators[0].media_types == ()

    def test_skips_non_literal_values(self) -> None:
        decorators = extract_route_decorators(NON_LITERAL_MEDIA_TYPE_ROUTER)
        assert decorators[0].media_types == ()

    def test_collects_multiple_literals(self) -> None:
        node = ast.parse(MIXED_MEDIA_TYPE_ROUTER).body[-1]
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        # ast.walk order is unspecified — only the set of literals matters.
        assert set(collect_media_type_literals(node)) == {"text/event-stream", "text/csv"}
