"""AI-writing E2E specs — WS interactive session (WRITE-005) + N08 pin.

Full-flow pin (audit-verified wire sequence, driven through the REAL UI):
ticket → WS connect → greeting → user_direction → text_chunk* → text_done
(with usage) → Add to Draft → save_to_chapter → end_session → clean close.
TestModel powers the turn (spec §3 layer 1).

HONEST-SPEC ADAPTATION (audit N09 draft gating, live-proven via frame dump):
the save leg pins what the UI really does — the "Draft saved to chapter!"
toast is UNREACHABLE from the interactive_session UI path. The server fills
its prose buffer only via a ``user_feedback accept`` frame (no FE component
sends one) or the interview-mode ``generate_draft`` auto-append
(_ws_draft_dispatch); the direction turn never appends. "Add to Draft" is
local-only FE state, and ``handle_save`` ignores the frame's text payload —
so Save always yields ``{"type": "error", "message": "Prose buffer is
empty — nothing to save."}``. Pinned verbatim: UI gating (N09), the error
frame, and the clean end.

N08 pin (spec §8, FIXED by Task 5 — PO ruling 2): the WS origin gate now
honors ENVIRONMENT=test exactly like REST CSRF. Pinned GREEN here: a
ticketed connect from a non-allowlisted origin reaches the greeting under
the runner's test mode. The production-settings rejection is unit-pinned
in Task 5 (tests/unit/api/writing/test_ws_origin.py + the route-level
rejection test) — the E2E runner boots one API, under test mode only.

RATE-LIMIT COUPLING (documented, not worked around): AI_WS_LIMITER is a
SHARED 3-connects/minute bucket per API process (SelfPruningLimiter builds
ONE InMemoryBucket via SingleBucketFactory — the per user+chapter key never
reaches a bucket), so this module (2 connects) must not run within the same
sliding minute as other WS-connecting traffic (e.g. the ADR-084 gate's 2
connects) — the 4th connect is rejected with a "Rate limited" error frame
before session resolution. A rejection frame names its gate ("Origin not
allowed" vs "Rate limited"), so a rate-limit hit cannot be mistaken for an
N08 regression.

Runtime budget: ≤ 90 s. Markers: e2e.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import API_URL, BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard
from tests.e2e.helpers.probes import capture_network
from tests.e2e.helpers.ws_probe import WritingSocketTracker

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page

# The N08 raw client connects DIRECTLY to the API (no Next.js proxy) —
# config.API_URL is the single source of truth for that origin
# (tests/e2e/config.py), swapped to the ws:// scheme for the handshake.
WS_API_ORIGIN = API_URL.replace("https://", "wss://").replace("http://", "ws://")


def _wait_until(page: Page, predicate, *, timeout_s: float, description: str) -> None:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"Timed out after {timeout_s}s waiting for: {description}")


@pytest.fixture(scope="module")
def ws_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    ws_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    """``api_request`` carrying the module user's bearer token (suite pattern)."""
    return make_authed_request(api_request, ws_novel)


@pytest.mark.e2e
class TestWsSessionFullFlow:
    def test_direction_turn_usage_save_and_clean_end(
        self, ws_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ws_novel.page
        tracker = WritingSocketTracker(page)
        network = capture_network(page)

        prepare_ai_chapter(page, authed_request, ws_novel.novel_id, title="WS Flow Chapter")

        # Open the session through the generation panel (WRITE-005 UI path).
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_role("button", name="Interactive", exact=True).click()
        page.get_by_role("button", name="Start Session", exact=True).click()

        _wait_until(
            page,
            lambda: len(tracker.sockets) >= 1,
            timeout_s=20,
            description="writing-session WebSocket to open",
        )
        _wait_until(
            page,
            lambda: "greeting" in tracker.frame_types(0),
            timeout_s=20,
            description="greeting frame",
        )
        page.locator('span[title="Connected"]').first.wait_for(state="visible", timeout=15_000)

        # One turn: user_direction → text_chunk* → text_done with usage.
        page.get_by_placeholder("Type your direction...").fill(
            "Elara bargains with the gatekeeper."
        )
        page.get_by_role("button", name="Send", exact=True).click()
        _wait_until(
            page,
            lambda: "user_direction" in tracker.sent_types(0),
            timeout_s=10,
            description="user_direction client frame",
        )
        _wait_until(
            page,
            lambda: "text_chunk" in tracker.frame_types(0),
            timeout_s=60,
            description="first text_chunk frame (TestModel turn)",
        )
        _wait_until(
            page,
            lambda: "text_done" in tracker.frame_types(0),
            timeout_s=60,
            description="text_done frame with usage",
        )
        done = next(json.loads(f) for f in tracker.sockets[0].frames if '"text_done"' in f)
        assert done.get("usage"), f"text_done must carry usage (N09-adjacent contract): {done}"

        # Draft-gated save (audit N09 reality): Save to Chapter is disabled
        # until a message is added to the draft.
        save_button = page.get_by_role("button", name="Save to Chapter")
        assert save_button.is_disabled(), "N09: save is draft-gated — pin current behavior"

        page.get_by_role("button", name="Add to Draft", exact=True).first.click()
        _wait_until(
            page,
            lambda: not save_button.is_disabled(),
            timeout_s=10,
            description="Save to Chapter enabled after Add to Draft",
        )
        save_button.click()

        # Honest-spec N09 pin (see module docstring): the save is draft-
        # creation-gated server-side — the interactive direction turn never
        # fills the server prose buffer (append_prose is reachable only via
        # a user_feedback frame no FE component sends, or interview-mode
        # generate_draft), so the REAL outcome is the error frame, not the
        # "Draft saved to chapter!" toast (live-proven: 'saved' never lands).
        _wait_until(
            page,
            lambda: "error" in tracker.frame_types(0),
            timeout_s=10,
            description="save error frame (empty server-side prose buffer)",
        )
        save_error = next(json.loads(f) for f in tracker.sockets[0].frames if '"error"' in f)
        assert "Prose buffer is empty" in str(save_error.get("message", "")), (
            f"N09: expected the draft-gating error frame, got: {save_error}"
        )

        # Clean end: end_session client frame → server closes the socket.
        page.get_by_role("button", name="End Session", exact=True).click()
        _wait_until(
            page,
            lambda: "end_session" in tracker.sent_types(0),
            timeout_s=10,
            description="end_session client frame",
        )
        _wait_until(
            page,
            lambda: tracker.sockets[0].raw.is_closed(),
            timeout_s=10,
            description="writing-session WebSocket closed",
        )
        network.assert_no_provider_calls()


@pytest.mark.e2e
class TestWsOriginTestMode:
    def test_ws_origin_check_honors_test_mode(
        self, ws_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """N08 GREEN pin (fix = Task 5): under ENVIRONMENT=test the origin
        gate relaxes exactly like REST CSRF — a ticketed WS connect with
        Origin http://localhost:9999 (not in the allowlist) reaches the
        greeting. Production invariance (foreign origin still rejected
        outside test mode) is unit-pinned by Task 5's policy pins and the
        pre-existing route-level rejection test."""
        from websockets.sync.client import connect

        network = capture_network(ws_novel.page)
        chapter = prepare_ai_chapter(
            ws_novel.page, authed_request, ws_novel.novel_id, title="WS Origin Chapter"
        )

        ticket_resp = authed_request("POST", "/api/v1/auth/ws-ticket")
        assert ticket_resp.status_code == 200, ticket_resp.text[:200]
        # WsTicketResponse.token (narrare.auth.schemas) — the brief's mechanical
        # note: field name verified against the schema at write time.
        ticket = ticket_resp.json()["token"]

        ws_url = (
            f"{WS_API_ORIGIN}/api/v1/writing/sessions/{chapter['chapter_id']}"
            f"?token={ticket}&project_id={ws_novel.novel_id}"
        )
        with connect(ws_url, additional_headers={"Origin": "http://localhost:9999"}) as ws:
            first = json.loads(ws.recv(timeout=10))
        assert first.get("type") == "greeting", (
            f"N08: expected greeting, got the origin rejection frame: {first}"
        )
        network.assert_no_provider_calls()
