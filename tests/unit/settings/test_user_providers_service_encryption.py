"""Tests for UserProvidersService - encryption, masking, and security.

Split from test_user_providers_service.py for RULE-04 compliance.
All repository calls are mocked (no I/O, no DB).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from narrare.settings.models import UserProvider
from narrare.settings.schemas import UpdateProviderRequest
from narrare.settings.user_providers_service import UserProvidersService
from narrare_core.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    *,
    provider_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    provider_name: str = "anthropic",
    api_key_encrypted: str = "encrypted-value",
    base_url: str | None = None,
    is_active: bool = True,
) -> UserProvider:
    """Create a real UserProvider ORM object (in-memory, no DB)."""
    now = datetime.now(UTC)
    return UserProvider(
        id=provider_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        provider_name=provider_name,
        api_key_encrypted=api_key_encrypted,
        base_url=base_url,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def _make_ai_settings(
    *,
    user_id: uuid.UUID | None = None,
    default_provider_id: uuid.UUID | None = None,
    default_model: str = "",
) -> object:
    """Create a simple settings-like object with default_provider_id."""
    from dataclasses import dataclass

    @dataclass
    class _Fake:
        user_id: uuid.UUID
        default_provider_id: uuid.UUID | None
        default_model: str

    return _Fake(
        user_id=user_id or uuid.uuid4(),
        default_provider_id=default_provider_id,
        default_model=default_model,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def provider_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_providers_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_by_user = AsyncMock(return_value=[])
    repo.get_active = AsyncMock(return_value=[])
    repo.get_by_name = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_ai_settings_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_make_ai_settings())
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def service(
    mock_providers_repo: AsyncMock,
    mock_ai_settings_repo: AsyncMock,
) -> UserProvidersService:
    return UserProvidersService(
        providers_repo=mock_providers_repo,
        ai_settings_repo=mock_ai_settings_repo,
    )


# ---------------------------------------------------------------------------
# Tests - Update Provider (re-encryption)
# ---------------------------------------------------------------------------


class TestUpdateProvider:
    async def test_update_api_key_re_encrypts(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Update API key -> new key is encrypted."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="old-encrypted",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        updated = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="new-encrypted",
        )
        mock_providers_repo.update = AsyncMock(return_value=updated)

        request = UpdateProviderRequest(api_key="sk-new-key")
        await service.update_provider(user_id, provider_id, request)

        call_kwargs = mock_providers_repo.update.call_args
        assert call_kwargs.kwargs["api_key_encrypted"] != "sk-new-key"

    async def test_update_provider_not_found_raises(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        mock_providers_repo.get = AsyncMock(return_value=None)

        request = UpdateProviderRequest(api_key="sk-new")
        with pytest.raises(ValidationError, match="Provider not found"):
            await service.update_provider(user_id, provider_id, request)

    async def test_update_provider_wrong_user_raises(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        other_user = uuid.uuid4()
        provider = _make_provider(
            provider_id=provider_id,
            user_id=other_user,
            provider_name="anthropic",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        request = UpdateProviderRequest(api_key="sk-new")
        with pytest.raises(ValidationError, match="Provider not found"):
            await service.update_provider(user_id, provider_id, request)


# ---------------------------------------------------------------------------
# Tests - Deactivate Last Provider (security)
# ---------------------------------------------------------------------------


class TestDeactivateLastProvider:
    async def test_cannot_deactivate_last_active_provider(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = _make_provider(provider_id=provider_id, user_id=user_id, is_active=True)
        mock_providers_repo.get = AsyncMock(return_value=provider)
        mock_providers_repo.get_active = AsyncMock(return_value=[provider])

        request = UpdateProviderRequest(is_active=False)

        with pytest.raises(ValidationError, match="Cannot deactivate the only active provider"):
            await service.update_provider(user_id, provider_id, request)

    async def test_can_deactivate_when_another_active_exists(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = _make_provider(provider_id=provider_id, user_id=user_id, is_active=True)
        other_provider = _make_provider(
            user_id=user_id,
            provider_name="openai",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)
        mock_providers_repo.get_active = AsyncMock(return_value=[provider, other_provider])

        updated = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            is_active=False,
        )
        mock_providers_repo.update = AsyncMock(return_value=updated)

        request = UpdateProviderRequest(is_active=False)
        result = await service.update_provider(user_id, provider_id, request)

        assert result.is_active is False


# ---------------------------------------------------------------------------
# Tests - Delete Provider (security validations)
# ---------------------------------------------------------------------------


class TestDeleteProviderSecurity:
    async def test_delete_provider_that_is_default_clears_default(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Deleting the default provider -> clears default_provider_id and default_model."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)
        mock_ai_settings_repo.get = AsyncMock(
            return_value=_make_ai_settings(
                user_id=user_id,
                default_provider_id=provider_id,
                default_model="claude-sonnet-4-5-20251020",
            ),
        )

        await service.delete_provider(user_id, provider_id)

        mock_ai_settings_repo.update.assert_called_once_with(
            user_id,
            default_provider_id=None,
            default_model="",
        )

    async def test_delete_provider_not_found_raises(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        mock_providers_repo.get = AsyncMock(return_value=None)

        with pytest.raises(ValidationError, match="Provider not found"):
            await service.delete_provider(user_id, provider_id)

    async def test_delete_provider_wrong_user_raises(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        other_user = uuid.uuid4()
        provider = _make_provider(
            provider_id=provider_id,
            user_id=other_user,
            provider_name="anthropic",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        with pytest.raises(ValidationError, match="Provider not found"):
            await service.delete_provider(user_id, provider_id)
