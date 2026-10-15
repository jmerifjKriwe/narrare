"""ADR-084 acceptance-gate E2E — WS ticket authentication for writing sessions.

Exercises the full browser ticket flow against the real stack
(ENVIRONMENT=test, NARRARE_E2E_TEST=1 → TestModel for all LLM providers):

  connect   → the frontend mints a ticket via POST /api/v1/auth/ws-ticket and
              opens ws://{host}/api/v1/writing/sessions/{chapterId}?token=…
              (identity is server-derived; the old user_id param is gone).
  session   → the server greets with a session_id (session active).
  recovery  → force-closing the raw socket makes the frontend reconnect with a
              FRESH single-use ticket and resume the same session
              (recover_session → session_recovered, ADR-052 semantics on top
              of ADR-084 identity).

The WebSocket upgrade itself is NOT interceptable by page.route() — it goes
through the Next.js rewrite on :3000 to the API on :8000 (empirically verified
as part of the ADR-084 acceptance gate: Next 16.3.1 rewrites DO proxy WS
upgrades). Assertions therefore observe the real network via page.on(
"websocket") frame events plus a window.WebSocket recorder used only to
force-close the underlying socket (simulated connection loss).

The WS tracker now lives in helpers/ws_probe.py (shared with the WRITE-005
spec, Task 11) — imported below under its original private name so this
gate's body stays untouched.

Follows the house patterns of tests/e2e/test_editor_autosave.py and
tests/e2e/test_helpers_wizard.py.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

from tests.e2e.helpers.ws_probe import WritingSocketTracker as _WritingSocketTracker
from tests.e2e.test_helpers_wizard import _complete_wizard_to_editor

if TYPE_CHECKING:
    from playwright.sync_api import Page

WS_TICKET_PATH = "/api/v1/auth/ws-ticket"

# Injected before any navigation: records every WebSocket the page creates so
# the test can close the writing-session socket directly (bypassing the app's
# WritingSessionSocket wrapper, which would suppress reconnection on close()).
_RAW_WS_RECORDER = """
window.__narrareRawSockets = [];
const __NarrareOrigWS = window.WebSocket;
window.WebSocket = class extends __NarrareOrigWS {
  constructor(...args) {
    super(...args);
    window.__narrareRawSockets.push(this);
  }
};
"""


def _wait_until(page: Page, predicate, *, timeout_s: float, description: str) -> None:
    """Poll ``predicate`` until true or fail with ``description``."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"Timed out after {timeout_s}s waiting for: {description}")


def _token_from_url(url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(url).query).get("token", [""])[0]


@pytest.mark.e2e
class TestWsTicketSession:
    """ADR-084 acceptance gate: ticket-authenticated writing session over WS."""

    def test_ws_ticket_session_connect_active_and_recovery(
        self,
        page: Page,
        base_url: str,
        api_request,
        register_unique_user,
    ) -> None:
        """connect → session active → forced disconnect → ticket-refresh recovery."""
        # Record raw sockets BEFORE any navigation so the app's WebSocket
        # instances are captured from the very first page load.
        page.add_init_script(_RAW_WS_RECORDER)

        tracker = _WritingSocketTracker(page)
        ticket_posts: list[str] = []
        ticket_statuses: list[int] = []
        page.on(
            "request",
            lambda req: (
                ticket_posts.append(req.url)
                if req.method == "POST" and WS_TICKET_PATH in req.url
                else None
            ),
        )
        page.on(
            "response",
            lambda resp: (
                ticket_statuses.append(resp.status) if WS_TICKET_PATH in resp.url else None
            ),
        )

        # --- Wizard → novel editor (established house pattern) -------------
        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        novel_id = result["novel_id"]
        access_token = result["access_token"]
        assert "/novel/" in page.url, f"Expected novel editor URL, got {page.url}"

        # --- Ensure a chapter exists (blank starter creates none) ----------
        chapters_resp = api_request(
            "GET",
            f"/api/v1/novels/{novel_id}/chapters",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert chapters_resp.status_code == 200, chapters_resp.text[:200]
        chapters = chapters_resp.json()
        if not chapters:
            created = api_request(
                "POST",
                f"/api/v1/novels/{novel_id}/chapters",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"title": "Chapter 1"},
            )
            assert created.status_code == 201, created.text[:200]
            page.reload()
        page.wait_for_timeout(1500)  # let the sidebar select the first chapter

        editor = page.locator(".ProseMirror, [contenteditable='true']").first
        if not editor.is_visible():
            # Defensive: click the first chapter in the sidebar (autosave
            # pattern) — the sidebar normally auto-selects it.
            page.locator(".space-y-1 button").first.click()
            page.wait_for_timeout(1000)
        editor.wait_for(state="visible", timeout=10000)

        # --- Start an interactive writing session (WRITE-005 UI) -----------
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_role("button", name="Interactive", exact=True).click()
        page.get_by_role("button", name="Start Session", exact=True).click()

        # --- CONNECT: ticket mint + WS with token= (never user_id=) --------
        _wait_until(
            page,
            lambda: len(ticket_posts) >= 1,
            timeout_s=15,
            description="POST /api/v1/auth/ws-ticket after Start Session",
        )
        _wait_until(
            page,
            lambda: len(ticket_statuses) >= 1,
            timeout_s=10,
            description="ws-ticket mint response",
        )
        assert ticket_statuses[0] == 200, f"ws-ticket mint failed: statuses={ticket_statuses}"

        _wait_until(
            page,
            lambda: len(tracker.sockets) >= 1,
            timeout_s=15,
            description="writing-session WebSocket to open",
        )
        ws1_url = tracker.urls[0]
        assert "token=" in ws1_url, f"WS URL must carry a ticket token: {ws1_url}"
        assert "user_id=" not in ws1_url, (
            f"ADR-084: client-asserted user_id must be gone from the URL: {ws1_url}"
        )
        token1 = _token_from_url(ws1_url)
        assert token1, f"token query param empty in WS URL: {ws1_url}"

        # --- SESSION ACTIVE: greeting frame with session_id ----------------
        _wait_until(
            page,
            lambda: "greeting" in tracker.frame_types(0),
            timeout_s=15,
            description="greeting frame on first writing-session socket",
        )
        greeting = json.loads(tracker.sockets[0].frames[0])
        session_id = greeting.get("session_id")
        assert session_id, f"greeting frame missing session_id: {greeting}"

        # Secondary DOM check — SessionHeader status dot reports Connected.
        page.locator('span[title="Connected"]').first.wait_for(state="visible", timeout=10000)

        # --- RECOVERY: force-close the raw socket (connection loss) --------
        # Closing the RAW WebSocket bypasses WritingSessionSocket.close()
        # (which forbids reconnection) — the wrapper sees a server/network
        # close and schedules a reconnect with a FRESH single-use ticket.
        closed_url = page.evaluate(
            """
            () => {
              const sockets = window.__narrareRawSockets || [];
              const isWriting = (s) => s.url.includes('/api/v1/writing/sessions/');
              const target = sockets.filter(isWriting).pop();
              if (!target) return null;
              target.close();
              return target.url;
            }
            """
        )
        assert closed_url == ws1_url, (
            f"Closed unexpected socket: {closed_url!r} vs first writing WS {ws1_url!r}"
        )

        # Fresh ticket mint + second connection with a NEW token.
        _wait_until(
            page,
            lambda: len(ticket_posts) >= 2,
            timeout_s=15,
            description="second POST /api/v1/auth/ws-ticket for the reconnect",
        )
        _wait_until(
            page,
            lambda: len(ticket_statuses) >= 2,
            timeout_s=10,
            description="second ws-ticket mint response",
        )
        assert ticket_statuses[:2] == [200, 200], (
            f"ws-ticket mints not both 200: statuses={ticket_statuses}"
        )
        _wait_until(
            page,
            lambda: len(tracker.sockets) >= 2,
            timeout_s=20,
            description="reconnected writing-session WebSocket",
        )
        ws2_url = tracker.urls[1]
        token2 = _token_from_url(ws2_url)
        assert "user_id=" not in ws2_url, f"user_id leaked into reconnect URL: {ws2_url}"
        assert token2 and token2 != token1, (
            "Reconnect must present a FRESH single-use ticket "
            f"(token1={token1!r}, token2={token2!r})"
        )
        assert f"session_id={session_id}" in ws2_url, (
            f"Reconnect URL must carry the previous session id: {ws2_url}"
        )

        # The client asks to recover; the server resumes the SAME session.
        _wait_until(
            page,
            lambda: "recover_session" in tracker.sent_types(1),
            timeout_s=10,
            description="recover_session client frame on second socket",
        )
        _wait_until(
            page,
            lambda: "session_recovered" in tracker.frame_types(1),
            timeout_s=20,
            description="session_recovered server frame on second socket",
        )
        recovered = next(
            json.loads(f) for f in tracker.sockets[1].frames if '"session_recovered"' in f
        )
        assert recovered.get("session_id") == session_id, (
            f"Recovered session id mismatch: {recovered.get('session_id')} != {session_id}"
        )

        # Session is active again in the UI.
        page.locator('span[title="Connected"]').first.wait_for(state="visible", timeout=10000)
