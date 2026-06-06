"""AI Invocation Adoption Contract (ADR-038, INFRA-013).

Runtime invocation types, protocols, and evidence for AI feature
adoption. Defines the boundary between feature services and the
prompt/agent runtime.

This module is the public entry point for the ``ai_invocation`` package.
Import types and protocols from here, not from internal modules.
"""

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
    ValidationStatus,
)
from narrare_core.ai_invocation.budgets import (
    IntentOutputBudgetResolverImpl,
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.contracts import (
    ContextEnricher,
    FeatureInvocationEvidenceSink,
    FinalPromptValidator,
    IntentOutputBudgetResolver,
    PreferenceContextEnricher,
    RuntimeVariableValidator,
)
from narrare_core.ai_invocation.evidence import LoggingEvidenceSink
from narrare_core.ai_invocation.models import (
    AdoptionPolicy,
    ContextEnrichmentResult,
    FeatureInvocationEvidence,
    InvocationWarning,
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.ai_invocation.pipeline import (
    FinalizedInvocation,
    InvocationPipeline,
    PreparedInvocation,
)
from narrare_core.ai_invocation.validators import (
    FinalPromptValidatorImpl,
    RuntimeVariableValidatorImpl,
)

__all__ = [
    "AdoptionPolicy",
    "AuditState",
    "ContextEnricher",
    "ContextEnrichmentResult",
    "FeatureInvocationEvidence",
    "FeatureInvocationEvidenceSink",
    "FinalPromptValidator",
    "FinalPromptValidatorImpl",
    "FinalizedInvocation",
    "IntentOutputBudgetResolver",
    "IntentOutputBudgetResolverImpl",
    "InvocationPipeline",
    "InvocationWarning",
    "KBSuggestedRequirement",
    "KBSuggestedStatus",
    "LoggingEvidenceSink",
    "OutputBudget",
    "OutputBudgetDecision",
    "PreferenceContextEnricher",
    "PreferenceRequirement",
    "PreferenceStatus",
    "PreparedInvocation",
    "PromptInvocationContext",
    "RuntimeVariableValidator",
    "RuntimeVariableValidatorImpl",
    "ValidationResult",
    "ValidationStatus",
]
