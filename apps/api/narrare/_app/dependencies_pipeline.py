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

    Assembles the pipeline with all P0.3 + ADR-069 components:
    - RuntimeVariableValidatorImpl (pre-composition checks)
    - IntentOutputBudgetResolverImpl (budget resolution)
    - FinalPromptValidatorImpl (post-composition checks)
    - AdaptiveContextEnricher (ADR-069 — writes all four adaptive
      prompt variables: user_preferences, style_constraints,
      avoidance_patterns, character_voice_profiles; replaces the
      legacy single-variable PreferenceContextEnricherImpl)
    - KBSuggestedContextEnricher (backed by KB repository)

    Note:
        The ``evidence_sink`` is resolved by ``get_evidence_sink()`` based on
        the ``use_persistent_evidence`` setting: ``PersistentEvidenceSink``
        (PostgreSQL) when enabled, ``LoggingEvidenceSink`` otherwise (default).

        The ``KBSuggestedProviderImpl`` uses ``get_session_factory()`` to
        create per-call database sessions because this function is cached
        (singleton) and cannot depend on request-scoped sessions.

        Phase 2 boundary (ADR-069): ``AdaptiveContextProviderImpl`` is
        wired with ``profile_provider=None`` — no Backend ProfileProvider
        exists yet (Phase 4 wires it). The adaptive enricher still writes
        three of four variables (user_preferences, style_constraints,
        avoidance_patterns) from PreferenceProfile data;
        character_voice_profiles stays empty until Phase 4.
    """
    from narrare._app.database import get_session_factory
    from narrare.adaptive.adaptive_context_provider import (
        AdaptiveContextProviderImpl,
    )
    from narrare.kb.kb_suggested_provider import KBSuggestedProviderImpl
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
        RuntimeVariableValidatorImpl,
    )
    from narrare_core.ai_invocation.enrichers import (
        AdaptiveContextEnricher,
        KBSuggestedContextEnricher,
    )

    preference_service = _get_preference_service_instance()

    # Adaptive enricher (ADR-069) — single canonical writer of all four
    # adaptive prompt variables. Phase 2 wires profile_provider=None;
    # Phase 4 will wire the production Backend ProfileProvider.
    adaptive_provider = AdaptiveContextProviderImpl(
        preference_provider=preference_service,
        profile_provider=None,
    )
    enrichers: list[ContextEnricher] = [
        AdaptiveContextEnricher(adaptive_provider=adaptive_provider),
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
