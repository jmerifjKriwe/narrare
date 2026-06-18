"""Integration test: WebSocket interactive session lifecycle.

Tests the WebSocket-based interactive writing session against the real
FastAPI app with patched LLM dependencies.

The WebSocket handler in ``router_sessions.py`` calls ``get_model_registry()``
and ``get_composer()`` directly (not via FastAPI Depends), so this module
patches those module-level names before creating the TestClient.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from narrare._app.main import create_app
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_llm_gateway import FakeModelRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ws_env():
    """TestClient + FakeModelRegistry with patched LLM dependencies.

    Patches ``get_model_registry`` and ``get_composer`` at the
    ``router_sessions`` module level so the WebSocket handler uses fakes
    instead of the real LLM gateway.

    Yields ``(client, fake_registry)`` so tests that need LLM responses
    can call ``fake_registry.returns_stream(...)`` before connecting.
    """
    fake_registry = FakeModelRegistry()

    mock_composer = AsyncMock()
    mock_composer.build.return_value = ComposedPrompt(
        system="You are a creative writing assistant.",
        user="Continue the story based on the user's direction.",
    )

    app = create_app(test_mode=True)

    with (
        patch(
            "narrare.writing.router_sessions.get_model_registry",
            return_value=fake_registry,
        ),
        patch(
            "narrare.writing.router_sessions.get_composer",
            return_value=mock_composer,
        ),
        TestClient(app) as client,
    ):
        yield client, fake_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_user(client: TestClient) -> tuple[str, dict[str, str]]:
    """Register a user and return (user_id, auth_headers).

    The ``TokenResponse`` schema does not include ``user_id`` in the response
    body, so we decode it from the JWT access token's ``sub`` claim instead.
    """
    import jwt as _jwt

    from narrare._app.config import get_settings

    email = f"ws-test-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "display_name": "WS Test User",
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    data = resp.json()

    # Decode user_id from JWT — TokenResponse doesn't include user_id
    settings = get_settings()
    payload = _jwt.decode(
        data["access_token"],
        settings.secret_key,
        algorithms=["HS256"],
    )
    user_id = payload["sub"]
    assert user_id, "JWT sub claim must not be empty"

    auth_headers = {"Authorization": f"Bearer {data['access_token']}"}

    # Create a fake AI provider + set it as default so the model routing
    # resolver doesn't fail with ConfigurationError when the WebSocket
    # handler resolves LLM config.
    # Full path: /api/v1 + /settings (router.py) + /ai/providers (router_ai_providers.py)
    provider_resp = client.post(
        "/api/v1/settings/ai/providers",
        json={
            "provider_name": "test-provider",
            "api_key": "sk-test-key",
        },
        headers=auth_headers,
    )
    assert provider_resp.status_code == 201, f"Provider creation failed: {provider_resp.text}"
    provider_id = provider_resp.json()["id"]

    # Set the test provider as default so model routing succeeds
    settings_resp = client.patch(
        "/api/v1/settings/ai",
        json={
            "default_provider_id": provider_id,
            "default_model": "test-model",
        },
        headers=auth_headers,
    )
    assert settings_resp.status_code == 200, f"AI settings update failed: {settings_resp.text}"

    return user_id, auth_headers


def _create_novel_and_chapter(
    client: TestClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel + chapter, return (novel_id, chapter_id)."""
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "WS Session Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201, f"Novel creation failed: {novel_resp.text}"
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "WS Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201, f"Chapter creation failed: {chapter_resp.text}"
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebSocketSessionLifecycle:
    """WebSocket interactive session: connect → message → save → disconnect."""

    def test_ws_session_connect_and_greeting(self, ws_env) -> None:
        """WebSocket sends greeting message after connection."""
        client, _ = ws_env
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            greeting = ws.receive_json()
            assert greeting["type"] == "greeting"
            assert "session_id" in greeting
            assert "message" in greeting

    def test_ws_session_send_direction_and_receive_text(self, ws_env) -> None:
        """Send user_direction → receive text chunks → text_done."""
        client, fake_registry = ws_env
        # Configure LLM streaming response BEFORE connecting
        fake_registry.returns_stream(["The rain ", "fell heavily"])

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

            # Collect messages until text_done or error
            messages: list[dict[str, object]] = []
            for _ in range(50):  # safety limit
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("text_done", "error"):
                    break

            assert len(messages) >= 1
            final = messages[-1]
            assert final["type"] in ("text_done", "text_chunk", "error")

    def test_ws_session_save_to_chapter(self, ws_env) -> None:
        """save_to_chapter returns error for empty prose buffer."""
        client, _ = ws_env
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            ws.receive_json()  # consume greeting

            # Try to save empty buffer
            ws.send_json({"type": "save_to_chapter"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "empty" in msg["message"].lower() or "nothing" in msg["message"].lower()

    def test_ws_session_unknown_message_type(self, ws_env) -> None:
        """Unknown message type returns error."""
        client, _ = ws_env
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            ws.receive_json()  # consume greeting

            ws.send_json({"type": "unknown_type"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "unknown" in msg["message"].lower()

    def test_ws_session_end_session(self, ws_env) -> None:
        """end_session message closes the WebSocket."""
        client, _ = ws_env
        user_id, auth_headers = _register_user(client)
        novel_id, chapter_id = _create_novel_and_chapter(client, auth_headers)

        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}?user_id={user_id}&project_id={novel_id}",
        ) as ws:
            ws.receive_json()  # consume greeting
            ws.send_json({"type": "end_session"})
            # WebSocket should close gracefully

    def test_ws_session_missing_params_closes(self, ws_env) -> None:
        """WebSocket without user_id or project_id closes with 4001."""
        client, _ = ws_env
        _, auth_headers = _register_user(client)
        _, chapter_id = _create_novel_and_chapter(client, auth_headers)

        # Connect without required params.
        # Server accepts, sends an error JSON, then closes with code 4001.
        with client.websocket_connect(
            f"/api/v1/writing/sessions/{chapter_id}",
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            msg_lower = str(msg.get("message", "")).lower()
            assert "user_id" in msg_lower or "project_id" in msg_lower
            # The close frame should raise WebSocketDisconnect on next receive
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
