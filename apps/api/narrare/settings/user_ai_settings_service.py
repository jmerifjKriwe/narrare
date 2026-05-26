"""User AI settings service — default model, overrides, token limits.

Manages user-level AI configuration:
- Default provider + model selection
- Category-level model overrides
- Intent-level model overrides
- Token limit profile and per-category/intent token overrides

Validates that any referenced provider exists and is active before
persisting changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.settings.token_profiles import VALID_TOKEN_LIMIT_PROFILES
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.settings.schemas import (
        UpdateUserAiSettingsRequest,
        UserAiSettingsResponse,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository

logger = structlog.get_logger(__name__)


class UserAiSettingsService:
    """Service for managing user-level AI settings.

    Args:
        ai_settings_repo: Repository for user AI settings.
        providers_repo: Repository for provider lookups (reference validation).
    """

    def __init__(
        self,
        ai_settings_repo: UserAiSettingsRepository,
        providers_repo: UserProvidersRepository,
        token_limits_service: TokenLimitsService | None = None,
    ) -> None:
        self._ai_settings_repo = ai_settings_repo
        self._providers_repo = providers_repo
        self._token_limits_service = token_limits_service

    async def get_settings(
        self,
        user_id: uuid.UUID,
    ) -> UserAiSettingsResponse:
        """Get user AI settings with computed embedding tier.

        Args:
            user_id: The user's UUID.

        Returns:
            The user's AI settings response with ``active_embedding_tier``.
        """
        from narrare.settings.schemas import UserAiSettingsResponse

        settings = await self._ai_settings_repo.get(user_id)
        response = UserAiSettingsResponse.model_validate(settings)

        # Compute active embedding tier from user's providers
        response.active_embedding_tier = await self._compute_embedding_tier(
            user_id, settings.embedding_provider
        )

        return response

    async def _compute_embedding_tier(self, user_id: uuid.UUID, embedding_provider: str) -> str:
        """Compute the active embedding cascade tier.

        Args:
            user_id: The user's UUID.
            embedding_provider: User's embedding provider setting.

        Returns:
            String describing the active tier: "openai", "local", or "disabled".
        """
        from narrare_core.memory.embedding_cascade import EmbeddingCascadeResolver

        providers = await self._providers_repo.get_active(user_id)
        user_providers = [p.provider_name for p in providers]
        user_api_keys: dict[str, str] = {}
        user_base_urls: dict[str, str | None] = {}

        # We don't expose actual API keys here — just check if provider exists
        # The cascade resolver checks key presence, so we provide placeholder info
        for p in providers:
            user_api_keys[p.provider_name] = "exists"  # type: ignore[assignment]
            user_base_urls[p.provider_name] = p.base_url

        resolver = EmbeddingCascadeResolver()
        config = resolver.resolve(
            user_providers=user_providers,
            user_api_keys=user_api_keys,
            user_base_urls=user_base_urls,
            explicit_provider=embedding_provider,
        )
        return config.provider

    async def update_settings(
        self,
        user_id: uuid.UUID,
        request: UpdateUserAiSettingsRequest,
    ) -> UserAiSettingsResponse:
        """Update user AI settings. Validates provider references.

        Args:
            user_id: The user's UUID.
            request: Update data with optional fields.

        Returns:
            Updated AI settings response.

        Raises:
            ValidationError: If a referenced provider doesn't exist or is inactive,
                or if token_limit_profile is invalid.
        """
        updates = request.model_dump(exclude_none=True)

        # Validate default_provider_id if provided
        if "default_provider_id" in updates:
            provider_id = updates["default_provider_id"]
            if provider_id is not None:
                await self._validate_provider_active(user_id, provider_id)

        # Validate category_overrides providers if provided
        if "category_overrides" in updates:
            await self._validate_override_providers(user_id, updates["category_overrides"])

        # Validate intent_overrides providers if provided
        if "intent_overrides" in updates:
            await self._validate_override_providers(user_id, updates["intent_overrides"])

        # Validate token_limit_profile if provided
        if "token_limit_profile" in updates:
            profile = updates["token_limit_profile"]
            if profile not in VALID_TOKEN_LIMIT_PROFILES:
                raise ValidationError(
                    f"Invalid token limit profile: {profile}",
                    code="INVALID_TOKEN_LIMIT_PROFILE",
                )

        # Dual-write to TokenLimitsService (DEPRECATED — old columns)
        if self._token_limits_service and "token_limit_profile" in updates:
            logger.warning(
                "token_limit_profile_write_deprecated",
                user_id=str(user_id),
            )
            await self._token_limits_service.update_user_limits(
                user_id=str(user_id),
                overrides={"token_profile": updates["token_limit_profile"]},
            )

        if self._token_limits_service and "token_limit_overrides" in updates:
            logger.warning(
                "token_limit_overrides_write_deprecated",
                user_id=str(user_id),
            )
            await self._token_limits_service.update_user_limits(
                user_id=str(user_id),
                overrides={"legacy_per_category_overrides": updates["token_limit_overrides"]},
            )

        settings = await self._ai_settings_repo.update(user_id, **updates)

        logger.info(
            "user_ai_settings_updated",
            user_id=str(user_id),
            fields_updated=list(updates.keys()),
        )

        from narrare.settings.schemas import UserAiSettingsResponse

        return UserAiSettingsResponse.model_validate(settings)

    async def _validate_provider_active(self, user_id: uuid.UUID, provider_id: uuid.UUID) -> None:
        """Validate that a provider exists and is active.

        Args:
            user_id: The user's UUID.
            provider_id: The provider to validate.

        Raises:
            ValidationError: If provider not found, belongs to another user,
                or is inactive.
        """
        provider = await self._providers_repo.get(provider_id)
        if provider is None or provider.user_id != user_id:
            raise ValidationError(
                "Referenced provider not found",
                code="PROVIDER_NOT_FOUND",
            )
        if not provider.is_active:
            raise ValidationError(
                "Provider is not active",
                code="PROVIDER_INACTIVE",
            )

    async def _validate_override_providers(
        self, user_id: uuid.UUID, overrides: dict[str, object]
    ) -> None:
        """Validate that all provider references in overrides are active.

        Args:
            user_id: The user's UUID.
            overrides: Dict of category/intent → override data with provider_id.

        Raises:
            ValidationError: If any referenced provider is not found or inactive.
        """
        overrides_dict: dict[str, object] = overrides  # type: ignore[assignment]
        for _key, value in overrides_dict.items():
            if isinstance(value, dict) and "provider_id" in value:
                from uuid import UUID

                raw_str = str(value["provider_id"])  # type: ignore[arg-type]
                try:
                    pid = UUID(raw_str)
                except (ValueError, AttributeError) as err:
                    raise ValidationError(
                        f"Invalid provider_id in override: {raw_str!r}",
                        code="INVALID_PROVIDER_ID",
                    ) from err
                await self._validate_provider_active(user_id, pid)
