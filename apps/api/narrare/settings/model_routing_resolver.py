"""Model routing resolver — implements the cascade resolution from DB.

Implements the ``ModelRoutingResolver`` Protocol from core by reading
from the database repositories. The cascade priority is:

    project intent → project category → user intent → user category → user default
    → ConfigurationError

The resolver is created per-request with a database session and is NOT
a singleton. It resolves synchronously (all DB reads happen in the
repos, which are async; the resolver awaits them internally).

See: openspec/changes/configurable-model-routing/specs/model-routing-cascade/spec.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare_core.crypto import decrypt
from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, get_default_profile_for_intent
from narrare_core.llm.intent_profiles import get_intent_profile
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare_core.llm import LLMIntent

logger = structlog.get_logger(__name__)


class ModelRoutingResolverImpl:
    """Database-backed model routing resolver.

    Resolves which model + provider to use for a given LLM intent by
    checking the configuration cascade through project and user settings.

    Args:
        user_providers_repo: Repository for provider lookups.
        user_ai_settings_repo: Repository for user AI settings.
        project_ai_settings_repo: Repository for project AI settings.
    """

    def __init__(
        self,
        user_providers_repo: UserProvidersRepository,
        user_ai_settings_repo: UserAiSettingsRepository,
        project_ai_settings_repo: ProjectAiSettingsRepository,
    ) -> None:
        self._providers_repo = user_providers_repo
        self._user_ai_repo = user_ai_settings_repo
        self._project_ai_repo = project_ai_settings_repo

    async def resolve(
        self,
        intent: LLMIntent,
        user_id: UUID,
        project_id: UUID | None,
    ) -> ResolvedModel:
        """Resolve model configuration for a given intent and context.

        Follows the cascade:
        1. Project-level intent override
        2. Project-level category override
        3. User-level intent override
        4. User-level category override
        5. User's default model
        6. ConfigurationError

        Args:
            intent: The LLM operation intent.
            user_id: User whose settings to check.
            project_id: Optional project for project-level overrides.

        Returns:
            ``ResolvedModel`` with config, credentials, and source metadata.

        Raises:
            ConfigurationError: If no provider is configured for this user.
        """
        intent_name = intent.value
        category = INTENT_CATEGORY_MAP.get(intent)
        category_name = category.value if category else None

        # Advisory capability tier — populated on every resolved model
        # for observability/logging. Does not affect routing logic.
        intent_profile = get_intent_profile(intent)
        recommended_tier = intent_profile.capability_tier

        # --- Project-level overrides ---
        if project_id is not None:
            project_settings = await self._project_ai_repo.get(project_id)

            # 1. Project intent override
            intent_overrides: dict[str, object] = project_settings.intent_overrides or {}
            if intent_name in intent_overrides:
                result = await self._resolve_override(
                    user_id, intent_overrides[intent_name], intent, "project_intent"
                )
                if result is not None:
                    return result

            # 2. Project category override
            if category_name is not None:
                cat_overrides: dict[str, object] = project_settings.category_overrides or {}
                if category_name in cat_overrides:
                    result = await self._resolve_override(
                        user_id, cat_overrides[category_name], intent, "project_category"
                    )
                    if result is not None:
                        return result

        # --- User-level overrides ---
        user_settings = await self._user_ai_repo.get(user_id)

        # 3. User intent override
        user_intent_overrides: dict[str, object] = user_settings.intent_overrides or {}
        if intent_name in user_intent_overrides:
            result = await self._resolve_override(
                user_id, user_intent_overrides[intent_name], intent, "user_intent"
            )
            if result is not None:
                return result

        # 4. User category override
        if category_name is not None:
            user_cat_overrides: dict[str, object] = user_settings.category_overrides or {}
            if category_name in user_cat_overrides:
                result = await self._resolve_override(
                    user_id, user_cat_overrides[category_name], intent, "user_category"
                )
                if result is not None:
                    return result

        # 5. User default model
        if user_settings.default_provider_id is not None and user_settings.default_model:
            provider = await self._providers_repo.get(user_settings.default_provider_id)
            if provider is not None and provider.is_active:
                api_key = self._decrypt_key(provider.api_key_encrypted)
                profile = get_default_profile_for_intent(intent)
                return ResolvedModel(
                    config=ResolvedModelConfig(
                        provider_name=provider.provider_name,
                        model_id=user_settings.default_model,
                        token_limit_profile=profile,
                    ),
                    api_key=api_key,
                    base_url=provider.base_url,
                    source="user_default",
                    recommended_tier=recommended_tier,
                )

        # 6. No configuration found
        raise ConfigurationError(
            "No AI provider configured. Go to Settings → AI Provider to set up a provider.",
            code="NO_AI_PROVIDER",
        )

    async def _resolve_override(
        self,
        user_id: UUID,
        override_data: object,
        intent: LLMIntent,
        source: str,
    ) -> ResolvedModel | None:
        """Resolve a single override entry to a ResolvedModel.

        Args:
            user_id: User who owns the providers.
            override_data: Dict with provider_id and model_id.
            intent: The LLM intent (used for default profile lookup).
            source: Source label for the result metadata.

        Returns:
            ResolvedModel, or None if the override is invalid.
        """
        if not isinstance(override_data, dict):
            logger.warning("invalid_override_data", source=source, data=override_data)
            return None

        # Narrow to typed dict after isinstance guard
        data = cast("dict[str, object]", override_data)
        provider_id_raw: object = data.get("provider_id")
        model_id_raw: object = data.get("model_id")

        if not provider_id_raw or not model_id_raw:
            return None

        from uuid import UUID

        try:
            provider_id_str = str(provider_id_raw)
            provider_id = UUID(provider_id_str)
        except ValueError, AttributeError:
            logger.warning(
                "invalid_provider_id_in_override",
                source=source,
                provider_id=provider_id_raw,
            )
            return None

        provider = await self._providers_repo.get(provider_id)
        if provider is None or provider.user_id != user_id or not provider.is_active:
            logger.warning(
                "provider_not_found_or_inactive",
                source=source,
                provider_id=str(provider_id),
            )
            return None

        api_key = self._decrypt_key(provider.api_key_encrypted)
        profile = get_default_profile_for_intent(intent)
        intent_profile = get_intent_profile(intent)
        model_id = str(model_id_raw)
        return ResolvedModel(
            config=ResolvedModelConfig(
                provider_name=provider.provider_name,
                model_id=model_id,
                token_limit_profile=profile,
            ),
            api_key=api_key,
            base_url=provider.base_url,
            source=source,
            recommended_tier=intent_profile.capability_tier,
        )

    @staticmethod
    def _decrypt_key(encrypted_key: str) -> str | None:
        """Decrypt an API key, returning None for empty keys.

        Args:
            encrypted_key: The Fernet-encrypted key or empty string.

        Returns:
            The decrypted key, or None if the encrypted value is empty.
        """
        if not encrypted_key:
            return None
        return decrypt(encrypted_key)
