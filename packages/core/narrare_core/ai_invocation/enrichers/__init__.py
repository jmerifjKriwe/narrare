"""Enrichers for the AI invocation pipeline.

Enrichers add runtime context to a PromptInvocationContext before
prompt composition runs. Each enricher is a focused, single-responsibility
implementation of the ContextEnricher Protocol.

See:
    ADR-038, ADR-039, INFRA-013, CONSTRAINTS.md RULE-06.
"""

from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedContextEnricher,
)
from narrare_core.ai_invocation.enrichers.preferences import (
    PreferenceContextEnricherImpl,
)

__all__ = [
    "KBSuggestedContextEnricher",
    "PreferenceContextEnricherImpl",
]
