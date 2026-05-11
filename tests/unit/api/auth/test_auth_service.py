"""Unit tests for auth/service.py — registration, login, token refresh."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from narrare.auth.models import User
from narrare.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from narrare.auth.service import AuthService


def _make_user(
    *,
    email: str = "user@example.com",
    is_active: bool = True,
    hashed_password: str = "$2b$12$fakehash",
) -> User:
    """Create a User instance with sensible defaults for testing."""
    from sqlalchemy.orm.attributes import set_attribute

    user = User()
    set_attribute(user, "id", uuid.uuid4())
    set_attribute(user, "email", email)
    set_attribute(user, "hashed_password", hashed_password)
    set_attribute(user, "display_name", "Test User")
    set_attribute(user, "is_active", is_active)
    set_attribute(user, "is_verified", False)
    return user


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.secret_key = "test-secret-key-at-least-32-characters-long"
    settings.access_token_expire_minutes = 60
    settings.refresh_token_expire_days = 30
    return settings


@pytest.fixture
def service(mock_session: MagicMock, mock_settings: MagicMock) -> AuthService:
    return AuthService(mock_session, mock_settings)


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestAuthServiceRegister:
    async def test_register_with_new_email_returns_tokens(self, service: AuthService) -> None:
        user = _make_user()
        service._repo.get_by_email = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        result = await service.register(
            RegisterRequest(email="new@example.com", password="secret123", display_name="New")
        )

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"

    async def test_register_with_existing_email_raises_409(self, service: AuthService) -> None:
        existing = _make_user(email="taken@example.com")
        service._repo.get_by_email = AsyncMock(return_value=existing)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.register(RegisterRequest(email="taken@example.com", password="secret123"))
        assert exc.value.status_code == 409
        assert "already registered" in exc.value.detail

    async def test_register_hashes_password_and_creates_user(self, service: AuthService) -> None:
        user = _make_user()
        service._repo.get_by_email = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        with patch("narrare.auth.service.hash_password", return_value="hashed_pw") as mock_hash:
            await service.register(RegisterRequest(email="new@example.com", password="mypassword"))
            mock_hash.assert_called_once_with("mypassword")

        service._repo.create.assert_called_once()  # type: ignore[reportPrivateUsage]
        call_kwargs = service._repo.create.call_args.kwargs  # type: ignore[reportPrivateUsage]
        assert call_kwargs["email"] == "new@example.com"
        assert call_kwargs["hashed_password"] == "hashed_pw"


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestAuthServiceLogin:
    async def test_login_with_valid_credentials_returns_tokens(self, service: AuthService) -> None:
        user = _make_user()
        service._repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        with patch("narrare.auth.service.verify_password", return_value=True):
            result = await service.login(
                LoginRequest(email="user@example.com", password="secret123")
            )

        assert isinstance(result, TokenResponse)
        assert result.access_token

    async def test_login_with_wrong_password_raises_401(self, service: AuthService) -> None:
        user = _make_user()
        service._repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        with (
            patch("narrare.auth.service.verify_password", return_value=False),
            pytest.raises(HTTPException) as exc,
        ):
            await service.login(LoginRequest(email="user@example.com", password="wrong"))
        assert exc.value.status_code == 401

    async def test_login_with_unknown_email_raises_401(self, service: AuthService) -> None:
        service._repo.get_by_email = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.login(LoginRequest(email="nobody@example.com", password="secret"))
        assert exc.value.status_code == 401

    async def test_login_with_inactive_user_raises_401(self, service: AuthService) -> None:
        user = _make_user(is_active=False)
        service._repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        with (
            patch("narrare.auth.service.verify_password", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            await service.login(LoginRequest(email="user@example.com", password="secret"))
        assert exc.value.status_code == 401
        assert "disabled" in exc.value.detail


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


class TestAuthServiceRefresh:
    async def test_refresh_with_valid_token_returns_new_tokens(
        self, service: AuthService, mock_settings: MagicMock
    ) -> None:
        user = _make_user()
        user_id_str = str(user.id)
        service._repo.get_by_id = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        payload = {"sub": user_id_str, "type": "refresh"}

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
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        payload = {"sub": str(uuid.uuid4()), "type": "refresh"}
        with (
            patch("narrare.auth.service.verify_refresh_token", return_value=payload),
            pytest.raises(HTTPException) as exc,
        ):
            await service.refresh("valid-token")
        assert exc.value.status_code == 401

    async def test_refresh_for_inactive_user_raises_401(self, service: AuthService) -> None:
        user = _make_user(is_active=False)
        service._repo.get_by_id = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

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
    async def test_tokens_have_correct_expires_in(
        self, service: AuthService, mock_settings: MagicMock
    ) -> None:
        user = _make_user()
        service._repo.get_by_email = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=user)  # type: ignore[reportPrivateUsage]

        result = await service.register(
            RegisterRequest(email="new@example.com", password="secret123")
        )

        assert result.expires_in == mock_settings.access_token_expire_minutes * 60
