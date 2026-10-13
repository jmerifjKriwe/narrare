"""``mock_llm`` — install catalog fixtures on a page (spec §3).

Usage in specs::

    from tests.e2e.helpers import mock_llm

    mock_llm(page, "generation_stream")                    # happy variant
    mock_llm(page, "coreference_stream", fixture="error")  # failure path

Handlers fall back on method mismatch / url_exclude, so they compose with
the auth-proxy route (``**/api/v1/**``) regardless of registration order.
Call BEFORE the navigation that triggers the request (page.route contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from tests.e2e.mocks.catalog import RouteSpec, entries_for

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Route


class RoutablePage(Protocol):
    """What ``mock_llm`` needs from a page — nothing more.

    Structural contract (RULE-03): real ``playwright.sync_api.Page`` objects
    satisfy it, and so do the test doubles in unit tests — with zero
    type-ignore suppressions at the call sites (RULE-23: structural typing
    instead of baseline-grown ignore lists).
    """

    def route(
        self,
        pattern: str,
        handler: Callable[[Route], None],
        /,
    ) -> None: ...


def mock_llm(
    page: RoutablePage,
    capability: str,
    *,
    fixture: str = "happy",
) -> list[RouteSpec]:
    """Install the catalog's route handlers for one capability+variant."""
    specs = entries_for(capability, fixture)
    for spec in specs:
        page.route(spec.pattern, _handler_for(spec))
    return specs


def _handler_for(spec: RouteSpec) -> Callable[[Route], None]:
    def _handle(route: Route) -> None:
        request = route.request
        if request.method != spec.method or spec.is_excluded(request.url):
            route.fallback()
            return
        route.fulfill(
            status=spec.status,
            content_type=spec.content_type,
            body=spec.body,
        )

    return _handle
