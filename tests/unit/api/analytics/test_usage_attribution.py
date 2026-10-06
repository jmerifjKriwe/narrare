"""Unit tests for usage attribution — STATS-002 / ADR-093 D3.

Covers the two attribution setters:

1. ``narrare.analytics.middleware.UsageAttributionMiddleware`` — pure ASGI
   middleware binding ``usage_novel_id`` from the ``/api/v1/novels/{uuid}``
   path prefix (http scope only; websocket/lifespan pass through untouched).
2. ``narrare._app.dependencies_auth.get_current_user_id`` — binds
   ``usage_user_id`` after successful JWT resolution.

Tests call the middleware directly with synthetic scopes and invoke the
dependency with patched ``verify_access_token`` (mirrors
``tests/unit/api/_app/test_dependencies_auth.py``) — no HTTP server needed.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from starlette.types import Message, Receive, Scope, Send

import narrare._app.dependencies_auth as auth_mod
from narrare_core.llm.usage_events import usage_novel_id, usage_user_id

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

ReceiveStub = Callable[[], Coroutine[Any, Any, Message]]
SendStub = Callable[[Message], Coroutine[Any, Any, None]]


def _noop_receive() -> ReceiveStub:
    async def receive() -> Message:
        raise AssertionError("receive must not be called by attribution middleware")

    return receive


def _noop_send() -> SendStub:
    async def send(message: Message) -> None:
        raise AssertionError("send must not be called by attribution middleware")

    return send


class _RecordingApp:
    """Downstream ASGI app capturing the ContextVar values it observes."""

    def __init__(self) -> None:
        self.observed_novel_id: UUID | None = None
        self.observed_user_id: UUID | None = None
        self.observed_scope: Scope | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.observed_scope = scope
        self.observed_novel_id = usage_novel_id.get()
        self.observed_user_id = usage_user_id.get()


async def _run_through_middleware(scope: Scope) -> _RecordingApp:
    """Push *scope* through the middleware and return the recording app."""
    from narrare.analytics.middleware import UsageAttributionMiddleware

    app = _RecordingApp()
    await UsageAttributionMiddleware(app)(scope, _noop_receive(), _noop_send())
    return app


# ---------------------------------------------------------------------------
# UsageAttributionMiddleware — http scope
# ---------------------------------------------------------------------------


class TestUsageAttributionMiddlewareHttp:
    async def test_novel_subpath_sets_novel_id(self) -> None:
        novel_id = uuid4()
        scope: Scope = {"type": "http", "path": f"/api/v1/novels/{novel_id}/chapters"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id == novel_id

    async def test_novel_path_without_suffix_sets_novel_id(self) -> None:
        novel_id = uuid4()
        scope: Scope = {"type": "http", "path": f"/api/v1/novels/{novel_id}"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id == novel_id

    async def test_non_novel_path_sets_none(self) -> None:
        stale_id = uuid4()
        usage_novel_id.set(stale_id)
        scope: Scope = {"type": "http", "path": "/api/v1/chapters"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id is None

    async def test_malformed_uuid_sets_none(self) -> None:
        stale_id = uuid4()
        usage_novel_id.set(stale_id)
        scope: Scope = {"type": "http", "path": "/api/v1/novels/not-a-uuid"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id is None

    async def test_uuid_with_trailing_junk_sets_none(self) -> None:
        novel_id = uuid4()
        usage_novel_id.set(novel_id)
        scope: Scope = {"type": "http", "path": f"/api/v1/novels/{novel_id}extra/chapters"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id is None

    async def test_uppercase_uuid_is_accepted(self) -> None:
        novel_id = uuid4()
        scope: Scope = {"type": "http", "path": f"/api/v1/novels/{str(novel_id).upper()}"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id == novel_id


# ---------------------------------------------------------------------------
# UsageAttributionMiddleware — non-http scopes pass through untouched
# ---------------------------------------------------------------------------


class TestUsageAttributionMiddlewareNonHttp:
    async def test_websocket_scope_passes_through_untouched(self) -> None:
        sentinel = uuid4()
        usage_novel_id.set(sentinel)
        scope: Scope = {
            "type": "websocket",
            "path": f"/api/v1/novels/{uuid4()}",
            "subprotocols": [],
            "headers": [],
        }

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id == sentinel

    async def test_lifespan_scope_passes_through_untouched(self) -> None:
        sentinel = uuid4()
        usage_novel_id.set(sentinel)
        scope: Scope = {"type": "lifespan"}

        app = await _run_through_middleware(scope)

        assert app.observed_novel_id == sentinel


# ---------------------------------------------------------------------------
# get_current_user_id — usage_user_id binding
# ---------------------------------------------------------------------------


class TestGetCurrentUserIdBindsUsageUser:
    async def test_resolves_user_and_binds_usage_user_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_id = uuid4()
        monkeypatch.setattr(
            "narrare.auth.security.verify_access_token",
            lambda _token, _key: {"sub": str(user_id)},
        )
        credentials = _fake_credentials("valid-token")

        result = await auth_mod.get_current_user_id(credentials, _fake_settings())

        assert result == str(user_id)
        assert usage_user_id.get() == user_id

    async def test_malformed_subject_leaves_usage_user_id_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        usage_user_id.set(None)
        monkeypatch.setattr(
            "narrare.auth.security.verify_access_token",
            lambda _token, _key: {"sub": "user-abc"},
        )
        credentials = _fake_credentials("valid-token")

        result = await auth_mod.get_current_user_id(credentials, _fake_settings())

        assert result == "user-abc"
        assert usage_user_id.get() is None

    async def test_missing_credentials_leave_usage_user_id_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sentinel = uuid4()
        usage_user_id.set(sentinel)
        monkeypatch.setattr(
            "narrare.auth.security.verify_access_token",
            lambda _token, _key: {"sub": str(uuid4())},
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.get_current_user_id(None, _fake_settings())

        assert exc_info.value.status_code == 401
        assert usage_user_id.get() == sentinel


# ---------------------------------------------------------------------------
# Fake dependency arguments (mirror test_dependencies_auth.py)
# ---------------------------------------------------------------------------


class _FakeCredentials:
    """Stand-in for ``HTTPAuthorizationCredentials``."""

    def __init__(self, token: str) -> None:
        self.credentials = token
        self.scheme = "Bearer"


class _FakeSettings:
    """Minimal settings with just ``secret_key``."""

    secret_key = "a" * 32


def _fake_credentials(token: str) -> Any:
    return cast("HTTPAuthorizationCredentials", _FakeCredentials(token))


def _fake_settings() -> Any:
    return cast("Any", _FakeSettings())
