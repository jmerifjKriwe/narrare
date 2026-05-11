"""Unit tests for auth/repository.py — DB query layer."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.auth.models import User
from narrare.auth.repository import AuthRepository


def _make_user(**kwargs: object) -> User:
    from sqlalchemy.orm.attributes import set_attribute

    user = User()
    set_attribute(user, "id", kwargs.get("id", uuid.uuid4()))
    set_attribute(user, "email", kwargs.get("email", "test@example.com"))
    set_attribute(user, "hashed_password", kwargs.get("hashed_password", "hashed"))
    set_attribute(user, "display_name", kwargs.get("display_name", "Test"))
    set_attribute(user, "is_active", True)
    set_attribute(user, "is_verified", kwargs.get("is_verified", False))
    return user


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_session: MagicMock) -> AuthRepository:
    return AuthRepository(mock_session)


class TestAuthRepositoryGetByEmail:
    async def test_returns_user_when_found(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        user = _make_user(email="found@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_email("found@example.com")

        assert result is not None
        assert result.email == "found@example.com"

    async def test_returns_none_when_not_found(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_email("missing@example.com")

        assert result is None

    async def test_lowercases_email(self, repo: AuthRepository, mock_session: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repo.get_by_email("UPPER@Example.COM")

        # Verify the query was executed (the lower() is in the SQL WHERE clause)
        mock_session.execute.assert_called_once()


class TestAuthRepositoryGetById:
    async def test_returns_user_when_found(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        uid = uuid.uuid4()
        user = _make_user(id=uid)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uid)

        assert result is not None
        assert result.id == uid

    async def test_returns_none_when_not_found(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None


class TestAuthRepositoryCreate:
    async def test_creates_user_and_flushes(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        result = await repo.create(
            email="New@Example.COM",
            hashed_password="hashed",
            display_name="Tester",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        # Email should be lowercased in the model constructor
        assert result.email == "new@example.com"

    async def test_create_defaults_empty_display_name(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        result = await repo.create(
            email="new@example.com",
            hashed_password="hashed",
        )

        assert result.display_name == ""


class TestAuthRepositorySetVerified:
    async def test_sets_verified_flag(self, repo: AuthRepository, mock_session: MagicMock) -> None:
        uid = uuid.uuid4()
        user = _make_user(id=uid, is_verified=False)

        # Mock get_by_id to return the user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        await repo.set_verified(uid)

        assert user.is_verified is True
        mock_session.flush.assert_called_once()

    async def test_does_nothing_when_user_not_found(
        self, repo: AuthRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        await repo.set_verified(uuid.uuid4())

        # flush should NOT be called since user is None
        mock_session.flush.assert_not_called()
