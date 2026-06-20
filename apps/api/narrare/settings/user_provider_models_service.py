"""User provider models service — fetch live models for a stored provider.

Handles:
- Decrypting stored API keys
- Validating provider ownership and active status
- Calling the provider's model listing API
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.setup.constants import OLLAMA_DEFAULT_URL
from narrare_core.crypto import decrypt
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare.setup.schemas import AvailableModelsResponse

logger = structlog.get_logger(__name__)


class UserProviderModelsService:
    """Service for fetching live model lists from user providers.

    Args:
        providers_repo: Repository for provider CRUD.
    """

    def __init__(
        self,
        providers_repo: UserProvidersRepository,
    ) -> None:
        self._providers_repo = providers_repo

    async def get_provider_models(
        self,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> AvailableModelsResponse:
        """Fetch live models for a provider using its stored API key.

        Decrypts the stored API key and calls the provider's model listing
        endpoint to retrieve up-to-date available models.

        Args:
            user_id: The user's UUID (for ownership verification).
            provider_id: The provider entry to fetch models for.

        Returns:
            Available models response from the provider API.

        Raises:
            ValidationError: If provider not found, belongs to another user,
                or is inactive.
        """
        from narrare.setup.provider_service import ProviderService
        from narrare.setup.schemas import AIProvider

        provider = await self._providers_repo.get(provider_id)
        if provider is None or provider.user_id != user_id:
            raise ValidationError(
                "Provider not found",
                code="PROVIDER_NOT_FOUND",
            )

        if not provider.is_active:
            raise ValidationError(
                "Provider is inactive. Activate it to fetch models.",
                code="PROVIDER_INACTIVE",
            )

        api_key = decrypt(provider.api_key_encrypted)

        try:
            ai_provider = AIProvider(provider.provider_name)
        except ValueError:
            raise ValidationError(
                f"Unknown provider: {provider.provider_name}",
                code="UNKNOWN_PROVIDER",
            ) from None

        provider_service = ProviderService()
        ollama_url = provider.base_url or OLLAMA_DEFAULT_URL
        result = await provider_service.list_models(
            provider=ai_provider,
            api_key=api_key,
            ollama_url=ollama_url,
        )

        logger.info(
            "provider_models_fetched",
            user_id=str(user_id),
            provider_id=str(provider_id),
            provider=provider.provider_name,
            model_count=len(result.models),
        )

        return result
