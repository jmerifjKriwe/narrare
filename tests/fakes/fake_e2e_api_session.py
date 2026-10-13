"""Browser-free double for a ``requests.Session`` as the e2e helpers use it.

Records every POST and replies with a canned response, so token-harvest
logic (``tests/e2e/helpers/audit_user.login_via_api``) is testable without
a live API. Fake-based per ADR-030 — recorded calls, not MagicMock.
"""

from __future__ import annotations


class FakeE2EResponse:
    """Minimal ``requests.Response`` stand-in: status + JSON payload + text."""

    def __init__(self, status_code: int, payload: dict[str, str], text: str) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict[str, str]:
        return self._payload


class FakeE2EApiSession:
    """Records POSTs; replies with the canned response."""

    def __init__(self, response: FakeE2EResponse) -> None:
        self.posts: list[tuple[str, dict[str, str]]] = []
        self._response = response

    def post(self, url: str, json: dict[str, str]) -> FakeE2EResponse:
        self.posts.append((url, json))
        return self._response
