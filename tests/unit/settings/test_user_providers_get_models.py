"""Tests for UserProviderModelsService.get_provider_models.

Covers the authenticated model-fetching endpoint logic:
- Happy path: returns live models from provider API
- Error: provider not found
- Error: provider belongs to another user
- Error: provider is inactive
- Error: unknown provider name string

All repository and external calls are mocked (no I/O, no DB, no LLM).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from narrare.settings.models import UserProvider
from narrare.settings.user_provider_models_service import UserProviderModelsService
from narrare.setup.schemas import AIProvider, AvailableModelsResponse, ProviderModel
from narrare_core.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    *,
    provider_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    provider_name: str = "anthropic",
    api_key_encrypted: str = "encrypted-value",
    base_url: str | None = None,
    is_active: bool = True,
) -> UserProvider:
    """Create a real UserProvider ORM object (in-memory, no DB)."""
    now = datetime.now(UTC)
    return UserProvider(
        id=provider_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        provider_name=provider_name,
        api_key_encrypted=api_key_encrypted,
        base_url=base_url,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def _make_ai_settings(
    *,
    user_id: uuid.UUID | None = None,
    default_provider_id: uuid.UUID | None = None,
    default_model: str = "",
) -> object:
    """Create a simple settings-like object with default_provider_id."""
    from dataclasses import dataclass

    @dataclass
    class _Fake:
        user_id: uuid.UUID
        default_provider_id: uuid.UUID | None
        default_model: str

    return _Fake(
        user_id=user_id or uuid.uuid4(),
        default_provider_id=default_provider_id,
        default_model=default_model,
    )


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
def mock_providers_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_by_user = AsyncMock(return_value=[])
    repo.get_active = AsyncMock(return_value=[])
    repo.get_by_name = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_ai_settings_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_make_ai_settings())
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def service(
    mock_providers_repo: AsyncMock,
) -> UserProviderModelsService:
    return UserProviderModelsService(
        providers_repo=mock_providers_repo,
    )


# ---------------------------------------------------------------------------
# Tests - get_provider_models
# ---------------------------------------------------------------------------


class TestGetProviderModels:
    """Tests for UserProviderModelsService.get_provider_models."""

    async def test_happy_path_returns_models(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Active provider with valid name -> returns models from ProviderService."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            api_key_encrypted="enc-key",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        expected_response = AvailableModelsResponse(
            provider=AIProvider.ANTHROPIC,
            models=[
                ProviderModel(id="claude-sonnet-4-5-20251020", name="Claude Sonnet 4.5"),
            ],
        )

        with (
            patch(
                "narrare.settings.user_provider_models_service.decrypt", return_value="sk-decrypted"
            ),
            patch("narrare.setup.provider_service.ProviderService") as mock_ps_cls,
        ):
            mock_ps = AsyncMock()
            mock_ps.list_models = AsyncMock(return_value=expected_response)
            mock_ps_cls.return_value = mock_ps

            result = await service.get_provider_models(user_id, provider_id)

        assert isinstance(result, AvailableModelsResponse)
        assert result.provider == AIProvider.ANTHROPIC
        assert len(result.models) == 1
        assert result.models[0].id == "claude-sonnet-4-5-20251020"
        mock_ps.list_models.assert_called_once_with(
            provider=AIProvider.ANTHROPIC,
            api_key="sk-decrypted",
            ollama_url="http://localhost:11434",
        )

    async def test_passes_base_url_as_ollama_url(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Ollama provider with custom base_url -> passes it as ollama_url."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="ollama",
            api_key_encrypted="enc-key",
            base_url="http://my-ollama:11434",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        expected_response = AvailableModelsResponse(
            provider=AIProvider.OLLAMA,
            models=[ProviderModel(id="llama3", name="Llama 3")],
        )

        with (
            patch("narrare.settings.user_provider_models_service.decrypt", return_value=""),
            patch("narrare.setup.provider_service.ProviderService") as mock_ps_cls,
        ):
            mock_ps = AsyncMock()
            mock_ps.list_models = AsyncMock(return_value=expected_response)
            mock_ps_cls.return_value = mock_ps

            result = await service.get_provider_models(user_id, provider_id)

        mock_ps.list_models.assert_called_once_with(
            provider=AIProvider.OLLAMA,
            api_key="",
            ollama_url="http://my-ollama:11434",
        )
        assert result.provider == AIProvider.OLLAMA

    async def test_provider_not_found_raises(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Provider ID doesn't exist -> ValidationError."""
        mock_providers_repo.get = AsyncMock(return_value=None)

        with pytest.raises(ValidationError, match="Provider not found"):
            await service.get_provider_models(user_id, provider_id)

    async def test_provider_wrong_user_raises(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Provider belongs to another user -> ValidationError."""
        other_user = uuid.uuid4()
        provider = _make_provider(
            provider_id=provider_id,
            user_id=other_user,
            provider_name="anthropic",
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        with pytest.raises(ValidationError, match="Provider not found"):
            await service.get_provider_models(user_id, provider_id)

    async def test_inactive_provider_raises(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Provider is inactive -> ValidationError with PROVIDER_INACTIVE code."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            is_active=False,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        with pytest.raises(ValidationError, match="inactive"):
            await service.get_provider_models(user_id, provider_id)

    async def test_unknown_provider_name_raises(
        self,
        service: UserProviderModelsService,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Provider name doesn't map to any AIProvider enum -> ValidationError."""
        provider = _make_provider(
            provider_id=provider_id,
            user_id=user_id,
            provider_name="unknown_provider_xyz",
            is_active=True,
        )
        mock_providers_repo.get = AsyncMock(return_value=provider)

        with (
            patch("narrare.settings.user_provider_models_service.decrypt", return_value="sk-key"),
            pytest.raises(ValidationError, match="Unknown provider"),
        ):
            await service.get_provider_models(user_id, provider_id)
