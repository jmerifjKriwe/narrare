"""Tests for nested router prefix handling in streaming compliance."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture.streaming_compliance import (  # noqa: E402
    build_effective_router_prefixes,
    extract_included_router_aliases,
    extract_router_import_aliases,
)
from scripts.check_streaming_compliance import (  # noqa: E402
    _extract_router_prefix,
    _extract_sse_routes,
)

SAMPLE_PARENT_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter

    from narrare.planning.router_timeline_analysis import router as timeline_analysis_router

    router = APIRouter(prefix="/planning", tags=["planning"])
    router.include_router(timeline_analysis_router)
""")

SAMPLE_PARENT_ROUTER_WITH_INCLUDE_PREFIX = textwrap.dedent("""\
    from fastapi import APIRouter

    from narrare.planning.router_timeline_analysis import router as timeline_analysis_router

    router = APIRouter(prefix="/planning", tags=["planning"])
    router.include_router(timeline_analysis_router, prefix="/ai")
""")

SAMPLE_CHILD_ROUTER = textwrap.dedent("""\
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/timeline", tags=["timeline"])

    @router.post("/{novel_id}/extract")
    async def extract_temporal_expressions(novel_id: str) -> StreamingResponse:
        async def event_stream():
            yield "data: chunk\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
""")


class TestNestedRouterPrefixes:
    def test_extracts_router_include_import_aliases(self) -> None:
        aliases = extract_router_import_aliases(SAMPLE_PARENT_ROUTER)

        assert (
            aliases["timeline_analysis_router"]
            .as_posix()
            .endswith("apps/api/narrare/planning/router_timeline_analysis.py")
        )

    def test_extracts_included_router_aliases(self) -> None:
        includes = extract_included_router_aliases(SAMPLE_PARENT_ROUTER_WITH_INCLUDE_PREFIX)

        assert includes == [("timeline_analysis_router", "/ai")]

    def test_builds_effective_prefix_for_nested_router(self, tmp_path: Path) -> None:
        planning_dir = tmp_path / "apps" / "api" / "narrare" / "planning"
        planning_dir.mkdir(parents=True)
        parent_file = planning_dir / "router.py"
        child_file = planning_dir / "router_timeline_analysis.py"
        parent_file.write_text(SAMPLE_PARENT_ROUTER, encoding="utf-8")
        child_file.write_text(SAMPLE_CHILD_ROUTER, encoding="utf-8")

        prefixes = build_effective_router_prefixes(
            [parent_file, child_file], _extract_router_prefix
        )

        assert prefixes[child_file] == ["/planning/timeline"]

    def test_extracts_sse_route_with_effective_nested_prefix(self, tmp_path: Path) -> None:
        child_file = (
            tmp_path / "apps" / "api" / "narrare" / "planning" / "router_timeline_analysis.py"
        )
        child_file.parent.mkdir(parents=True)
        child_file.write_text(SAMPLE_CHILD_ROUTER, encoding="utf-8")

        routes = _extract_sse_routes(SAMPLE_CHILD_ROUTER, "/planning/timeline", child_file)

        assert len(routes) == 1
        assert routes[0].route == "/api/v1/planning/timeline/{novel_id}/extract"
