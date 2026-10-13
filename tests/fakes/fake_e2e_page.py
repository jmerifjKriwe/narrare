"""Browser-free double for the playwright sync ``Page`` surface.

The e2e helper units (``tests/unit/test_e2e_*.py``) test helper LOGIC —
selectors, wait predicates, call ordering, fail-loud behavior — without
launching a browser (ADR-030 spirit: fake-based doubles, not behavior-free
MagicMocks). The double RECORDS every interaction so specs can assert exact
call sequences (e.g. the N06 ordering pin in ``build_stable_session``), and
lets tests inject failures per method to prove RULE-11 propagation (no
auto-heal/retry).

The e2e helpers type their ``page`` parameter against narrow structural
Protocols (RoutablePage precedent in ``tests/e2e/helpers/llm_mocks.py``);
``FakeE2EPage`` satisfies them all by providing the full recorded surface.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeE2ELocator:
    """Locator double: records ``wait_for`` calls, never blocks."""

    def __init__(self, page: FakeE2EPage, selector: str) -> None:
        self._page = page
        self._selector = selector

    def wait_for(self, *, state: str = "", timeout: float = 0.0) -> None:
        self._page.events.append(("locator_wait", self._selector, state, str(timeout)))


class FakeE2EPage:
    """Records every page interaction; can simulate failures per method."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []
        self.gotos: list[str] = []
        self.url_predicates: list[Any] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.clicks: list[str] = []
        self.init_scripts: list[str] = []
        self.routes: list[tuple[str, Any]] = []
        self.wait_for_function_calls: list[tuple[str, str]] = []
        self.wait_for_url_exc: Exception | None = None
        self.wait_for_function_exc: Exception | None = None

    def goto(self, url: str, *, wait_until: str | None = None) -> None:
        self.events.append(("goto", url, wait_until or ""))
        self.gotos.append(url)

    def locator(self, selector: str) -> FakeE2ELocator:
        return FakeE2ELocator(self, selector)

    def fill(self, selector: str, value: str) -> None:
        self.events.append(("fill", selector, value))
        self.fill_calls.append((selector, value))

    def click(self, selector: str) -> None:
        self.events.append(("click", selector))
        self.clicks.append(selector)

    def wait_for_url(self, url: Any, *, timeout: float) -> None:
        self.events.append(("wait_for_url", str(timeout)))
        self.url_predicates.append(url)
        if self.wait_for_url_exc is not None:
            raise self.wait_for_url_exc

    def wait_for_function(self, expression: str, *, timeout: float) -> None:
        self.events.append(("wait_for_function", expression, str(timeout)))
        self.wait_for_function_calls.append((expression, str(timeout)))
        if self.wait_for_function_exc is not None:
            raise self.wait_for_function_exc

    def add_init_script(self, script: str) -> None:
        self.events.append(("init_script", script))
        self.init_scripts.append(script)

    def route(self, pattern: str, handler: Any, /) -> None:
        self.events.append(("route", pattern))
        self.routes.append((pattern, handler))


class FakeE2ERoute:
    """Route double for exercising a handler installed via ``page.route``.

    Mimics the slice of the playwright ``Route`` API that the auth-proxy
    handler (``tests/e2e/test_helpers._setup_auth_proxy``) touches.
    """

    def __init__(self) -> None:
        self.request = SimpleNamespace(headers={"accept": "application/json"})
        self.fetch_headers: dict[str, str] | None = None
        self.fulfilled: dict[str, Any] | None = None

    def fetch(self, *, headers: dict[str, str] | None = None) -> Any:
        self.fetch_headers = headers
        return SimpleNamespace(
            status=200,
            headers={"content-type": "application/json"},
            body=lambda: b"{}",
        )

    def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = kwargs
