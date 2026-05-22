"""Unit tests for UserProvidersService — create and update provider operations.

Tests business logic: validation, encryption, duplicate checks.
Repositories are faked — no DB, no real encryption.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from narrare.settings.schemas import CreateProviderRequest, UpdateProviderRequest
from narrare_core.shared.errors import ValidationError
from tests.unit.api.settings._provider_fakes import (
    FakeAiSettingsRepo,
    FakeProvidersRepo,
    fake_to_response,
)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def providers_repo() -> FakeProvidersRepo:
    return FakeProvidersRepo()


@pytest.fixture
def ai_settings_repo() -> FakeAiSettingsRepo:
    return FakeAiSettingsRepo()


@pytest.fixture
def service(providers_repo: FakeProvidersRepo, ai_settings_repo: FakeAiSettingsRepo) -> Any:
    from narrare.settings.user_providers_service import UserProvidersService

    return UserProvidersService(
        providers_repo=providers_repo,  # type: ignore[arg-type]
        ai_settings_repo=ai_settings_repo,  # type: ignore[arg-type]
    )


class TestCreateProvider:
    @patch("narrare.settings.user_providers_service.encrypt", return_value="encrypted_value")
    @patch(
        "narrare.settings.user_providers_service.UserProvidersService._to_response",
        fake_to_response,
    )
    async def test_create_provider_validates_and_stores(
        self,
        mock_encrypt: Any,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        request = CreateProviderRequest(
            provider_name="anthropic",
            api_key="sk-ant-key123",
            base_url=None,
        )

        result = await service.create_provider(user_id, request)

        assert result.provider_name == "anthropic"
        assert result.has_api_key is True
        assert result.is_active is True
        mock_encrypt.assert_called_once_with("sk-ant-key123")

    @patch("narrare.settings.user_providers_service.encrypt", return_value="encrypted_value")
    async def test_create_provider_rejects_duplicate_name(
        self,
        mock_encrypt: Any,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        from tests.unit.api.settings._provider_fakes import FakeUserProvider

        existing = FakeUserProvider(user_id=user_id, provider_name="anthropic")
        providers_repo.seed(existing)

        request = CreateProviderRequest(
            provider_name="anthropic",
            api_key="sk-ant-key456",
        )

        with pytest.raises(ValidationError, match="already exists"):
            await service.create_provider(user_id, request)


class TestUpdateProvider:
    @patch("narrare.settings.user_providers_service.encrypt", return_value="new_encrypted")
    @patch(
        "narrare.settings.user_providers_service.UserProvidersService._to_response",
        fake_to_response,
    )
    async def test_update_provider_changes_config(
        self,
        mock_encrypt: Any,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        from tests.unit.api.settings._provider_fakes import FakeUserProvider

        provider = FakeUserProvider(user_id=user_id, provider_name="anthropic")
        providers_repo.seed(provider)

        request = UpdateProviderRequest(api_key="new-key", base_url="https://custom.api.com")

        result = await service.update_provider(user_id, provider.id, request)

        assert result.provider_name == "anthropic"
        mock_encrypt.assert_called_once_with("new-key")
        assert providers_repo._providers[provider.id].base_url == "https://custom.api.com"

    async def test_update_provider_rejects_not_found(
        self,
        service: Any,
        user_id: uuid.UUID,
    ) -> None:
        request = UpdateProviderRequest(api_key="new-key")

        with pytest.raises(ValidationError, match="not found"):
            await service.update_provider(user_id, uuid.uuid4(), request)

    async def test_update_provider_rejects_deactivating_last_provider(
        self,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        from tests.unit.api.settings._provider_fakes import FakeUserProvider

        provider = FakeUserProvider(user_id=user_id, provider_name="anthropic", is_active=True)
        providers_repo.seed(provider)

        request = UpdateProviderRequest(is_active=False)

        with pytest.raises(ValidationError, match="Cannot deactivate"):
            await service.update_provider(user_id, provider.id, request)

    @patch("narrare.settings.user_providers_service.encrypt", return_value="new_encrypted")
    @patch(
        "narrare.settings.user_providers_service.UserProvidersService._to_response",
        fake_to_response,
    )
    async def test_update_provider_can_deactivate_when_others_active(
        self,
        mock_encrypt: Any,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        from tests.unit.api.settings._provider_fakes import FakeUserProvider

        p1 = FakeUserProvider(user_id=user_id, provider_name="anthropic", is_active=True)
        p2 = FakeUserProvider(user_id=user_id, provider_name="openai", is_active=True)
        providers_repo.seed(p1, p2)

        request = UpdateProviderRequest(is_active=False)

        result = await service.update_provider(user_id, p1.id, request)

        assert result.is_active is False
