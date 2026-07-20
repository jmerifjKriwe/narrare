"""Adaptive context enricher — single canonical writer of all four
adaptive prompt variables.

Consults the ``AdaptiveContextProvider`` Protocol (ADR-069 Decision 1)
and writes:

- ``dynamic_inputs["user_preferences"]``         <- AdaptiveContext.preference_text
- ``dynamic_inputs["style_constraints"]``        <- AdaptiveContext.style_constraints_text
- ``dynamic_inputs["avoidance_patterns"]``       <- AdaptiveContext.avoidance_patterns_text
- ``dynamic_inputs["character_voice_profiles"]`` <- AdaptiveContext.voice_profiles_text

Graceful degradation (ADR-038 D7):
- No provider -> return context unchanged.
- Missing user_id / project_id -> return context unchanged (warning).
- Provider raises -> return context unchanged (warning).
- AdaptiveSettings.enabled=False -> return context unchanged.
- AdaptiveContext.has_any_signal=False -> write all four keys with "".

See:
    ADR-069 Decision 1 (single canonical writer), Decision 4 (applicability),
    ADR-038 D7 (graceful degradation),
    ADR-055/057 (voice_metrics never reach generation — only
    descriptive voice_profiles_text is written here),
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation.enrichers._keys import (
    AVOIDANCE_PATTERNS_KEY,
    CHARACTER_VOICE_PROFILES_KEY,
    STYLE_CONSTRAINTS_KEY,
    USER_PREFERENCES_KEY,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.adaptive_contracts import (
        AdaptiveContextProvider,
    )
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)


class AdaptiveContextEnricher:
    """Writes all four adaptive prompt variables via immutable model_copy.

    Single canonical writer per ADR-069 Decision 1.

    Args:
        adaptive_provider: An ``AdaptiveContextProvider`` implementation,
            or ``None`` for a no-op enricher (graceful degradation when
            adaptivity is not configured — e.g., mem0 unavailable).

    Implements:
        ``ContextEnricher`` Protocol from ``ai_invocation.contracts``.
    """

    def __init__(self, adaptive_provider: AdaptiveContextProvider | None) -> None:
        self._provider = adaptive_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the context with adaptive data.

        Args:
            context: The current invocation context.

        Returns:
            A new ``PromptInvocationContext`` with all four adaptive
            ``dynamic_inputs`` keys set, or the original context
            unchanged when enrichment is not possible.
        """
        if self._provider is None:
            logger.debug(
                "adaptive_enricher_noop",
                reason="no_provider",
                feature_id=context.feature_id,
            )
            return context

        if context.user_id is None or context.project_id is None:
            logger.warning(
                "adaptive_enricher_missing_ids",
                feature_id=context.feature_id,
                has_user_id=context.user_id is not None,
                has_project_id=context.project_id is not None,
            )
            return context

        try:
            settings = await self._provider.get_settings(
                user_id=context.user_id,
                project_id=context.project_id,
            )
        except Exception:
            logger.warning(
                "adaptive_enricher_settings_failed",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
                exc_info=True,
            )
            return context

        if not settings.enabled:
            logger.debug(
                "adaptive_enricher_disabled",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
            )
            return context

        try:
            adaptive = await self._provider.get_context(
                user_id=context.user_id,
                project_id=context.project_id,
            )
        except Exception:
            logger.warning(
                "adaptive_enricher_context_failed",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
                exc_info=True,
            )
            return context

        logger.debug(
            "adaptive_enricher_success",
            feature_id=context.feature_id,
            user_id=str(context.user_id),
            has_signal=adaptive.has_any_signal,
            preference_length=len(adaptive.preference_text),
            voice_profiles_length=len(adaptive.voice_profiles_text),
            style_constraints_length=len(adaptive.style_constraints_text),
            avoidance_length=len(adaptive.avoidance_patterns_text),
        )

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    USER_PREFERENCES_KEY: adaptive.preference_text,
                    STYLE_CONSTRAINTS_KEY: adaptive.style_constraints_text,
                    AVOIDANCE_PATTERNS_KEY: adaptive.avoidance_patterns_text,
                    CHARACTER_VOICE_PROFILES_KEY: adaptive.voice_profiles_text,
                },
            },
        )
