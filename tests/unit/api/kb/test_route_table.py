"""Route-table invariant tests for the KB HTTP surface (ADR-085 P4, Task 11).

The KB-009 merge HTTP surface (``kb/router_merge.py``) is retired — superseded
by the entity-resolution surface (ADR-085 D5). These tests pin the app route
table: the merge prefix must stay absent and the resolution prefix present.
``KBMergeService`` itself is untouched (Task 12's adjudicator adapter uses it).
"""

from __future__ import annotations

import importlib.util


def test_merge_router_module_is_retired() -> None:
    """The merge router module no longer exists (HTTP surface only).

    Service-level merge tests (``test_merge_service*.py``) keep covering
    ``KBMergeService`` — only the unmounted route module is gone.
    """
    assert importlib.util.find_spec("narrare.kb.router_merge") is None


def _app_paths() -> set[str]:
    """Mounted OpenAPI paths of the full app (no lifespan / DB needed)."""
    from narrare._app.main import create_app

    app = create_app(test_mode=True)
    return set(app.openapi()["paths"].keys())


def test_merge_route_prefix_is_absent_from_route_table() -> None:
    """No mounted path carries the retired ``/kb/merge`` prefix."""
    merge_paths = [path for path in _app_paths() if "/kb/merge" in path]
    assert merge_paths == []


def test_resolution_route_prefix_is_present_in_route_table() -> None:
    """All four entity-resolution endpoints are mounted under ``/kb/resolution``."""
    paths = _app_paths()
    expected = (
        "/api/v1/novels/{novel_id}/kb/resolution/analyze",
        "/api/v1/novels/{novel_id}/kb/resolution/suggestions",
        "/api/v1/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/endorse",
        "/api/v1/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/reject",
    )
    for path in expected:
        assert path in paths, f"missing resolution route: {path}"
