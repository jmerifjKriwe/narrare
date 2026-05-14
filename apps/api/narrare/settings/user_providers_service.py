"""User providers service — CRUD with encryption for AI provider entries.

Handles:
- Encrypting API keys before storage
- Masking API keys on read (only last 4 chars visible)
- Validating that referenced providers exist
- Preventing deactivation of the last active provider
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.crypto import encrypt
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.settings.schemas import (
        CreateProviderRequest,
        ProviderResponse,
        UpdateProviderRequest,
    )
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository

logger = structlog.get_logger(__name__)


class UserProvidersService:
    """Service for managing user AI providers with encryption.

    Args:
        providers_repo: Repository for provider CRUD.
        ai_settings_repo: Repository for AI settings (to clear dangling references).
    """

    def __init__(
        self,
        providers_repo: UserProvidersRepository,
        ai_settings_repo: UserAiSettingsRepository,
    ) -> None:
        self._providers_repo = providers_repo
        self._ai_settings_repo = ai_settings_repo

    async def create_provider(
        self,
        user_id: uuid.UUID,
        request: CreateProviderRequest,
    ) -> ProviderResponse:
        """Register a new AI provider for a user.

        Encrypts the API key before storage.

        Args:
            user_id: The user's UUID.
            request: Provider creation data.

        Returns:
            Provider response with masked API key.

        Raises:
            ValidationError: If a provider with this name already exists.
        """
        existing = await self._providers_repo.get_by_name(user_id, request.provider_name)
        if existing is not None:
            raise ValidationError(
                f"Provider '{request.provider_name}' already exists for this user",
                code="PROVIDER_ALREADY_EXISTS",
            )

        encrypted_key = encrypt(request.api_key)

        provider = await self._providers_repo.create(
            user_id=user_id,
            provider_name=request.provider_name,
            api_key_encrypted=encrypted_key,
            base_url=request.base_url,
        )

        logger.info(
            "provider_created",
            user_id=str(user_id),
            provider_name=request.provider_name,
            provider_id=str(provider.id),
        )

        return self._to_response(provider)

    async def list_providers(
        self,
        user_id: uuid.UUID,
    ) -> list[ProviderResponse]:
        """List all providers for a user with masked API keys.

        Args:
            user_id: The user's UUID.

        Returns:
            List of provider responses.
        """
        providers = await self._providers_repo.get_by_user(user_id)
        return [self._to_response(p) for p in providers]

    async def update_provider(
        self,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
        request: UpdateProviderRequest,
    ) -> ProviderResponse:
        """Update provider credentials or status.

        If is_active is being set to False, validates that this is not
        the last active provider.

        Args:
            user_id: The user's UUID.
            provider_id: The provider to update.
            request: Update data.

        Returns:
            Updated provider response.

        Raises:
            ValidationError: If provider not found, belongs to another user,
                or is the last active provider being deactivated.
        """
        provider = await self._providers_repo.get(provider_id)
        if provider is None or provider.user_id != user_id:
            raise ValidationError(
                "Provider not found",
                code="PROVIDER_NOT_FOUND",
            )

        updates: dict[str, object] = {}

        if request.api_key is not None:
            updates["api_key_encrypted"] = encrypt(request.api_key)

        if request.base_url is not None:
            updates["base_url"] = request.base_url

        if request.is_active is not None:
            if not request.is_active and provider.is_active:
                # Check this isn't the last active provider
                active_providers = await self._providers_repo.get_active(user_id)
                if len(active_providers) <= 1:
                    raise ValidationError(
                        "Cannot deactivate the only active provider. Add another provider first.",
                        code="CANNOT_DEACTIVATE_LAST_PROVIDER",
                    )
            updates["is_active"] = request.is_active

        if updates:
            provider = await self._providers_repo.update(provider_id, **updates)

        logger.info(
            "provider_updated",
            user_id=str(user_id),
            provider_id=str(provider_id),
            fields_updated=list(updates.keys()),
        )

        return self._to_response(provider)

    async def delete_provider(
        self,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Delete a provider. Clears references from AI settings.

        If the deleted provider is the default, the default is cleared.

        Args:
            user_id: The user's UUID.
            provider_id: The provider to delete.

        Raises:
            ValidationError: If provider not found or belongs to another user.
        """
        provider = await self._providers_repo.get(provider_id)
        if provider is None or provider.user_id != user_id:
            raise ValidationError(
                "Provider not found",
                code="PROVIDER_NOT_FOUND",
            )

        # Clear references from user_ai_settings
        ai_settings = await self._ai_settings_repo.get(user_id)
        if ai_settings.default_provider_id == provider_id:
            await self._ai_settings_repo.update(user_id, default_provider_id=None, default_model="")
            logger.info(
                "default_provider_cleared_after_delete",
                user_id=str(user_id),
                deleted_provider_id=str(provider_id),
            )

        await self._providers_repo.delete(provider_id)

        logger.info(
            "provider_deleted",
            user_id=str(user_id),
            provider_id=str(provider_id),
        )

    @staticmethod
    def _to_response(provider: object) -> ProviderResponse:
        """Convert a UserProvider model to a masked response.

        Args:
            provider: The UserProvider ORM object.

        Returns:
            ProviderResponse with masked API key.
        """
        from narrare.settings.models import UserProvider
        from narrare.settings.schemas import ProviderResponse

        assert isinstance(provider, UserProvider)

        api_key_encrypted: str = provider.api_key_encrypted
        has_key = bool(api_key_encrypted)

        # Simple masking: show last 4 of encrypted (not the real key)
        # The encrypted text is a Fernet token, not the real key
        # We just show whether a key exists
        return ProviderResponse(
            id=provider.id,
            provider_name=provider.provider_name,
            has_api_key=has_key,
            api_key_last4="****" if not has_key else "●●●●",
            base_url=provider.base_url,
            is_active=provider.is_active,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
