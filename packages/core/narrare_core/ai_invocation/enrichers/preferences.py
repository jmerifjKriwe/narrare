"""Preference context enricher — loads user preferences into invocation context.

Implements the PreferenceContextEnricher Protocol from
:mod:`narrare_core.ai_invocation.contracts`. Queries the memory layer for
user/project preferences and injects them into
``dynamic_inputs["user_preferences"]`` for downstream prompt composition.

This is a **parallel path** to PromptComposer's preference_service
auto-injection. It does NOT replace that mechanism — it provides a
well-known key in ``dynamic_inputs`` that templates can reference.

Graceful degradation (D7): if the provider is unavailable, returns the
context unchanged with a debug log.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.memory.protocols import PreferenceProvider

logger = structlog.get_logger(__name__)

#: Well-known key for preference text in dynamic_inputs.
PREFERENCE_KEY: str = "user_preferences"


class PreferenceContextEnricherImpl:
    """Loads compact user preferences into the invocation context.

    Queries the :class:`~narrare_core.memory.protocols.PreferenceProvider`
    for the user/project pair and writes the formatted preference text
    into ``dynamic_inputs["user_preferences"]`` via immutable model_copy.

    Args:
        preference_provider: A PreferenceProvider implementation, or ``None``
            for a no-op enricher (graceful degradation).

    Implements:
        PreferenceContextEnricher Protocol.
    """

    def __init__(self, preference_provider: PreferenceProvider | None) -> None:
        self._provider = preference_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the context with user preference data.

        Reads ``user_id`` and ``project_id`` from the context, queries the
        preference provider, and injects formatted preference text into
        ``dynamic_inputs``.

        Args:
            context: The current invocation context.

        Returns:
            A new PromptInvocationContext with preference data in
            ``dynamic_inputs["user_preferences"]``, or the original context
            unchanged if enrichment is not possible.
        """
        if self._provider is None:
            logger.debug(
                "preference_enricher_noop",
                reason="no_provider",
                feature_id=context.feature_id,
            )
            return context

        if context.user_id is None or context.project_id is None:
            logger.warning(
                "preference_enricher_missing_ids",
                feature_id=context.feature_id,
                has_user_id=context.user_id is not None,
                has_project_id=context.project_id is not None,
            )
            return context

        try:
            profile = await self._provider.get_preferences(
                user_id=context.user_id,
                project_id=context.project_id,
            )
            preference_text = profile.to_prompt_text()
        except Exception:
            logger.warning(
                "preference_enricher_provider_failed",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
                exc_info=True,
            )
            return context

        logger.debug(
            "preference_enricher_success",
            feature_id=context.feature_id,
            user_id=str(context.user_id),
            preference_length=len(preference_text),
        )

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    PREFERENCE_KEY: preference_text,
                },
            },
        )
