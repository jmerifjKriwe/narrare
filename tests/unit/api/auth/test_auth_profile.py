"""Unit tests for auth/service.py — get_current_user_profile."""

from __future__ import annotations

import uuid

import pytest

from narrare.auth.schemas import UserResponse
from narrare.auth.service import AuthService
from narrare_core.shared.errors import AuthenticationError
from tests.factories import make_user
from tests.fakes import FakeAuthRepository, FakeUserProvidersRepository


@pytest.fixture
def fake_repo() -> FakeAuthRepository:
    return FakeAuthRepository()


@pytest.fixture
def fake_providers_repo() -> FakeUserProvidersRepository:
    return FakeUserProvidersRepository()


class _FakeSettings:
    """Minimal settings object for AuthService."""

    secret_key = "test-secret-key-at-least-32-characters-long"
    access_token_expire_minutes = 60
    refresh_token_expire_days = 30


@pytest.fixture
def service(
    fake_repo: FakeAuthRepository,
    fake_providers_repo: FakeUserProvidersRepository,
) -> AuthService:
    return AuthService(
        repo=fake_repo,
        settings=_FakeSettings(),  # type: ignore[arg-type]
        providers_repo=fake_providers_repo,
    )


class TestAuthServiceGetCurrentUserProfile:
    async def test_returns_profile_for_existing_user(
        self,
        service: AuthService,
        fake_repo: FakeAuthRepository,
    ) -> None:
        """get_current_user_profile returns UserResponse for a valid user."""
        user = make_user()
        fake_repo.seed(user)

        result = await service.get_current_user_profile(user.id)

        assert isinstance(result, UserResponse)
        assert result.id == user.id
        assert result.email == user.email

    async def test_has_providers_false_when_no_providers(
        self,
        service: AuthService,
        fake_repo: FakeAuthRepository,
        fake_providers_repo: FakeUserProvidersRepository,
    ) -> None:
        """New user with no providers has has_providers=False."""
        user = make_user()
        fake_repo.seed(user)
        # No providers seeded → count = 0

        result = await service.get_current_user_profile(user.id)

        assert result.has_providers is False

    async def test_has_providers_true_when_providers_exist(
        self,
        service: AuthService,
        fake_repo: FakeAuthRepository,
        fake_providers_repo: FakeUserProvidersRepository,
    ) -> None:
        """User with at least one provider has has_providers=True."""
        user = make_user()
        fake_repo.seed(user)
        fake_providers_repo.seed_count(user.id, count=2)

        result = await service.get_current_user_profile(user.id)

        assert result.has_providers is True

    async def test_raises_for_nonexistent_user(
        self,
        service: AuthService,
    ) -> None:
        """get_current_user_profile raises AuthenticationError for unknown user."""
        with pytest.raises(AuthenticationError, match="User not found"):
            await service.get_current_user_profile(uuid.uuid4())

    async def test_works_without_providers_repo(
        self,
        fake_repo: FakeAuthRepository,
    ) -> None:
        """Service works when providers_repo is None (graceful degradation)."""
        svc = AuthService(
            repo=fake_repo,
            settings=_FakeSettings(),  # type: ignore[arg-type]
            providers_repo=None,
        )
        user = make_user()
        fake_repo.seed(user)

        result = await svc.get_current_user_profile(user.id)

        assert isinstance(result, UserResponse)
        assert result.has_providers is False
