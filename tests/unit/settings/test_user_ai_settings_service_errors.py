"""Tests for UserAiSettingsService - error cases.

Split from test_user_ai_settings_service.py for RULE-04 compliance.
All repository calls are mocked (no I/O, no DB).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.settings.schemas import UpdateUserAiSettingsRequest
from narrare.settings.user_ai_settings_service import UserAiSettingsService
from narrare_core.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Fake ORM objects
# ---------------------------------------------------------------------------


@dataclass
class FakeProvider:
    id: uuid.UUID
    user_id: uuid.UUID
    provider_name: str
    api_key_encrypted: str
    base_url: str | None = None
    is_active: bool = True


@dataclass
class FakeUserAiSettings:
    user_id: uuid.UUID
    default_provider_id: uuid.UUID | None = None
    default_model: str = ""
    category_overrides: dict[str, Any] = field(default_factory=dict)
    intent_overrides: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
def mock_ai_settings_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_providers_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def service(
    mock_ai_settings_repo: AsyncMock,
    mock_providers_repo: AsyncMock,
) -> UserAiSettingsService:
    return UserAiSettingsService(
        ai_settings_repo=mock_ai_settings_repo,
        providers_repo=mock_providers_repo,
    )


# ---------------------------------------------------------------------------
# Tests - Error Cases for Default Model
# ---------------------------------------------------------------------------


class TestSetDefaultModelErrors:
    async def test_set_default_model_with_inactive_provider_raises(
        self,
        service: UserAiSettingsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Set default model with inactive provider -> ValidationError."""
        provider = FakeProvider(
            id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="enc",
            is_active=False,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        request = UpdateUserAiSettingsRequest(
            default_provider_id=provider_id,
            default_model="claude-sonnet-4-5-20251020",
        )

        with pytest.raises(ValidationError, match="Provider is not active"):
            await service.update_settings(user_id, request)

    async def test_set_default_model_with_nonexistent_provider_raises(
        self,
        service: UserAiSettingsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Set default model referencing non-existent provider -> ValidationError."""
        mock_providers_repo.get = AsyncMock(return_value=None)

        request = UpdateUserAiSettingsRequest(
            default_provider_id=provider_id,
            default_model="gpt-4o",
        )

        with pytest.raises(ValidationError, match="Referenced provider not found"):
            await service.update_settings(user_id, request)

    async def test_set_default_model_with_wrong_user_provider_raises(
        self,
        service: UserAiSettingsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Set default model referencing another user's provider -> ValidationError."""
        other_user = uuid.uuid4()
        provider = FakeProvider(
            id=provider_id,
            user_id=other_user,
            provider_name="anthropic",
            api_key_encrypted="enc",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        request = UpdateUserAiSettingsRequest(
            default_provider_id=provider_id,
            default_model="gpt-4o",
        )

        with pytest.raises(ValidationError, match="Referenced provider not found"):
            await service.update_settings(user_id, request)
