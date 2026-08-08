"""Regression tests for the ``narrare.tasks`` package (ADR-080).

The TaskIQ broker, worker process, broker-registered stubs, and the
``GET /tasks/status`` monitoring endpoint have been removed (ADR-080).
Background work now runs in-process. This file guards against silent
re-introduction:

- ``test_tasks_status_endpoint_not_mounted`` — asserts ``GET /tasks/status``
  is not registered on the app, so the endpoint cannot silently reappear.
"""

from __future__ import annotations


def test_tasks_status_endpoint_not_mounted() -> None:
    """GET /tasks/status is not registered on the app (regression, ADR-080).

    The monitoring endpoint and its backing broker were removed. If a router
    is accidentally re-mounted, this assertion fails loudly instead of
    silently re-introducing a Redis-backed surface.
    """
    from narrare._app.main import create_app

    app = create_app(test_mode=True)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/tasks/status" not in paths
