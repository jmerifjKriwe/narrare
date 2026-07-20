"""Enrichers for the AI invocation pipeline.

Enrichers add runtime context to a PromptInvocationContext before
prompt composition runs. Each enricher is a focused, single-responsibility
implementation of the ContextEnricher Protocol.

See:
    ADR-038, ADR-039, ADR-040, ADR-069 (Decision 1 enricher swap),
    INFRA-013, CONSTRAINTS.md RULE-06.
"""

from narrare_core.ai_invocation.enrichers.adaptive import (
    AdaptiveContextEnricher,
)
from narrare_core.ai_invocation.enrichers.consistency import (
    KBConsistencyEnricher,
)
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedContextEnricher,
)

__all__ = [
    "AdaptiveContextEnricher",
    "KBConsistencyEnricher",
    "KBSuggestedContextEnricher",
]
