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
from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.requires_db


class TestGatewayIntegration:
    """End-to-end: intent → resolver → (mock) gateway."""

    async def test_resolver_produces_correct_resolved_model_for_default(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User with default model → resolver produces correct ResolvedModel."""
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt

        user_id = uuid.uuid4()

        # Create a provider
        provider = UserProvider(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted=encrypt("sk-test-api-key-12345"),
        )
        db_session.add(provider)
        await db_session.flush()

        # Create user AI settings
        ai_settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="claude-sonnet-4-5-20251020",
        )
        db_session.add(ai_settings)
        await db_session.flush()

        # Create resolver
        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        # Resolve
        result = await resolver.resolve(LLMIntent.WRITE, user_id, None)

        # Verify the resolved model is correct
        assert isinstance(result.config, ResolvedModelConfig)
        assert result.config.provider_name == "anthropic"
        assert result.config.model_id == "claude-sonnet-4-5-20251020"
        assert result.source == "user_default"
        assert result.api_key == "sk-test-api-key-12345"

    async def test_resolver_with_category_override(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User with category override → resolver uses override model."""
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt

        user_id = uuid.uuid4()

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
        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository

        user_id = uuid.uuid4()

        # Create empty settings (no default)
        ai_settings = UserAiSettings(user_id=user_id)
        db_session.add(ai_settings)
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
        from tests.fakes.fake_llm_gateway import FakeLLMGateway

        from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
        from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
        from narrare.settings.user_providers_repository import UserProvidersRepository
        from narrare_core.crypto import encrypt

        user_id = uuid.uuid4()

        provider = UserProvider(
            user_id=user_id,
            provider_name="openai",
            api_key_encrypted=encrypt("sk-openai-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        ai_settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="gpt-4o",
        )
        db_session.add(ai_settings)
        await db_session.flush()

        resolver = ModelRoutingResolverImpl(
            user_providers_repo=UserProvidersRepository(db_session),
            user_ai_settings_repo=UserAiSettingsRepository(db_session),
            project_ai_settings_repo=ProjectAiSettingsRepository(db_session),
        )

        # Resolve
        resolved = await resolver.resolve(LLMIntent.WRITE, user_id, None)

        # Pass to fake gateway
        gateway = FakeLLMGateway()
        gateway.returns("Test response")

        result = await gateway.run(
            intent=LLMIntent.WRITE,
            system_prompt="System.",
            user_prompt="Write.",
            config=resolved.config,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

        assert result.text == "Test response"
        gateway.assert_called_once()
        call = gateway.last_call()
        assert call.config is not None
        assert call.config.provider_name == "openai"
        assert call.config.model_id == "gpt-4o"
        assert call.api_key == "sk-openai-key"
