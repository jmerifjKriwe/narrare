"""Unit tests for UserProvidersRepository.count_by_user().

Verifies that the provider count logic correctly reports the presence
or absence of configured providers for a given user. Uses the
FakeProvidersRepo to avoid DB dependencies.
"""

from __future__ import annotations

import uuid

from tests.unit.api.settings._provider_fakes import FakeProvidersRepo


class TestCountByUser:
    """Tests for FakeProvidersRepo.count_by_user()."""

    async def test_count_by_user_with_no_providers_returns_zero(self) -> None:
        """User with no providers returns 0."""
        repo = FakeProvidersRepo()
        user_id = uuid.uuid4()

        result = await repo.count_by_user(user_id)

        assert result == 0

    async def test_count_by_user_with_one_provider_returns_one(self) -> None:
        """User with one provider returns 1."""
        repo = FakeProvidersRepo()
        user_id = uuid.uuid4()
        await repo.create(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="encrypted_key",
            base_url=None,
        )

        result = await repo.count_by_user(user_id)

        assert result == 1

    async def test_count_by_user_with_multiple_providers_returns_count(self) -> None:
        """User with multiple providers returns the correct count."""
        repo = FakeProvidersRepo()
        user_id = uuid.uuid4()
        await repo.create(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="key1",
            base_url=None,
        )
        await repo.create(
            user_id=user_id,
            provider_name="openrouter",
            api_key_encrypted="key2",
            base_url=None,
        )

        result = await repo.count_by_user(user_id)

        assert result == 2

    async def test_count_by_user_ignores_other_users_providers(self) -> None:
        """Providers belonging to other users are not counted."""
        repo = FakeProvidersRepo()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        await repo.create(
            user_id=user_a,
            provider_name="anthropic",
            api_key_encrypted="key_a",
            base_url=None,
        )
        await repo.create(
            user_id=user_b,
            provider_name="openrouter",
            api_key_encrypted="key_b",
            base_url=None,
        )

        result = await repo.count_by_user(user_a)

        assert result == 1

    async def test_count_by_user_with_zero_used_for_has_providers(self) -> None:
        """count_by_user result can be used directly for has_providers check."""
        repo = FakeProvidersRepo()
        user_id = uuid.uuid4()

        count = await repo.count_by_user(user_id)
        has_providers = count > 0

        assert has_providers is False

    async def test_count_by_user_with_providers_used_for_has_providers(self) -> None:
        """count_by_user > 0 correctly maps to has_providers=True."""
        repo = FakeProvidersRepo()
        user_id = uuid.uuid4()
        await repo.create(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="key",
            base_url=None,
        )

        count = await repo.count_by_user(user_id)
        has_providers = count > 0

        assert has_providers is True
