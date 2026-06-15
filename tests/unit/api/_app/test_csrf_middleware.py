"""Unit tests for CSRF Origin/Referer validation (AUFG-05-13).

Tests T1-T8 covering the OriginValidationMiddleware and WebSocket origin check.

Test matrix:
  T1 — Same-origin POST with valid Origin → 200
  T2 — Cross-origin POST without Bearer → 403 (CSRF_ORIGIN_MISMATCH)
  T3 — POST with Bearer but no Origin → 200 (programmatic client)
  T4 — POST without Origin AND without Bearer → 403
  T5 — GET request (safe method) → 200 regardless of Origin
  T6 — WebSocket with matching Origin → accepted
  T7 — WebSocket with non-matching Origin → 4001 close
  T8 — WebSocket without Origin → accepted (CLI compat)
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from narrare._app.middleware import OriginValidationMiddleware
from narrare.auth.security import create_access_token

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------
TRUSTED_ORIGINS = ["http://localhost:3000"]


def _valid_token() -> str:
    """Create a valid JWT for testing."""
    from narrare._app.config import get_settings

    settings = get_settings()
    return create_access_token(
        subject="test-user",
        secret_key=settings.secret_key,
    )


# ---------------------------------------------------------------------------
# Minimal route handlers for testing
# ---------------------------------------------------------------------------


async def _post_ok(_: object) -> JSONResponse:
    """POST handler that returns 200."""
    return JSONResponse({"status": "ok"})


async def _get_ok(_: object) -> PlainTextResponse:
    """GET handler that returns 200."""
    return PlainTextResponse("ok")


async def _ws_echo(websocket: WebSocket) -> None:
    """WebSocket handler with origin check (same pattern as router_sessions.py).

    Follows the same validation pattern: accept first (for consistent error
    delivery), send error, close on rejection.
    """
    from narrare._app.config import get_settings

    settings = get_settings()
    trusted = settings.csrf_trusted_origins
    origin = websocket.headers.get("origin", "")

    if origin and origin not in trusted:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Origin not allowed",
            }
        )
        await websocket.close(code=4001, reason="Origin not allowed")
        return

    await websocket.accept()
    await websocket.send_json({"type": "hello"})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _make_app() -> Starlette:
    """Create a minimal Starlette app with OriginValidationMiddleware."""
    app = Starlette(
        routes=[
            WebSocketRoute("/ws", _ws_echo),
        ],
    )
    app.add_middleware(
        OriginValidationMiddleware,
        trusted_origins=TRUSTED_ORIGINS,
    )
    app.add_route("/test", _post_ok, methods=["POST"])
    app.add_route("/safe", _get_ok, methods=["GET"])
    return app


# ===================================================================
# T1 — Same-origin POST with valid Origin → 200
# ===================================================================


def test_same_origin_post_allowed() -> None:
    """T1: POST with matching Origin header is allowed through."""
    client = TestClient(_make_app())
    response = client.post("/test", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200


# ===================================================================
# T2 — Cross-origin POST without Bearer → 403
# ===================================================================


def test_cross_origin_post_rejected() -> None:
    """T2: POST with non-matching Origin and no Bearer returns 403."""
    client = TestClient(_make_app())
    response = client.post("/test", headers={"Origin": "https://evil.com"})
    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "CSRF_ORIGIN_MISMATCH"
    assert data["detail"] == "Origin not allowed"


# ===================================================================
# T3 — POST with Bearer but no Origin → 200 (programmatic client)
# ===================================================================


def test_post_with_bearer_no_origin_allowed() -> None:
    """T3: POST with valid Bearer token and no Origin header is allowed."""
    token = _valid_token()
    client = TestClient(_make_app())
    response = client.post("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


# ===================================================================
# T4 — POST without Origin AND without Bearer → 403
# ===================================================================


def test_post_no_origin_no_bearer_rejected() -> None:
    """T4: POST without Origin and without Bearer is rejected."""
    client = TestClient(_make_app())
    response = client.post("/test")
    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "CSRF_ORIGIN_MISMATCH"


# ===================================================================
# T5 — GET request (safe method) → 200 regardless of Origin
# ===================================================================


def test_safe_method_with_evil_origin_allowed() -> None:
    """T5: GET with any Origin is allowed (safe methods exempt)."""
    client = TestClient(_make_app())
    response = client.get("/safe", headers={"Origin": "https://evil.com"})
    assert response.status_code == 200


# ===================================================================
# T6 — WebSocket with matching Origin → accepted
# ===================================================================


def test_websocket_matching_origin_allowed() -> None:
    """T6: WebSocket with matching Origin connects successfully."""
    client = TestClient(_make_app())
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as ws:
        data = ws.receive_json()
        assert data["type"] == "hello"


# ===================================================================
# T7 — WebSocket with non-matching Origin → 4001 close
# ===================================================================


def test_websocket_non_matching_origin_rejected() -> None:
    """T7: WebSocket with non-matching Origin returns error then closes."""
    client = TestClient(_make_app())
    with client.websocket_connect("/ws", headers={"Origin": "https://evil.com"}) as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert data["message"] == "Origin not allowed"
        # Next receive should raise disconnect with code 4001
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4001


# ===================================================================
# T8 — WebSocket without Origin → accepted (CLI compat)
# ===================================================================


def test_websocket_no_origin_allowed() -> None:
    """T8: WebSocket without Origin header connects (CLI/programmatic compat)."""
    client = TestClient(_make_app())
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "hello"


# ===================================================================
# Additional — Referer fallback tests
# ===================================================================


def test_post_with_referer_fallback_allowed() -> None:
    """POST with matching Referer (no Origin) is allowed."""
    client = TestClient(_make_app())
    response = client.post(
        "/test",
        headers={"Referer": "http://localhost:3000/writing/abc"},
    )
    assert response.status_code == 200


def test_post_with_referer_fallback_rejected() -> None:
    """POST with non-matching Referer (no Origin) is rejected."""
    client = TestClient(_make_app())
    response = client.post(
        "/test",
        headers={"Referer": "https://evil.com/page"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "CSRF_ORIGIN_MISMATCH"


def test_post_with_invalid_bearer_no_origin_rejected() -> None:
    """POST with invalid Bearer and no Origin is rejected."""
    client = TestClient(_make_app())
    response = client.post(
        "/test",
        headers={"Authorization": "Bearer invalidtoken123"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "CSRF_ORIGIN_MISMATCH"


def test_post_with_origin_and_referer_origin_takes_precedence() -> None:
    """When both Origin and Referer present, Origin is checked first."""
    client = TestClient(_make_app())
    # Origin matches, Referer doesn't → allowed (Origin takes precedence)
    response = client.post(
        "/test",
        headers={
            "Origin": "http://localhost:3000",
            "Referer": "https://evil.com/page",
        },
    )
    assert response.status_code == 200
