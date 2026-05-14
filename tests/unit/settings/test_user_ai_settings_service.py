"""Tests for UserAiSettingsService - happy path tests.

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

from narrare.settings.schemas import (
    UpdateUserAiSettingsRequest,
    UserAiSettingsResponse,
)
from narrare.settings.user_ai_settings_service import UserAiSettingsService

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
    token_limit_profile: str = "balanced"
    token_limit_overrides: dict[str, Any] = field(default_factory=dict)
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
# Tests - Get Settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    async def test_get_settings_returns_defaults(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """Get settings for new user -> returns default values."""
        settings = FakeUserAiSettings(
            user_id=user_id,
            default_provider_id=None,
            default_model="",
        )
        mock_ai_settings_repo.get = AsyncMock(return_value=settings)

        result = await service.get_settings(user_id)

        assert isinstance(result, UserAiSettingsResponse)
        assert result.user_id == user_id
        assert result.default_model == ""


# ---------------------------------------------------------------------------
# Tests - Set Default Model (happy path)
# ---------------------------------------------------------------------------


class TestSetDefaultModel:
    async def test_set_default_model_with_active_provider(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Set default model -> validates provider exists and is active."""
        provider = FakeProvider(
            id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="enc",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        updated = FakeUserAiSettings(
            user_id=user_id,
            default_provider_id=provider_id,
            default_model="claude-sonnet-4-5-20251020",
        )
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        request = UpdateUserAiSettingsRequest(
            default_provider_id=provider_id,
            default_model="claude-sonnet-4-5-20251020",
        )
        result = await service.update_settings(user_id, request)

        assert result.default_provider_id == provider_id
        assert result.default_model == "claude-sonnet-4-5-20251020"


# ---------------------------------------------------------------------------
# Tests - Category Overrides (happy path)
# ---------------------------------------------------------------------------


class TestCategoryOverrides:
    async def test_set_category_override_validates_provider(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Set category override -> validates provider exists."""
        provider = FakeProvider(
            id=provider_id,
            user_id=user_id,
            provider_name="openai",
            api_key_encrypted="enc",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        updated = FakeUserAiSettings(
            user_id=user_id,
            category_overrides={
                "writing": {"provider_id": str(provider_id), "model_id": "gpt-4o"},
            },
        )
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        request = UpdateUserAiSettingsRequest(
            category_overrides={
                "writing": {"provider_id": str(provider_id), "model_id": "gpt-4o"},
            },
        )
        result = await service.update_settings(user_id, request)

        assert "writing" in result.category_overrides


# ---------------------------------------------------------------------------
# Tests - Token Limit Profile (happy path)
# ---------------------------------------------------------------------------


class TestTokenLimitProfile:
    async def test_set_valid_token_limit_profile(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        """Set token_limit_profile to 'quick' -> success."""
        updated = FakeUserAiSettings(user_id=user_id)
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        request = UpdateUserAiSettingsRequest(token_limit_profile="quick")
        await service.update_settings(user_id, request)

        mock_ai_settings_repo.update.assert_called_once()

    @pytest.mark.parametrize("profile", ["quick", "balanced", "long_texts", "custom"])
    async def test_all_valid_profiles_accepted(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        profile: str,
    ) -> None:
        """Each valid profile name is accepted."""
        updated = FakeUserAiSettings(user_id=user_id)
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        request = UpdateUserAiSettingsRequest(token_limit_profile=profile)
        await service.update_settings(user_id, request)
        mock_ai_settings_repo.update.assert_called_once()
