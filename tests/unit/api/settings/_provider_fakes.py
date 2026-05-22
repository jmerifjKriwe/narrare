from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from narrare.settings.schemas import ProviderResponse


class FakeUserProvider:
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        provider_name: str = "anthropic",
        api_key_encrypted: str = "encrypted_key",
        base_url: str | None = None,
        is_active: bool = True,
    ) -> None:
        self.id = id or uuid.uuid4()
        self.user_id = user_id or uuid.uuid4()
        self.provider_name = provider_name
        self.api_key_encrypted = api_key_encrypted
        self.base_url = base_url
        self.is_active = is_active
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


def fake_to_response(*args: Any) -> ProviderResponse:
    provider = args[-1]
    has_key = bool(provider.api_key_encrypted)
    return ProviderResponse(
        id=provider.id,
        provider_name=provider.provider_name,
        has_api_key=has_key,
        api_key_last4="●●●●" if has_key else "****",
        base_url=provider.base_url,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


class FakeProvidersRepo:
    def __init__(self) -> None:
        self._providers: dict[uuid.UUID, FakeUserProvider] = {}

    def seed(self, *providers: FakeUserProvider) -> None:
        for p in providers:
            self._providers[p.id] = p

    async def get_by_name(self, user_id: uuid.UUID, provider_name: str) -> FakeUserProvider | None:
        for p in self._providers.values():
            if p.user_id == user_id and p.provider_name == provider_name:
                return p
        return None

    async def create(
        self,
        user_id: uuid.UUID,
        provider_name: str,
        api_key_encrypted: str,
        base_url: str | None,
    ) -> FakeUserProvider:
        provider = FakeUserProvider(
            id=uuid.uuid4(),
            user_id=user_id,
            provider_name=provider_name,
            api_key_encrypted=api_key_encrypted,
            base_url=base_url,
        )
        self._providers[provider.id] = provider
        return provider

    async def get(self, provider_id: uuid.UUID) -> FakeUserProvider | None:
        return self._providers.get(provider_id)

    async def get_by_user(self, user_id: uuid.UUID) -> list[FakeUserProvider]:
        return [p for p in self._providers.values() if p.user_id == user_id]

    async def get_active(self, user_id: uuid.UUID) -> list[FakeUserProvider]:
        return [p for p in self._providers.values() if p.user_id == user_id and p.is_active]

    async def update(self, provider_id: uuid.UUID, **kwargs: Any) -> FakeUserProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ValueError(f"Provider {provider_id} not found")
        for key, value in kwargs.items():
            setattr(provider, key, value)
        return provider

    async def delete(self, provider_id: uuid.UUID) -> None:
        self._providers.pop(provider_id, None)


class FakeAiSettingsRepo:
    def __init__(self) -> None:
        self.default_provider_id: uuid.UUID | None = None
        self.default_model: str = ""

    async def get(self, user_id: uuid.UUID) -> Any:
        settings = AsyncMock()
        settings.default_provider_id = self.default_provider_id
        return settings

    async def update(self, user_id: uuid.UUID, **kwargs: Any) -> Any:
        if "default_provider_id" in kwargs:
            self.default_provider_id = kwargs["default_provider_id"]
        if "default_model" in kwargs:
            self.default_model = kwargs["default_model"]
        return AsyncMock()
