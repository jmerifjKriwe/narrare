"""Unit tests for setup/service.complete() — provider and AI settings handling."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

from narrare.setup.schemas import AIProvider

from ._complete_helpers import (
    _FakeAiSettingsRepo,
    _FakeProvidersRepo,
    _make_mock_session,
    _make_service,
    _make_wizard_state,
)

if TYPE_CHECKING:
    from narrare.setup.service import SetupService
    from tests.fakes import FakeDemoLoader, FakeProviderService


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

    # --- Regression: skip_provider flag ------------------------------------

    async def test_complete_skips_provider_when_flag_set(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """When skip_provider=True, no new provider is created and existing is preserved."""
        user_id = uuid.uuid4()
        existing_provider_id = uuid.uuid4()

        # Fake existing AI settings with a default provider
        fake_settings = type(
            "FakeSettings",
            (),
            {
                "default_provider_id": existing_provider_id,
                "default_model": "claude-sonnet-4-5-20251020",
            },
        )()

        # Mock session.execute to return an existing provider
        mock_session = _make_mock_session()
        fake_provider = type(
            "FakeProvider",
            (),
            {
                "id": existing_provider_id,
                "provider_name": "anthropic",
            },
        )()
        mock_result = MagicMock(spec=object)
        mock_result.scalar_one_or_none = MagicMock(spec=object, return_value=fake_provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = _make_service(
            fake_provider_service,
            fake_demo_loader,
            mock_session=mock_session,
            ai_settings_override=fake_settings,
        )

        state = _make_wizard_state(skip_provider=True)

        result = await svc.complete(str(user_id), state)

        # No provider was created
        providers_repo = cast("_FakeProvidersRepo", svc._providers_repo)
        assert len(providers_repo.created) == 0

        # No ai_settings update was made (provider not overwritten)
        ai_settings_repo = cast("_FakeAiSettingsRepo", svc._ai_settings_repo)
        assert len(ai_settings_repo.updates) == 0

        # ProjectSettings uses existing provider's name
        add_calls = mock_session.add.call_args_list
        project_settings = add_calls[1][0][0]
        assert project_settings.ai_provider == "anthropic"
        assert project_settings.ai_model == "claude-sonnet-4-5-20251020"

        assert isinstance(result.novel_id, str)

    async def test_complete_skips_provider_without_existing_settings(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """When skip_provider=True and no existing settings, ProjectSettings uses empty strings."""
        user_id = uuid.uuid4()

        # Existing settings but no default provider configured
        fake_settings = type(
            "FakeSettings",
            (),
            {
                "default_provider_id": None,
                "default_model": "",
            },
        )()

        svc = _make_service(
            fake_provider_service,
            fake_demo_loader,
            ai_settings_override=fake_settings,
        )

        state = _make_wizard_state(skip_provider=True)

        result = await svc.complete(str(user_id), state)

        # No provider was created
        providers_repo = cast("_FakeProvidersRepo", svc._providers_repo)
        assert len(providers_repo.created) == 0

        # ProjectSettings uses empty strings (no provider configured yet)
        add_calls = svc._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        project_settings = add_calls[1][0][0]
        assert project_settings.ai_provider == ""
        assert project_settings.ai_model == ""

        assert isinstance(result.novel_id, str)
