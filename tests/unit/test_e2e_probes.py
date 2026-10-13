"""Unit tests for the E2E observation probes (tests/e2e/helpers/probes.py).

The probes are test-infra, but they carry assertions other specs rely on —
so they get the same regression discipline as product code. These tests run
WITHOUT a browser: a fake page records the listeners the probe attaches and
emits canned events through them.

``cast("Page", ...)`` is used at the probe-call boundary instead of inline
``# type: ignore`` comments so the repo's type-ignore baseline stays at 875.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from tests.e2e.helpers.probes import (
    PROVIDER_HOSTS,
    capture_console,
    capture_network,
    dump_a11y,
)

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page


class _FakeConsoleMessage:
    def __init__(self, type_: str, text: str) -> None:
        self.type = type_
        self.text = text


class _FakeRequest:
    def __init__(self, method: str, url: str) -> None:
        self.method = method
        self.url = url


class _FakeResponse:
    def __init__(self, request: _FakeRequest, url: str, status: int) -> None:
        self.request = request
        self.url = url
        self.status = status


class _FakePage:
    """Minimal Page stand-in: records .on() listeners, emits via .emit()."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[Any]] = {}
        self.a11y_snapshot: dict[str, Any] | None = None

    def on(self, event: str, handler: Any) -> None:
        self.listeners.setdefault(event, []).append(handler)

    def emit(self, event: str, arg: Any) -> None:
        for handler in self.listeners.get(event, []):
            handler(arg)

    @property
    def context(self) -> Any:
        # dump_a11y reads the AX tree via a CDP session (page.accessibility
        # was removed in Playwright 1.61), so the fake exposes that shape.
        page = self

        class _Context:
            def new_cdp_session(self, target: Any) -> Any:
                class _CdpSession:
                    def send(self, method: str) -> Any:
                        assert method == "Accessibility.getFullAXTree"
                        return page.a11y_snapshot

                return _CdpSession()

        return _Context()


class TestConsoleCapture:
    def test_collects_page_and_console_errors_separately(self) -> None:
        page = _FakePage()
        capture = capture_console(cast("Page", page))

        page.emit("pageerror", ValueError("boom"))
        page.emit("console", _FakeConsoleMessage("error", "api failed"))
        page.emit("console", _FakeConsoleMessage("warning", "deprecated"))

        assert capture.page_errors == ["boom"]
        assert capture.console_errors == ["api failed"]
        assert capture.console_warnings == ["deprecated"]

    def test_assert_no_page_errors_passes_with_allow_filter(self) -> None:
        page = _FakePage()
        capture = capture_console(cast("Page", page))
        page.emit("pageerror", Exception("ResizeObserver loop limit exceeded"))

        capture.assert_no_page_errors(allow=("ResizeObserver",))  # not raised

        with pytest.raises(AssertionError, match="ResizeObserver"):
            capture.assert_no_page_errors()

    def test_assert_no_console_errors_empty_by_default(self) -> None:
        capture = capture_console(cast("Page", _FakePage()))
        capture.assert_no_console_errors()  # not raised


class TestNetworkCapture:
    def test_records_api_failures_with_status(self) -> None:
        page = _FakePage()
        capture = capture_network(cast("Page", page))

        request = _FakeRequest("POST", "http://localhost:8000/api/v1/writing/generate")
        page.emit("response", _FakeResponse(request, request.url, 422))

        assert capture.api_failures == ["POST http://localhost:8000/api/v1/writing/generate → 422"]

    def test_ignores_successful_and_non_api_responses(self) -> None:
        page = _FakePage()
        capture = capture_network(cast("Page", page))

        ok = _FakeRequest("GET", "http://localhost:8000/api/v1/novels")
        page.emit("response", _FakeResponse(ok, ok.url, 200))
        static = _FakeRequest("GET", "http://localhost:3000/_next/static/app.js")
        page.emit("response", _FakeResponse(static, static.url, 500))

        assert capture.api_failures == []

    def test_provider_calls_flagged_for_every_known_host(self) -> None:
        page = _FakePage()
        capture = capture_network(cast("Page", page))

        for host in PROVIDER_HOSTS:
            page.emit("request", _FakeRequest("POST", f"https://{host}/v1/messages"))

        assert len(capture.provider_calls) == len(PROVIDER_HOSTS)
        with pytest.raises(AssertionError, match="real LLM provider"):
            capture.assert_no_provider_calls()

    def test_assert_no_api_failures_with_allowed_status(self) -> None:
        page = _FakePage()
        capture = capture_network(cast("Page", page))

        request = _FakeRequest("GET", "http://localhost:8000/api/v1/health")
        page.emit("response", _FakeResponse(request, request.url, 503))

        capture.assert_no_api_failures(allow_statuses=(503,))  # not raised
        with pytest.raises(AssertionError, match="503"):
            capture.assert_no_api_failures()


class TestDumpA11y:
    def test_writes_snapshot_json(self, tmp_path: Path) -> None:
        page = _FakePage()
        page.a11y_snapshot = {"role": "WebArea", "children": [{"role": "heading"}]}

        out = dump_a11y(cast("Page", page), tmp_path / "a11y" / "login.json")

        assert out.exists()
        assert json.loads(out.read_text(encoding="utf-8"))["role"] == "WebArea"
