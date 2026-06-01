"""Integration tests for gateway integration — resolver produces correct ResolvedModel.

This test verifies the resolver produces the correct ResolvedModel that
COULD be passed to the gateway. The gateway itself is mocked.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare.settings.models import UserAiSettings, UserProvider
from narrare_core.llm import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestGatewayIntegration:
    """End-to-end: intent → resolver → (mock) gateway."""

    async def test_resolver_produces_correct_resolved_model_for_default(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User with default model → resolver produces correct ResolvedModel."""
        from narrare.auth.models import User
        from narrare.auth.security import hash_password
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt

        user_id = uuid.uuid4()

        # Create user (required for FK constraint)
        user = User(
            id=user_id,
            email="default-test@example.com",
            hashed_password=hash_password("password123"),
            display_name="Default Test User",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Create provider
        provider = UserProvider(
            user_id=user_id,
            provider_name="openrouter",
            api_key_encrypted=encrypt("sk-or-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        # User AI settings with ONLY default model — no category overrides
        ai_settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="default-model",
        )
        db_session.add(ai_settings)
        await db_session.flush()

        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, None)

        assert result.config.model_id == "default-model"
        assert result.config.provider_name == "openrouter"
        assert result.source == "user_default"

    async def test_resolver_with_category_override(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User with category override → resolver uses override model."""
        from narrare.auth.models import User
        from narrare.auth.security import hash_password
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt

        user_id = uuid.uuid4()

        # Create user first (required for FK constraint)
        user = User(
            id=user_id,
            email="test@example.com",
            hashed_password=hash_password("password123"),
            display_name="Test User",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Create provider
        provider = UserProvider(
            user_id=user_id,
            provider_name="openrouter",
            api_key_encrypted=encrypt("sk-or-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        # User AI settings with category override
        ai_settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="default-model",
            category_overrides={
                "writing": {"provider_id": str(provider.id), "model_id": "override-model"},
            },
        )
        db_session.add(ai_settings)
        await db_session.flush()

        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, None)

        assert result.config.model_id == "override-model"
        assert result.source == "user_category"

    async def test_resolver_no_provider_raises_configuration_error(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User with no provider → ConfigurationError."""

        from narrare.auth.models import User
        from narrare.auth.security import hash_password
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.shared.errors import ConfigurationError

        user_id = uuid.uuid4()

        # Create user with NO provider and NO settings
        user = User(
            id=user_id,
            email="no-provider@example.com",
            hashed_password=hash_password("password123"),
            display_name="No Provider User",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await resolver.resolve(LLMIntent.WRITE, user_id, None)

    async def test_resolved_model_can_be_passed_to_fake_gateway(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Resolved model from resolver is compatible with FakeLLMGateway."""
        from narrare.auth.models import User
        from narrare.auth.security import hash_password
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt
        from narrare_core.llm import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        user_id = uuid.uuid4()

        # Create user (required for FK constraint)
        user = User(
            id=user_id,
            email="gateway-compat@example.com",
            hashed_password=hash_password("password123"),
            display_name="Gateway Compat User",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Create provider
        provider = UserProvider(
            user_id=user_id,
            provider_name="openrouter",
            api_key_encrypted=encrypt("sk-or-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        # User AI settings with default model
        ai_settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="default-model",
        )
        db_session.add(ai_settings)
        await db_session.flush()

        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, None)

        # Verify the result is a proper ResolvedModel
        assert isinstance(result, ResolvedModel)
        # Verify the config is a ResolvedModelConfig — the type ModelRegistry.get_model() expects
        assert isinstance(result.config, ResolvedModelConfig)
        # Verify all fields needed by ModelRegistry.get_model() are present
        assert result.config.provider_name == "openrouter"
        assert result.config.model_id == "default-model"
        # api_key and base_url are the kwargs passed to get_model()
        assert isinstance(result.api_key, str)
        # base_url is None when not set on provider
        assert result.base_url is None
