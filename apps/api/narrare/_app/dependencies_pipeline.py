"""Invocation Pipeline singleton.

Extracted from ``dependencies.py`` for RULE-04 modularisation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from narrare._app.dependencies_prompts import (
    _get_preference_service_instance,  # pyright: ignore[reportPrivateUsage]
)
from narrare.evidence.dependencies import get_evidence_sink

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
    - KBSuggestedContextEnricher (backed by KB repository)

    Note:
        The ``evidence_sink`` is resolved by ``get_evidence_sink()`` based on
        the ``use_persistent_evidence`` setting: ``PersistentEvidenceSink``
        (PostgreSQL) when enabled, ``LoggingEvidenceSink`` otherwise (default).

        The ``KBSuggestedProviderImpl`` uses ``get_session_factory()`` to
        create per-call database sessions because this function is cached
        (singleton) and cannot depend on request-scoped sessions.
    """
    from narrare._app.database import get_session_factory
    from narrare.kb.kb_suggested_provider import KBSuggestedProviderImpl
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
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
    # Uses get_session_factory() to avoid coupling the singleton pipeline
    # to request-scoped sessions — each get_suggested_context() call
    # creates its own session (lightweight, read-only query).
    kb_provider = KBSuggestedProviderImpl(session_factory=get_session_factory())
    enrichers.append(KBSuggestedContextEnricher(kb_provider=kb_provider))

    return InvocationPipeline(
        enrichers=enrichers,
        variable_validator=RuntimeVariableValidatorImpl(),
        budget_resolver=IntentOutputBudgetResolverImpl(),
        final_validator=FinalPromptValidatorImpl(),
        evidence_sink=get_evidence_sink(),
    )
