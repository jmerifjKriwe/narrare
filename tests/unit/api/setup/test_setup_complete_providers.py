"""Unit tests for setup/service.complete() — provider and AI settings handling."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

from narrare.setup.schemas import AIProvider

from ._complete_helpers import (
    _FakeAiSettingsRepo,
    _FakeProvidersRepo,
    _make_wizard_state,
)

if TYPE_CHECKING:
    from narrare.setup.service import SetupService


class TestCompleteProviders:
    async def test_complete_creates_user_provider_entry(
        self, complete_service: SetupService
    ) -> None:
        """complete() saves provider to user_providers (new AI settings system)."""
        user_id = uuid.uuid4()
        state = _make_wizard_state(provider=AIProvider.ANTHROPIC, api_key="sk-ant-test-123")

        await complete_service.complete(str(user_id), state)

        providers_repo = cast("_FakeProvidersRepo", complete_service._providers_repo)
        assert len(providers_repo.created) == 1
        entry = providers_repo.created[0]
        assert entry["user_id"] == user_id
        assert entry["provider_name"] == "anthropic"
        assert entry["api_key_encrypted"]  # Not empty, not the plain key
        assert entry["api_key_encrypted"] != "sk-ant-test-123"  # Must be encrypted
        assert entry["base_url"] is None

    async def test_complete_creates_user_provider_with_zai_coding_base_url(
        self, complete_service: SetupService
    ) -> None:
        """Z.AI coding endpoint gets explicit base_url."""
        user_id = uuid.uuid4()
        state = _make_wizard_state(
            provider=AIProvider.ZAI, api_key="zai-key", zai_endpoint="coding"
        )

        await complete_service.complete(str(user_id), state)

        providers_repo = cast("_FakeProvidersRepo", complete_service._providers_repo)
        assert len(providers_repo.created) == 1
        assert providers_repo.created[0]["base_url"] == "https://api.z.ai/api/coding/paas/v4"

    async def test_complete_creates_user_provider_with_zai_general_no_base_url(
        self, complete_service: SetupService
    ) -> None:
        """Z.AI general endpoint has no base_url (provider factory handles default)."""
        user_id = uuid.uuid4()
        state = _make_wizard_state(
            provider=AIProvider.ZAI, api_key="zai-key", zai_endpoint="general"
        )

        await complete_service.complete(str(user_id), state)

        providers_repo = cast("_FakeProvidersRepo", complete_service._providers_repo)
        assert len(providers_repo.created) == 1
        assert providers_repo.created[0]["base_url"] is None

    async def test_complete_updates_ai_settings_with_default_model(
        self, complete_service: SetupService
    ) -> None:
        """complete() sets default provider and model in user_ai_settings."""
        user_id = uuid.uuid4()
        state = _make_wizard_state(model="claude-sonnet-4-5-20251020")

        await complete_service.complete(str(user_id), state)

        ai_settings_repo = cast("_FakeAiSettingsRepo", complete_service._ai_settings_repo)
        assert len(ai_settings_repo.updates) == 1
        update = ai_settings_repo.updates[0]
        assert update["user_id"] == user_id
        assert update["default_model"] == "claude-sonnet-4-5-20251020"
        assert update["default_provider_id"] is not None

    async def test_complete_with_ollama_saves_empty_encrypted_key(
        self, complete_service: SetupService
    ) -> None:
        """Ollama provider gets empty encrypted key (no key needed)."""
        user_id = uuid.uuid4()
        state = _make_wizard_state(provider=AIProvider.OLLAMA, api_key="")

        await complete_service.complete(str(user_id), state)

        providers_repo = cast("_FakeProvidersRepo", complete_service._providers_repo)
        assert len(providers_repo.created) == 1
        assert providers_repo.created[0]["api_key_encrypted"] == ""
