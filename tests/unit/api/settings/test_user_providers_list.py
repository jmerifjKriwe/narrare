"""Unit tests for UserProvidersService — delete and list operations.

Tests business logic: deletion cascades, default reference cleanup, listing.
Repositories are faked — no DB, no real encryption.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from narrare_core.shared.errors import ValidationError
from tests.unit.api.settings._provider_fakes import (
    FakeAiSettingsRepo,
    FakeProvidersRepo,
    FakeUserProvider,
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


class TestDeleteProvider:
    async def test_delete_provider_removes_entry(
        self,
        service: Any,
        providers_repo: FakeProvidersRepo,
        ai_settings_repo: FakeAiSettingsRepo,
        user_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(user_id=user_id, provider_name="anthropic")
        providers_repo.seed(provider)

        await service.delete_provider(user_id, provider.id)

        assert provider.id not in providers_repo._providers

    async def test_delete_provider_clears_default_reference(
        self,
        service: Any,
        providers_repo: FakeProvidersRepo,
        ai_settings_repo: FakeAiSettingsRepo,
        user_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(user_id=user_id, provider_name="anthropic")
        providers_repo.seed(provider)
        ai_settings_repo.default_provider_id = provider.id

        await service.delete_provider(user_id, provider.id)

        assert ai_settings_repo.default_provider_id is None

    async def test_delete_provider_rejects_not_found(
        self,
        service: Any,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ValidationError, match="not found"):
            await service.delete_provider(user_id, uuid.uuid4())


class TestListProviders:
    @patch(
        "narrare.settings.user_providers_service.UserProvidersService._to_response",
        fake_to_response,
    )
    async def test_list_providers_returns_list(
        self,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        p1 = FakeUserProvider(user_id=user_id, provider_name="anthropic")
        p2 = FakeUserProvider(user_id=user_id, provider_name="openai")
        providers_repo.seed(p1, p2)

        result = await service.list_providers(user_id)

        assert len(result) == 2
        assert all(r.provider_name in ("anthropic", "openai") for r in result)

    async def test_list_providers_returns_empty_for_new_user(
        self,
        service: Any,
        user_id: uuid.UUID,
    ) -> None:
        result = await service.list_providers(user_id)
        assert result == []

    @patch(
        "narrare.settings.user_providers_service.UserProvidersService._to_response",
        fake_to_response,
    )
    async def test_list_providers_masks_api_keys(
        self,
        service: Any,
        providers_repo: FakeProvidersRepo,
        user_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="some_encrypted_data",
        )
        providers_repo.seed(provider)

        result = await service.list_providers(user_id)

        assert len(result) == 1
        assert result[0].has_api_key is True
        assert result[0].api_key_last4 == "●●●●"
