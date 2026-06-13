"""Unit tests for ``narrare._app.dependencies_auth`` — JWT validation.

Tests the ``get_current_user_id`` dependency with fake credentials and
patched ``verify_access_token`` so no real JWT decoding is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from fastapi import HTTPException

import narrare._app.dependencies_auth as auth_mod

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials

    from narrare._app.config import Settings

# ---------------------------------------------------------------------------
# Fake objects
# ---------------------------------------------------------------------------


class _FakeCredentials:
    """Stand-in for ``HTTPAuthorizationCredentials``."""

    def __init__(self, token: str = "some-token") -> None:
        self.credentials = token
        self.scheme = "Bearer"


class _FakeSettings:
    """Minimal settings with just ``secret_key``."""

    def __init__(self, secret_key: str = "a" * 32) -> None:
        self.secret_key = secret_key


def _creds(token: str = "some-token") -> Any:
    """Build fake credentials cast for type compatibility."""
    return cast("HTTPAuthorizationCredentials | None", _FakeCredentials(token))


def _settings() -> Any:
    """Build fake settings cast for type compatibility."""
    return cast("Settings", _FakeSettings())


# ---------------------------------------------------------------------------
# get_current_user_id
# ---------------------------------------------------------------------------


class TestGetCurrentUserId:
    async def test_returns_user_id_for_valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "narrare.auth.security.verify_access_token",
            lambda _token, _key: {"sub": "user-abc"},
        )

        result = await auth_mod.get_current_user_id(_creds("ok"), _settings())

        assert result == "user-abc"

    async def test_raises_401_when_no_credentials(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.get_current_user_id(None, _settings())

        assert exc_info.value.status_code == 401

    async def test_raises_401_when_token_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "narrare.auth.security.verify_access_token",
            lambda _token, _key: None,
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.get_current_user_id(_creds("bad"), _settings())

        assert exc_info.value.status_code == 401
        headers = exc_info.value.headers or {}
        assert headers["WWW-Authenticate"] == "Bearer"
