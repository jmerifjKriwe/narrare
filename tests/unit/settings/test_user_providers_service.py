"""Tests for UserProvidersService - CRUD operations.

Split from test_user_providers_service.py for RULE-04 compliance.
All repository calls are mocked (no I/O, no DB).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from narrare.settings.models import UserProvider
from narrare.settings.schemas import (
    CreateProviderRequest,
    ProviderResponse,
)
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
# Tests - Create Provider
# ---------------------------------------------------------------------------


class TestCreateProvider:
    async def test_create_provider_encrypts_api_key(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """Create provider -> encrypts API key, stores encrypted version."""
        request = CreateProviderRequest(
            provider_name="anthropic",
            api_key="sk-ant-secret-key",
        )

        created = _make_provider(user_id=user_id, provider_name="anthropic")
        mock_providers_repo.create = AsyncMock(return_value=created)

        result = await service.create_provider(user_id, request)

        call_kwargs = mock_providers_repo.create.call_args
        encrypted_arg = call_kwargs.kwargs["api_key_encrypted"]
        assert encrypted_arg != "sk-ant-secret-key"
        assert len(encrypted_arg) > 0
        assert isinstance(result, ProviderResponse)

    async def test_create_provider_returns_masked_response(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """Create provider -> response has has_api_key=True, never full key."""
        created = _make_provider(
            user_id=user_id,
            provider_name="openai",
            api_key_encrypted="some-encrypted-value",
        )
        mock_providers_repo.create = AsyncMock(return_value=created)

        request = CreateProviderRequest(provider_name="openai", api_key="sk-test")
        result = await service.create_provider(user_id, request)

        assert result.has_api_key is True
        assert result.api_key_last4 != "sk-test"
        assert "sk-test" not in result.api_key_last4

    async def test_create_duplicate_provider_raises(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """Creating a provider that already exists -> ValidationError."""
        existing = _make_provider(user_id=user_id, provider_name="anthropic")
        mock_providers_repo.get_by_name = AsyncMock(return_value=existing)

        request = CreateProviderRequest(
            provider_name="anthropic",
            api_key="sk-new-key",
        )

        with pytest.raises(ValidationError, match="already exists"):
            await service.create_provider(user_id, request)


# ---------------------------------------------------------------------------
# Tests - List Providers
# ---------------------------------------------------------------------------


class TestListProviders:
    async def test_list_providers_returns_all_with_masked_keys(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """List providers -> all keys are masked."""
        providers = [
            _make_provider(user_id=user_id, provider_name="anthropic"),
            _make_provider(user_id=user_id, provider_name="openai"),
        ]
        mock_providers_repo.get_by_user = AsyncMock(return_value=providers)

        results = await service.list_providers(user_id)

        assert len(results) == 2
        for r in results:
            assert isinstance(r, ProviderResponse)
            assert r.has_api_key is True

    async def test_list_empty_returns_empty_list(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """List providers with none configured -> empty list."""
        mock_providers_repo.get_by_user = AsyncMock(return_value=[])
        results = await service.list_providers(user_id)
        assert results == []


# ---------------------------------------------------------------------------
# Tests - Delete Provider (basic CRUD)
# ---------------------------------------------------------------------------


class TestDeleteProvider:
    async def test_delete_provider_removes_entry(
        self,
        service: UserProvidersService,
        mock_providers_repo: AsyncMock,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Delete provider -> calls repo.delete."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="groq",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)
        mock_ai_settings_repo.get = AsyncMock(
            return_value=_make_ai_settings(user_id=user_id, default_provider_id=None),
        )

        await service.delete_provider(user_id, provider_id)
        mock_providers_repo.delete.assert_called_once_with(provider_id)
