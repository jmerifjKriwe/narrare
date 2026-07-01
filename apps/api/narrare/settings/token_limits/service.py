"""Token limits service — three-layer resolution cascade.

Resolves effective token limits by merging settings from:
1. User-DB overrides (highest priority)
2. Project-DB overrides
3. Operator-Env (application config)
4. Code defaults (lowest priority)

CR-08 P1:
* Legacy persisted ``conservative`` is normalised to ``balanced`` at the read
  boundary and never re-emitted (D2).
* An explicit ``output_limit`` override without a ``token_profile`` override
  resolves the profile to ``custom`` so the raw limit takes effect (D3).
* Preset profiles resolve their effective limit via
  :attr:`TokenLimitOverrides.effective_output_limit`.

Usage:
    service = TokenLimitsService(user_repo, project_repo, config)
    limits = await service.get_resolved_limits(user_id="abc", project_id="novel_1")
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

import structlog

from narrare.settings.token_limits._validators import validate_token_overrides
from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.llm.cost_rates import ModelLimits, get_model_limits
from narrare_core.llm.token_profiles import (
    TokenLimitProfile,
    normalize_legacy_token_profile,
)

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

        After merging, the resolved profile is finalised: legacy
        ``conservative`` is normalised to ``balanced`` and an explicit
        ``output_limit`` without a profile resolves to ``custom``.

        Args:
            user_id: The user's ID.
            project_id: Optional project/novel ID for project overrides.

        Returns:
            Fully resolved TokenLimitOverrides with all layers merged.
        """
        # Layer 1: Code defaults
        merged = TokenLimitOverrides()

        # Layer 2: Operator-Env (application config). Env values are not
        # "explicit user intent" and must not trigger custom inference.
        merged = self._apply_env_layer(merged)

        # Layers 3 & 4: DB overrides. Track which keys were explicitly set by
        # user/project intent so the custom-mode inference (D3) can fire.
        explicit: set[str] = set()
        if project_id is not None:
            project_overrides = self._overrides_or_empty(await self._project_repo.get(project_id))
            if project_overrides:
                merged = self._merge_overrides(merged, project_overrides)
                explicit.update(project_overrides.keys())

        user_overrides = self._overrides_or_empty(await self._user_repo.get(user_id))
        if user_overrides:
            merged = self._merge_overrides(merged, user_overrides)
            explicit.update(user_overrides.keys())

        merged = self._resolve_profile(merged, explicit)

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
            max_chapter_tokens=cfg.consistency_max_chapter_tokens,
            max_kb_entries=cfg.consistency_max_kb_entries,
            max_selection_words=cfg.default_max_selection_words,
        )

    @staticmethod
    def _overrides_or_empty(entity: object) -> dict[str, object]:
        """Return the entity's overrides dict, or empty if missing/None."""

        return getattr(entity, "overrides", None) or {}

    @staticmethod
    def _resolve_profile(
        merged: TokenLimitOverrides,
        explicit: set[str],
    ) -> TokenLimitOverrides:
        """Finalise the resolved profile (CR-08 P1 D2/D3).

        * Normalise the retired ``conservative`` alias to ``balanced`` at the
          read boundary so stored legacy values never reach clients.
        * Infer ``custom`` when ``output_limit`` was explicitly set by a DB
          override without an explicit ``token_profile`` (raw-limit mode).

        Args:
            merged: The merged overrides state.
            explicit: Field names explicitly set by user/project DB layers.

        Returns:
            TokenLimitOverrides with the finalised ``token_profile``.
        """
        profile = merged.token_profile
        normalized = normalize_legacy_token_profile(profile)
        if normalized is not None:
            profile = normalized
        if (
            profile != TokenLimitProfile.CUSTOM.value
            and "token_profile" not in explicit
            and "output_limit" in explicit
        ):
            profile = TokenLimitProfile.CUSTOM.value
        if profile == merged.token_profile:
            return merged
        return replace(merged, token_profile=profile)

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
            max_chapter_tokens=cast(
                "int", overrides.get("max_chapter_tokens", base.max_chapter_tokens)
            ),
            max_kb_entries=cast("int", overrides.get("max_kb_entries", base.max_kb_entries)),
            max_selection_words=cast(
                "int", overrides.get("max_selection_words", base.max_selection_words)
            ),
        )
