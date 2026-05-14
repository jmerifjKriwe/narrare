"""Unit tests for auth/cookie_helpers.py — httpOnly refresh cookie logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from narrare.auth.cookie_helpers import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    clear_refresh_cookie,
    set_refresh_cookie,
)


class _DevSettings:
    """Minimal settings stub for development."""

    refresh_token_expire_days = 30
    is_production = False


class _ProdSettings:
    """Minimal settings stub for production."""

    refresh_token_expire_days = 7
    is_production = True


@pytest.fixture
def mock_response() -> MagicMock:
    from fastapi import Response

    return MagicMock(spec=Response)


class TestSetRefreshCookie:
    def test_sets_cookie_with_correct_name(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "token-abc", _DevSettings())  # type: ignore[arg-type]
        mock_response.set_cookie.assert_called_once()
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["key"] == REFRESH_COOKIE_NAME
        assert kwargs["value"] == "token-abc"

    def test_sets_httponly(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "tok", _DevSettings())  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["httponly"] is True

    def test_sets_samesite_lax(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "tok", _DevSettings())  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["samesite"] == "lax"

    def test_sets_path_to_auth_endpoints(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "tok", _DevSettings())  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["path"] == REFRESH_COOKIE_PATH

    def test_max_age_matches_expire_days(self, mock_response: MagicMock) -> None:
        settings = _DevSettings()  # 30 days
        set_refresh_cookie(mock_response, "tok", settings)  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["max_age"] == 30 * 86400  # 30 days in seconds

    def test_max_age_respects_custom_expire_days(self, mock_response: MagicMock) -> None:
        settings = _ProdSettings()  # 7 days
        set_refresh_cookie(mock_response, "tok", settings)  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["max_age"] == 7 * 86400

    def test_secure_false_in_development(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "tok", _DevSettings())  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["secure"] is False

    def test_secure_true_in_production(self, mock_response: MagicMock) -> None:
        set_refresh_cookie(mock_response, "tok", _ProdSettings())  # type: ignore[arg-type]
        kwargs = mock_response.set_cookie.call_args[1]
        assert kwargs["secure"] is True


class TestClearRefreshCookie:
    def test_deletes_cookie_with_correct_name(self, mock_response: MagicMock) -> None:
        clear_refresh_cookie(mock_response)
        mock_response.delete_cookie.assert_called_once()
        kwargs = mock_response.delete_cookie.call_args[1]
        assert kwargs["key"] == REFRESH_COOKIE_NAME

    def test_deletes_cookie_with_correct_path(self, mock_response: MagicMock) -> None:
        clear_refresh_cookie(mock_response)
        kwargs = mock_response.delete_cookie.call_args[1]
        assert kwargs["path"] == REFRESH_COOKIE_PATH
