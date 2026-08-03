"""Regression tests for the E2E direct-HTTP helper.

Guards the CSRF-fragility fix (AUFG-05-13): E2E fixtures/helpers that make
direct API calls must send a browser-like ``Origin`` header so the
``OriginValidationMiddleware`` accepts state-changing requests outside CI's
``is_test`` CSRF bypass. Without these, calls silently break locally
(development) but pass in CI (``is_test=True`` disables CSRF).

These are UNIT tests of the test-infra helper — they run WITHOUT a live API
by mounting a recording adapter on the session and inspecting the prepared
request headers. They are NOT E2E tests.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter

from tests.e2e.http_session import build_api_session

E2E_ORIGIN = "http://localhost:3000"


class _RecordingAdapter(HTTPAdapter):
    """An adapter that records the last PreparedRequest instead of using the network."""

    def __init__(self) -> None:
        super().__init__()
        self.last_request: requests.PreparedRequest | None = None

    def send(  # type: ignore[override]
        self, request: requests.PreparedRequest, **_kwargs: Any
    ) -> requests.Response:
        """Record the outgoing request and return a canned 200 response."""
        self.last_request = request
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        response.url = request.url or ""
        response.request = request
        return response


def _session_with_recorder(origin: str) -> tuple[requests.Session, _RecordingAdapter]:
    """Build a browser-mimic session whose network calls are captured."""
    session = build_api_session(origin)
    recorder = _RecordingAdapter()
    session.mount("http://", recorder)
    session.mount("https://", recorder)
    return session, recorder


def test_build_api_session_sets_browser_origin_headers() -> None:
    """The session must default to a browser-like Origin/Referer."""
    session = build_api_session(E2E_ORIGIN)

    assert session.headers["Origin"] == E2E_ORIGIN
    assert session.headers["Referer"] == f"{E2E_ORIGIN}/"


def test_api_session_sends_origin_on_state_changing_request() -> None:
    """POST requests must carry the Origin header so CSRF validation passes."""
    session, recorder = _session_with_recorder(E2E_ORIGIN)

    session.post(f"{E2E_ORIGIN}/api/v1/auth/register", json={"email": "x"})

    assert recorder.last_request is not None
    assert recorder.last_request.headers["Origin"] == E2E_ORIGIN


def test_api_session_origin_survives_extra_call_headers() -> None:
    """Origin must survive even when callers pass per-call headers.

    This is the key regression guard. ``requests`` MERGES session defaults
    with per-call ``headers=``; if a future refactor dropped the session
    default or clobbered it, Origin would vanish and CSRF would silently
    break again (locally only — invisible in CI).
    """
    session, recorder = _session_with_recorder(E2E_ORIGIN)

    session.post(
        f"{E2E_ORIGIN}/api/v1/novels/x/chapters",
        json={"title": "T"},
        headers={
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    assert recorder.last_request is not None
    headers = recorder.last_request.headers
    assert headers["Origin"] == E2E_ORIGIN, "Origin header lost — CSRF would reject this"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Content-Type"] == "application/json"
