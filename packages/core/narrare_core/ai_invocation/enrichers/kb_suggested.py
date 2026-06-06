"""KB-suggested context enricher — adds KB-suggested data to invocation context.

Implements the ContextEnricher Protocol from
:mod:`narrare_core.ai_invocation.contracts`. Optionally queries a KB provider
for suggested context and injects it into ``dynamic_inputs["kb_suggested"]``
for downstream prompt composition and budget resolution.

This enricher runs **before** the budget resolver so that the resolver can
decide whether to keep (token budget sufficient) or reject (token budget
exceeded) the KB-suggested content.

Graceful degradation: if the provider is unavailable or no provider is
configured, uses a placeholder or returns context unchanged.

See:
    ADR-039, ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

from narrare_core.ai_invocation._enums import KBSuggestedRequirement

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)

#: Well-known key for KB-suggested text in dynamic_inputs.
KB_SOURCE_KEY: str = "kb_suggested"

#: Placeholder text used when no KB provider is configured.
_PLACEHOLDER_TEXT: str = "[KB context will be provided in a future update]"


class KBSuggestedProvider(Protocol):
    """Provides KB-suggested context for an AI invocation.

    Implementations query the knowledge base for relevant context
    (characters, locations, factions, plot threads, etc.) based on
    the invocation parameters.

    This protocol is intentionally broad — actual KB querying logic
    will be refined in P2+.
    """

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> str:
        """Return KB-suggested context text for the given parameters.

        Args:
            user_id: The user identifier, or None.
            project_id: The project identifier, or None.
            intent: The invocation intent value, or None.
            mode: The invocation mode, or None.

        Returns:
            Formatted KB context text to inject into dynamic_inputs.
        """
        ...


class KBSuggestedContextEnricher:
    """Adds KB-suggested context to the invocation context.

    Checks the adoption policy to determine whether kb_suggested is
    applicable for the current invocation. If applicable, populates
    ``dynamic_inputs["kb_suggested"]`` with content from the provider
    or a placeholder.

    The enricher returns a new :class:`PromptInvocationContext` via
    ``model_copy`` — the original context is never mutated (immutability
    guarantee).

    Implements:
        ContextEnricher Protocol.

    Args:
        kb_provider: A KBSuggestedProvider implementation, or ``None``
            for graceful degradation (uses placeholder text).
    """

    def __init__(self, kb_provider: KBSuggestedProvider | None = None) -> None:
        self._provider = kb_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the context with KB-suggested data.

        Args:
            context: The current invocation context.

        Returns:
            A new PromptInvocationContext with KB-suggested data in
            ``dynamic_inputs["kb_suggested"]``, or the original context
            unchanged if kb_suggested is not applicable.
        """
        # Check adoption policy — if not applicable, skip enrichment
        policy = context.adoption_policy
        if (
            policy is None
            or policy.kb_suggested_requirement == KBSuggestedRequirement.NOT_APPLICABLE
        ):
            logger.debug(
                "kb_suggested_enricher_skipped",
                reason="not_applicable",
                feature_id=context.feature_id,
            )
            return context

        # Skip if already populated (defensive — prevents double-enrichment)
        if KB_SOURCE_KEY in context.dynamic_inputs:
            logger.debug(
                "kb_suggested_enricher_already_populated",
                feature_id=context.feature_id,
            )
            return context

        try:
            if self._provider is not None:
                suggested_text = await self._provider.get_suggested_context(
                    user_id=context.user_id,
                    project_id=context.project_id,
                    intent=context.intent.value if context.intent else None,
                    mode=context.mode,
                )
            else:
                suggested_text = _PLACEHOLDER_TEXT

            logger.debug(
                "kb_suggested_enricher_success",
                feature_id=context.feature_id,
                kb_suggested_length=len(suggested_text),
            )
        except Exception:
            logger.warning(
                "kb_suggested_enricher_provider_failed",
                feature_id=context.feature_id,
                exc_info=True,
            )
            return context

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    KB_SOURCE_KEY: suggested_text,
                },
            },
        )
