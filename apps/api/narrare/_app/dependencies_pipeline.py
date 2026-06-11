"""Invocation Pipeline singleton.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from narrare._app.dependencies_prompts import (
    _get_preference_service_instance,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation import ContextEnricher
    from narrare_core.ai_invocation.pipeline import InvocationPipeline


@lru_cache
def get_invocation_pipeline() -> InvocationPipeline:
    """Create InvocationPipeline with production implementations.

    Assembles the pipeline with all P0.3 components:
    - RuntimeVariableValidatorImpl (pre-composition checks)
    - IntentOutputBudgetResolverImpl (budget resolution)
    - FinalPromptValidatorImpl (post-composition checks)
    - PreferenceContextEnricherImpl (if preference service available)

    Note:
        ``evidence_sink`` is a :class:`LoggingEvidenceSink` that records
        structured logs for each invocation. Can be disabled via log level.
    """
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
        LoggingEvidenceSink,
        RuntimeVariableValidatorImpl,
    )
    from narrare_core.ai_invocation.enrichers import (
        KBSuggestedContextEnricher,
        PreferenceContextEnricherImpl,
    )

    preference_service = _get_preference_service_instance()

    # Preference enricher is always wired — graceful degradation via None
    # provider (returns context unchanged, preference_status=MISSING).
    enrichers: list[ContextEnricher] = [
        PreferenceContextEnricherImpl(preference_provider=preference_service),
    ]

    # KB-suggested enricher runs before budget resolution so the resolver
    # can decide whether token budget allows KB context inclusion.
    enrichers.append(KBSuggestedContextEnricher(kb_provider=None))

    return InvocationPipeline(
        enrichers=enrichers,
        variable_validator=RuntimeVariableValidatorImpl(),
        budget_resolver=IntentOutputBudgetResolverImpl(),
        final_validator=FinalPromptValidatorImpl(),
        evidence_sink=LoggingEvidenceSink(),
    )
