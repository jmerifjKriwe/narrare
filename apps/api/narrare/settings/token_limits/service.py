"""Token limits service — three-layer resolution cascade.

Resolves effective token limits by merging settings from:
1. User-DB overrides (highest priority)
2. Project-DB overrides
3. Operator-Env (application config)
4. Code defaults (lowest priority)

Usage:
    service = TokenLimitsService(user_repo, project_repo, config)
    limits = await service.get_resolved_limits(user_id="abc", project_id="novel_1")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare.settings.token_limits._validators import validate_token_overrides
from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.llm.cost_rates import ModelLimits, get_model_limits

if TYPE_CHECKING:
    from narrare._app.config import Settings
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )

logger = structlog.get_logger(__name__)


class TokenLimitsService:
    """Service for resolving token limits across all layers.

    Args:
        user_repo: Repository for user-level token limits.
        project_repo: Repository for project-level token limits.
        config: Application settings (operator-env layer).
    """

    def __init__(
        self,
        user_repo: UserTokenLimitsRepository,
        project_repo: ProjectTokenLimitsRepository,
        config: Settings,
    ) -> None:
        self._user_repo = user_repo
        self._project_repo = project_repo
        self._config = config

    async def get_resolved_limits(
        self,
        user_id: str,
        project_id: str | None = None,
    ) -> TokenLimitOverrides:
        """Resolve token limits by merging all layers.

        Resolution order (last wins):
        1. Code defaults (TokenLimitOverrides dataclass)
        2. Operator-Env (application Settings)
        3. Project-DB overrides (if project_id provided)
        4. User-DB overrides (highest priority)

        Args:
            user_id: The user's ID.
            project_id: Optional project/novel ID for project overrides.

        Returns:
            Fully resolved TokenLimitOverrides with all layers merged.
        """
        # Layer 1: Code defaults
        merged = TokenLimitOverrides()

        # Layer 2: Operator-Env (application config)
        merged = self._apply_env_layer(merged)

        # Layer 3: Project-DB overrides
        if project_id is not None:
            merged = await self._apply_project_layer(merged, project_id)

        # Layer 4: User-DB overrides (highest priority)
        merged = await self._apply_user_layer(merged, user_id)

        logger.debug(
            "token_limits_resolved",
            user_id=user_id,
            project_id=project_id,
            output_limit=merged.output_limit,
            token_profile=merged.token_profile,
        )

        return merged

    async def update_user_limits(
        self,
        user_id: str,
        overrides: dict[str, object],
    ) -> None:
        """Update user-level token limit overrides.

        Args:
            user_id: The user's ID.
            overrides: Partial dict of fields to update.

        Raises:
            ValidationError: If any field name is invalid.
        """
        validate_token_overrides(overrides)
        await self._user_repo.update(user_id, overrides)
        logger.info(
            "user_token_limits_updated",
            user_id=user_id,
            fields_updated=list(overrides.keys()),
        )

    async def update_project_limits(
        self,
        project_id: str,
        overrides: dict[str, object],
    ) -> None:
        """Update project-level token limit overrides.

        Args:
            project_id: The project/novel ID.
            overrides: Partial dict of fields to update.

        Raises:
            ValidationError: If any field name is invalid.
        """
        validate_token_overrides(overrides)
        await self._project_repo.update(project_id, overrides)
        logger.info(
            "project_token_limits_updated",
            project_id=project_id,
            fields_updated=list(overrides.keys()),
        )

    async def get_model_limits(
        self,
        provider: str,
        model_id: str,
    ) -> ModelLimits | None:
        """Look up model token limits from models.dev.

        Delegates to ``narrare_core.llm.cost_rates.get_model_limits()``.

        Args:
            provider: Provider name (e.g. "openai", "anthropic").
            model_id: Model identifier (e.g. "gpt-4o").

        Returns:
            ``ModelLimits`` with ``context`` and ``output``, or ``None`` if
            the model is not found in models.dev or the cache is unavailable.
        """
        return get_model_limits(provider, model_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_env_layer(self, base: TokenLimitOverrides) -> TokenLimitOverrides:
        """Merge operator-env settings on top of code defaults.

        Args:
            base: Current merged state.

        Returns:
            Updated TokenLimitOverrides with env values applied.
        """
        cfg = self._config
        return TokenLimitOverrides(
            output_limit=cfg.default_max_tokens,
            token_profile=base.token_profile,
            tier_percentages=base.tier_percentages,
            ws_timeout=cfg.ws_idle_timeout_seconds,
            retry_max_attempts=cfg.retry_max_attempts,
            retry_base_delay=cfg.retry_base_delay,
            max_chapter_tokens=cfg.consistency_max_chapter_tokens,
            max_kb_entries=cfg.consistency_max_kb_entries,
            max_selection_words=cfg.default_max_selection_words,
        )

    async def _apply_project_layer(
        self,
        base: TokenLimitOverrides,
        project_id: str,
    ) -> TokenLimitOverrides:
        """Merge project-DB overrides on top of current state.

        Args:
            base: Current merged state.
            project_id: The project to load overrides for.

        Returns:
            Updated TokenLimitOverrides with project overrides applied.
        """
        project_limits = await self._project_repo.get(project_id)
        overrides = project_limits.overrides or {}
        if not overrides:
            return base
        return self._merge_overrides(base, overrides)

    async def _apply_user_layer(
        self,
        base: TokenLimitOverrides,
        user_id: str,
    ) -> TokenLimitOverrides:
        """Merge user-DB overrides on top of current state (highest priority).

        Args:
            base: Current merged state.
            user_id: The user to load overrides for.

        Returns:
            Updated TokenLimitOverrides with user overrides applied.
        """
        user_limits = await self._user_repo.get(user_id)
        overrides = user_limits.overrides or {}
        if not overrides:
            return base
        return self._merge_overrides(base, overrides)

    @staticmethod
    def _merge_overrides(
        base: TokenLimitOverrides,
        overrides: dict[str, object],
    ) -> TokenLimitOverrides:
        """Merge a partial overrides dict into a TokenLimitOverrides.

        Only known fields from the overrides dict are applied.
        Unknown keys are silently ignored.

        Args:
            base: The current resolved state.
            overrides: Dict of fields to apply on top.

        Returns:
            A new TokenLimitOverrides with overrides merged in.
        """
        # Each field is extracted with cast() — the override value
        # either has the correct type (validated by _validate_overrides
        # at write time) or we fall back to base.* which is already typed.
        return TokenLimitOverrides(
            output_limit=cast("int", overrides.get("output_limit", base.output_limit)),
            token_profile=cast("str", overrides.get("token_profile", base.token_profile)),
            tier_percentages=cast(
                "dict[str, float] | None",
                overrides.get("tier_percentages", base.tier_percentages),
            ),
            ws_timeout=cast("int", overrides.get("ws_timeout", base.ws_timeout)),
            retry_max_attempts=cast(
                "int", overrides.get("retry_max_attempts", base.retry_max_attempts)
            ),
            retry_base_delay=cast(
                "float", overrides.get("retry_base_delay", base.retry_base_delay)
            ),
            max_chapter_tokens=cast(
                "int", overrides.get("max_chapter_tokens", base.max_chapter_tokens)
            ),
            max_kb_entries=cast("int", overrides.get("max_kb_entries", base.max_kb_entries)),
            max_selection_words=cast(
                "int", overrides.get("max_selection_words", base.max_selection_words)
            ),
        )
