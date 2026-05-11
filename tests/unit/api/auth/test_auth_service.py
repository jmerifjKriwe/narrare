"""Unit tests for auth/service.py — registration, login, token refresh."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from narrare.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from narrare.auth.service import AuthService
from tests.factories import make_user
from tests.fakes import FakeAuthRepository


@pytest.fixture
def fake_repo() -> FakeAuthRepository:
    return FakeAuthRepository()


class _FakeSettings:
    """Minimal settings object for AuthService."""

    secret_key = "test-secret-key-at-least-32-characters-long"
    access_token_expire_minutes = 60
    refresh_token_expire_days = 30


@pytest.fixture
def service(fake_repo: FakeAuthRepository) -> AuthService:
    svc = AuthService.__new__(AuthService)
    svc._repo = fake_repo
    svc._settings = _FakeSettings()  # type: ignore[assignment]
    return svc


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestAuthServiceRegister:
    async def test_register_with_new_email_returns_tokens(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]

        with patch("narrare.auth.service.hash_password", return_value="hashed_pw"):
            result = await service.register(
                RegisterRequest(email="new@example.com", password="secret123", display_name="New")
            )

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"

    async def test_register_with_existing_email_raises_409(self, service: AuthService) -> None:
        existing = make_user(email="taken@example.com")
        service._repo.seed(existing)  # type: ignore[attr-defined]

        with pytest.raises(HTTPException) as exc:
            await service.register(RegisterRequest(email="taken@example.com", password="secret123"))
        assert exc.value.status_code == 409
        assert "already registered" in exc.value.detail

    async def test_register_hashes_password_and_creates_user(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]

        with patch("narrare.auth.service.hash_password", return_value="hashed_pw") as mock_hash:
            await service.register(RegisterRequest(email="new@example.com", password="mypassword"))
            mock_hash.assert_called_once_with("mypassword")

        service._repo.assert_called_once("create")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestAuthServiceLogin:
    async def test_login_with_valid_credentials_returns_tokens(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]

        with patch("narrare.auth.service.verify_password", return_value=True):
            result = await service.login(
                LoginRequest(email="test@example.com", password="secret123")
            )

        assert isinstance(result, TokenResponse)
        assert result.access_token

    async def test_login_with_wrong_password_raises_401(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]

        with (
            patch("narrare.auth.service.verify_password", return_value=False),
            pytest.raises(HTTPException) as exc,
        ):
            await service.login(LoginRequest(email="test@example.com", password="wrong"))
        assert exc.value.status_code == 401

    async def test_login_with_unknown_email_raises_401(self, service: AuthService) -> None:
        with pytest.raises(HTTPException) as exc:
            await service.login(LoginRequest(email="nobody@example.com", password="secret"))
        assert exc.value.status_code == 401

    async def test_login_with_inactive_user_raises_401(self, service: AuthService) -> None:
        user = make_user(is_active=False)
        service._repo.seed(user)  # type: ignore[attr-defined]

        with (
            patch("narrare.auth.service.verify_password", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            await service.login(LoginRequest(email="test@example.com", password="secret"))
        assert exc.value.status_code == 401
        assert "disabled" in exc.value.detail


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


class TestAuthServiceRefresh:
    async def test_refresh_with_valid_token_returns_new_tokens(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]
        payload = {"sub": str(user.id), "type": "refresh"}

        with patch("narrare.auth.service.verify_refresh_token", return_value=payload):
            result = await service.refresh("valid-refresh-token")

        assert isinstance(result, TokenResponse)
        assert result.access_token

    async def test_refresh_with_invalid_token_raises_401(self, service: AuthService) -> None:
        with (
            patch("narrare.auth.service.verify_refresh_token", return_value=None),
            pytest.raises(HTTPException) as exc,
        ):
            await service.refresh("bad-token")
        assert exc.value.status_code == 401

    async def test_refresh_with_missing_sub_raises_401(self, service: AuthService) -> None:
        payload = {"type": "refresh"}  # no "sub"

        with (
            patch("narrare.auth.service.verify_refresh_token", return_value=payload),
            pytest.raises(HTTPException) as exc,
        ):
            await service.refresh("token-without-sub")
        assert exc.value.status_code == 401

    async def test_refresh_for_deleted_user_raises_401(self, service: AuthService) -> None:
        payload = {"sub": str(uuid.uuid4()), "type": "refresh"}

        with (
            patch("narrare.auth.service.verify_refresh_token", return_value=payload),
            pytest.raises(HTTPException) as exc,
        ):
            await service.refresh("valid-token")
        assert exc.value.status_code == 401

    async def test_refresh_for_inactive_user_raises_401(self, service: AuthService) -> None:
        user = make_user(is_active=False)
        service._repo.seed(user)  # type: ignore[attr-defined]
        payload = {"sub": str(user.id), "type": "refresh"}

        with (
            patch("narrare.auth.service.verify_refresh_token", return_value=payload),
            pytest.raises(HTTPException) as exc,
        ):
            await service.refresh("valid-token")
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# _create_tokens (private, tested via public methods)
# ---------------------------------------------------------------------------


class TestAuthServiceCreateTokens:
    async def test_tokens_have_correct_expires_in(self, service: AuthService) -> None:
        user = make_user()
        service._repo.seed(user)  # type: ignore[attr-defined]

        with patch("narrare.auth.service.hash_password", return_value="hashed_pw"):
            result = await service.register(
                RegisterRequest(email="new@example.com", password="secret123")
            )

        assert result.expires_in == _FakeSettings.access_token_expire_minutes * 60
