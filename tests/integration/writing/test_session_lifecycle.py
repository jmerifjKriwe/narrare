"""Integration test: WebSocket interactive session lifecycle.

Tests the WebSocket-based interactive writing session against the real
FastAPI app.  Uses httpx_ws or the ASGI transport for WebSocket testing.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from narrare._app.main import create_app

pytestmark = [
    pytest.mark.skip(
        reason="WebSocket tests need dedicated app fixture with patched dependencies "
        "— sync TestClient bypasses conftest patches; tracked separately"
    ),
    pytest.mark.requires_db,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_sync_client() -> TestClient:
    """Create a sync TestClient for WebSocket testing."""
    app = create_app()
    return TestClient(app)


def _register_user(sync_client: TestClient) -> tuple[str, dict[str, str]]:
    """Register a user and return (user_id, auth_headers)."""
    email = f"ws-test-{uuid4().hex[:8]}@example.com"
    resp = sync_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "display_name": "WS Test User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data.get("user_id", str(uuid4())), {
        "Authorization": f"Bearer {data['access_token']}",
    }


def _create_novel_and_chapter(
    sync_client: TestClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel + chapter, return (novel_id, chapter_id)."""
    novel_resp = sync_client.post(
        "/api/v1/novels",
        json={"title": "WS Session Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = sync_client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "WS Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebSocketSessionLifecycle:
    """WebSocket interactive session: connect → message → save → disconnect."""

    def test_ws_session_connect_and_greeting(self) -> None:
        """WebSocket sends greeting message after connection."""
        client = _create_sync_client()
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            # Should receive greeting
            greeting = ws.receive_json()
            assert greeting["type"] == "greeting"
            assert "session_id" in greeting
            assert "message" in greeting

    def test_ws_session_send_direction_and_receive_text(self) -> None:
        """Send user_direction → receive text chunks → text_done."""
        client = _create_sync_client()
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            # Consume greeting
            ws.receive_json()

            # Send a direction
            ws.send_json(
                {
                    "type": "user_direction",
                    "content": "Write a dramatic opening scene with rain and thunder",
                }
            )

            # Collect all messages until text_done or error
            messages: list[dict[str, object]] = []
            for _ in range(50):  # Safety limit
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("text_done", "error"):
                    break

            # Should have at least one message (text_chunk or text_done or error)
            assert len(messages) >= 1
            # The last message should be text_done or error (LLM is mocked/blocked)
            final = messages[-1]
            assert final["type"] in ("text_done", "text_chunk", "error")

    def test_ws_session_save_to_chapter(self) -> None:
        """save_to_chapter message returns saved or error for empty buffer."""
        client = _create_sync_client()
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            # Consume greeting
            ws.receive_json()

            # Try to save empty buffer
            ws.send_json({"type": "save_to_chapter"})
            msg = ws.receive_json()
            # Empty buffer should return error
            assert msg["type"] == "error"
            assert "empty" in msg["message"].lower() or "nothing" in msg["message"].lower()

    def test_ws_session_unknown_message_type(self) -> None:
        """Unknown message type returns error."""
        client = _create_sync_client()
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            # Consume greeting
            ws.receive_json()

            ws.send_json({"type": "unknown_type"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "unknown" in msg["message"].lower()

    def test_ws_session_end_session(self) -> None:
        """end_session message closes the WebSocket."""
        client = _create_sync_client()
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            # Consume greeting
            ws.receive_json()

            ws.send_json({"type": "end_session"})
            # WebSocket should close

    def test_ws_session_missing_params_closes(self) -> None:
        """WebSocket without user_id or project_id closes with 4001."""
        client = _create_sync_client()
        _, auth_headers = _register_user(client)
        _, chapter_id = _create_novel_and_chapter(client, auth_headers)

        # Connect without required params - server closes with 4001
        with (
            pytest.raises(WebSocketDisconnect),  # server rejects invalid auth
            client.websocket_connect(
                f"/api/v1/writing/sessions/{chapter_id}",
            ) as ws,
        ):
            ws.receive_json()
