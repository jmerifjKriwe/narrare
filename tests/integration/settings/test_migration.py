"""Integration tests for migration verification — new models can be created and queried.

The Alembic migration 0004_ai_settings creates user_providers, user_ai_settings
tables and adds JSONB columns to project_settings. Since the integration test
conftest creates all tables via Base.metadata.create_all(), the migration is
already implicitly tested. This test verifies the new models can be created
and queried correctly.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from narrare.settings.models import ProjectSettings, UserAiSettings, UserProvider
from narrare_core.crypto import encrypt

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [
    pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues"),
    pytest.mark.requires_db,
]


class TestUserProvidersTable:
    async def test_create_and_query_provider(self, db_session: AsyncSession) -> None:
        """UserProvider model can be created and queried."""
        user_id = uuid.uuid4()
        provider = UserProvider(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted=encrypt("sk-test-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        # Query it back
        result = await db_session.execute(
            select(UserProvider).where(UserProvider.user_id == user_id)
        )
        found = result.scalar_one()
        assert found.provider_name == "anthropic"
        assert found.is_active is True
        assert found.base_url is None

    async def test_provider_with_base_url(self, db_session: AsyncSession) -> None:
        """UserProvider with custom base_url stored correctly."""
        user_id = uuid.uuid4()
        provider = UserProvider(
            user_id=user_id,
            provider_name="openai",
            api_key_encrypted=encrypt("sk-key"),
            base_url="https://my-proxy.example.com/v1",
        )
        db_session.add(provider)
        await db_session.flush()

        result = await db_session.execute(
            select(UserProvider).where(UserProvider.id == provider.id)
        )
        found = result.scalar_one()
        assert found.base_url == "https://my-proxy.example.com/v1"

    async def test_provider_default_is_active(self, db_session: AsyncSession) -> None:
        """New providers are active by default."""
        user_id = uuid.uuid4()
        provider = UserProvider(
            user_id=user_id,
            provider_name="ollama",
            api_key_encrypted="",
        )
        db_session.add(provider)
        await db_session.flush()

        result = await db_session.execute(
            select(UserProvider).where(UserProvider.id == provider.id)
        )
        found = result.scalar_one()
        assert found.is_active is True


class TestUserAiSettingsTable:
    async def test_create_and_query_ai_settings(self, db_session: AsyncSession) -> None:
        """UserAiSettings model can be created and queried."""
        user_id = uuid.uuid4()

        # Create a provider first (FK constraint)
        provider = UserProvider(
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted=encrypt("sk-key"),
        )
        db_session.add(provider)
        await db_session.flush()

        # Create AI settings
        settings = UserAiSettings(
            user_id=user_id,
            default_provider_id=provider.id,
            default_model="claude-sonnet-4-5-20251020",
        )
        db_session.add(settings)
        await db_session.flush()

        # Query back
        result = await db_session.execute(
            select(UserAiSettings).where(UserAiSettings.user_id == user_id)
        )
        found = result.scalar_one()
        assert found.default_model == "claude-sonnet-4-5-20251020"
        assert found.default_provider_id == provider.id

    async def test_ai_settings_defaults(self, db_session: AsyncSession) -> None:
        """UserAiSettings has correct defaults."""
        user_id = uuid.uuid4()
        settings = UserAiSettings(user_id=user_id)
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(UserAiSettings).where(UserAiSettings.user_id == user_id)
        )
        found = result.scalar_one()
        assert found.default_provider_id is None
        assert found.default_model == ""
        assert found.category_overrides == {}
        assert found.intent_overrides == {}
        assert found.token_limit_overrides == {}

    async def test_ai_settings_jsonb_overrides(self, db_session: AsyncSession) -> None:
        """UserAiSettings JSONB columns store and retrieve dict data."""
        user_id = uuid.uuid4()
        provider_id = uuid.uuid4()

        settings = UserAiSettings(
            user_id=user_id,
            category_overrides={
                "writing": {"provider_id": str(provider_id), "model_id": "gpt-4o"},
            },
            intent_overrides={
                "write": {"provider_id": str(provider_id), "model_id": "claude"},
            },
            token_limit_overrides={
                "writing": {"max_tokens": 8000, "temperature": 0.9},
            },
        )
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(UserAiSettings).where(UserAiSettings.user_id == user_id)
        )
        found = result.scalar_one()
        assert "writing" in found.category_overrides
        assert "write" in found.intent_overrides
        assert "writing" in found.token_limit_overrides


class TestProjectSettingsJsonbColumns:
    async def test_project_settings_jsonb_overrides(self, db_session: AsyncSession) -> None:
        """ProjectSettings JSONB override columns store and retrieve correctly."""
        # We need a novel_id that exists (or create directly)
        # For this test, we create ProjectSettings directly
        novel_id = uuid.uuid4()

        settings = ProjectSettings(
            novel_id=novel_id,
            category_overrides={
                "analysis": {"provider_id": str(uuid.uuid4()), "model_id": "gpt-4o"},
            },
            intent_overrides={
                "sentiment": {"provider_id": str(uuid.uuid4()), "model_id": "haiku"},
            },
            token_limit_overrides={
                "analysis": {"max_tokens": 1500, "temperature": 0.2},
            },
        )
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert "analysis" in found.category_overrides
        assert "sentiment" in found.intent_overrides
        assert "analysis" in found.token_limit_overrides

    async def test_project_settings_defaults(self, db_session: AsyncSession) -> None:
        """ProjectSettings has correct defaults for JSONB columns."""
        novel_id = uuid.uuid4()

        settings = ProjectSettings(novel_id=novel_id)
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.category_overrides == {}
        assert found.intent_overrides == {}
        assert found.token_limit_overrides == {}
