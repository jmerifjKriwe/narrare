"""Observation probes for E2E specs: console, network, accessibility.

Spec §4 (helpers package): probes.py owns every "what happened on the page
while the test ran" concern so specs assert instead of wiring listeners.

Scope note (spec §3): ``assert_no_provider_calls`` guards the BROWSER side —
the page's own requests must never reach an LLM provider host. The API side
is guaranteed by ``NARRARE_E2E_TEST=1`` (TestModel) and pinned by the
environment smoke spec via the ``e2e_test_mode_active`` startup banner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import ConsoleMessage, Page, Request, Response


#: LLM provider hosts the browser must never call (spec §3: no real LLM calls).
PROVIDER_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "openrouter.ai",
    }
)


@dataclass
class ConsoleCapture:
    """Collected console/page errors. Attach via :func:`capture_console`."""

    page_errors: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    console_warnings: list[str] = field(default_factory=list)

    def assert_no_page_errors(self, *, allow: tuple[str, ...] = ()) -> None:
        """Fail on unfiltered page errors (RULE-11: loud, with the list)."""
        offending = [e for e in self.page_errors if not any(a in e for a in allow)]
        assert not offending, f"Page errors during test: {offending}"

    def assert_no_console_errors(self, *, allow: tuple[str, ...] = ()) -> None:
        """Fail on unfiltered console.error messages."""
        offending = [e for e in self.console_errors if not any(a in e for a in allow)]
        assert not offending, f"console.error during test: {offending}"


@dataclass
class NetworkCapture:
    """Collected API failures + provider leaks. Attach via :func:`capture_network`."""

    api_failures: list[str] = field(default_factory=list)
    provider_calls: list[str] = field(default_factory=list)

    def assert_no_provider_calls(self) -> None:
        """Fail on ANY browser-side LLM provider request (spec §3)."""
        assert not self.provider_calls, (
            f"Browser made real LLM provider calls (spec violation): {self.provider_calls}"
        )

    def assert_no_api_failures(self, *, allow_statuses: tuple[int, ...] = ()) -> None:
        """Fail on unfiltered >=400 API responses (recorded 'METHOD url → status')."""
        offending = [
            f for f in self.api_failures if int(f.rsplit("→ ", 1)[1]) not in allow_statuses
        ]
        assert not offending, f"API failures during test: {offending}"


def capture_console(page: Page) -> ConsoleCapture:
    """Attach console/pageerror listeners and return the collector."""
    capture = ConsoleCapture()
    page.on("pageerror", lambda err: capture.page_errors.append(str(err)))

    def _on_console(msg: ConsoleMessage) -> None:
        if msg.type == "error":
            capture.console_errors.append(msg.text)
        elif msg.type == "warning":
            capture.console_warnings.append(msg.text)

    page.on("console", _on_console)
    return capture


def capture_network(page: Page) -> NetworkCapture:
    """Attach request/response listeners and return the collector."""
    capture = NetworkCapture()

    def _on_request(request: Request) -> None:
        host = urlparse(request.url).hostname or ""
        if host in PROVIDER_HOSTS:
            capture.provider_calls.append(f"{request.method} {request.url}")

    def _on_response(response: Response) -> None:
        if "/api/v1/" in response.url and response.status >= 400:
            capture.api_failures.append(
                f"{response.request.method} {response.url} → {response.status}"
            )

    page.on("request", _on_request)
    page.on("response", _on_response)
    return capture


def dump_a11y(page: Page, path: Path) -> Path:
    """Dump the page's accessibility tree to ``path`` as JSON; returns path.

    Uses the CDP ``Accessibility.getFullAXTree`` domain (Chromium — the E2E
    suite's only browser, see ``tests/e2e/conftest.py::browser_type_launch_args``),
    because ``page.accessibility`` was deprecated in Playwright 1.49 and
    removed by 1.61 (the version pinned here).
    """
    cdp = page.context.new_cdp_session(page)
    snapshot = cdp.send("Accessibility.getFullAXTree")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path
