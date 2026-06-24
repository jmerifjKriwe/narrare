"""Validation-path unit tests for the writing-session WebSocket route.

Split from test_router_sessions_basic.py per RULE-04.

Covers: missing params, origin validation, rate limiting, and exception
safety (guard clauses before the success path).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare._app.config import Settings as AppSettings
from narrare.writing.router_sessions import interactive_session

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_websocket() -> MagicMock:
    """A mock WebSocket with standard headers for localhost origin."""
    from unittest.mock import AsyncMock

    ws = AsyncMock()
    ws.app = MagicMock(spec=["state"])
    ws.headers = {"origin": "http://localhost:3000"}
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


@pytest.fixture
def chapter_id() -> UUID:
    """A unique chapter UUID per test."""
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    """A unique project UUID per test."""
    return uuid4()


# ---------------------------------------------------------------------------
# Error path: Missing parameters
# ---------------------------------------------------------------------------


async def test_missing_user_id_returns_error(
    mock_websocket: MagicMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When user_id is an empty string, send error + close(4001)."""
    await interactive_session(
        mock_websocket,
        chapter_id,
        user_id="",
        project_id=project_id,
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4001,
        reason="Missing user_id or project_id",
    )


async def test_none_project_id_returns_error(
    mock_websocket: MagicMock,
    chapter_id: UUID,
) -> None:
    """When project_id is None, send error + close(4001)."""
    await interactive_session(
        mock_websocket,
        chapter_id,
        user_id="user123",
        project_id=None,
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4001,
        reason="Missing user_id or project_id",
    )


# ---------------------------------------------------------------------------
# Error path: Origin validation
# ---------------------------------------------------------------------------


async def test_untrusted_origin_returns_error(
    mock_websocket: MagicMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When origin is not in csrf_trusted_origins, send error + close(4001)."""
    mock_websocket.headers["origin"] = "http://evil.com"

    await interactive_session(
        mock_websocket,
        chapter_id,
        user_id="user123",
        project_id=project_id,
    )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4001,
        reason="Origin not allowed",
    )


async def test_empty_origin_is_allowed(
    mock_websocket: MagicMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When origin is empty (no header), the origin check is skipped.

    This is the behaviour specified by the code::
        if _origin and _origin not in _trusted:
    An empty origin is falsy so the guard is bypassed.

    We mock the rate limiter to return False so we can verify the
    empty origin *did* pass the origin check and reached the rate
    limit check.
    """
    mock_websocket.headers["origin"] = ""
    from narrare._app.rate_limits import AI_WS_LIMITER

    with patch.object(AI_WS_LIMITER, "try_acquire", return_value=False):
        await interactive_session(
            mock_websocket,
            chapter_id,
            user_id="user123",
            project_id=project_id,
        )

    # Should have hit the rate limiter (not origin rejection).
    # The function calls close(code=4003, reason="Rate limited").
    mock_websocket.accept.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4003,
        reason="Rate limited",
    )


# ---------------------------------------------------------------------------
# Error path: Rate limiting
# ---------------------------------------------------------------------------


async def test_rate_limited_returns_error(
    mock_websocket: MagicMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When rate limit is exceeded, send error + close(4003).

    Mocks ``AI_WS_LIMITER.try_acquire`` to return ``False`` (rate limit hit)
    so the guard clause fires. The underlying pyrate_limiter is not tested
    here — only the route's response to a rate-limit signal.
    """
    from narrare._app.rate_limits import AI_WS_LIMITER

    with patch.object(AI_WS_LIMITER, "try_acquire", return_value=False):
        await interactive_session(
            mock_websocket,
            chapter_id,
            user_id="user123",
            project_id=project_id,
        )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4003,
        reason="Rate limited",
    )


# ---------------------------------------------------------------------------
# Error path: Exception safety
# ---------------------------------------------------------------------------


async def test_origin_check_closes_on_empty_trusted_list(
    mock_websocket: MagicMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When csrf_trusted_origins is empty and origin is set, reject.

    Edge case: a misconfigured deployment that sets an empty list
    should reject all origins (defense-in-depth).
    """
    mock_websocket.headers["origin"] = "http://localhost:3000"

    with patch("narrare._app.config.get_settings") as mock_get_settings:
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = []
        mock_get_settings.return_value = mock_settings

        await interactive_session(
            mock_websocket,
            chapter_id,
            user_id="user123",
            project_id=project_id,
        )

    mock_websocket.accept.assert_awaited_once()
    mock_websocket.send_json.assert_awaited_once()
    mock_websocket.close.assert_awaited_once_with(
        code=4001,
        reason="Origin not allowed",
    )
