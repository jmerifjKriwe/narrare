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
    VoiceProfileStatus,
)
from narrare_core.ai_invocation.budgets import (
    IntentOutputBudgetResolverImpl,
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.consistency import (
    ConsistencyStatus,
    EntityType,
    EntityTypeCheck,
    KBConsistencyCheck,
    KBConsistencyResult,
)
from narrare_core.ai_invocation.contracts import (
    ContextEnricher,
    FeatureInvocationEvidenceSink,
    FinalPromptValidator,
    IntentOutputBudgetResolver,
    PreferenceContextEnricher,
    ProfileProvider,
    RuntimeVariableValidator,
)
from narrare_core.ai_invocation.evidence import LoggingEvidenceSink
from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
from narrare_core.ai_invocation.models import (
    AdoptionPolicy,
    ContextEnrichmentResult,
    FeatureInvocationEvidence,
    InvocationWarning,
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.ai_invocation.non_writing_adapter import (
    ComposedInvocation,
    compose_invocation,
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
    "ComposedInvocation",
    "ConsistencyStatus",
    "ContextEnricher",
    "ContextEnrichmentResult",
    "EntityType",
    "EntityTypeCheck",
    "FeatureInvocationEvidence",
    "FeatureInvocationEvidenceSink",
    "FinalPromptValidator",
    "FinalPromptValidatorImpl",
    "FinalizedInvocation",
    "IntentOutputBudgetResolver",
    "IntentOutputBudgetResolverImpl",
    "InvocationPipeline",
    "InvocationWarning",
    "KBConsistencyCheck",
    "KBConsistencyResult",
    "KBSuggestedRequirement",
    "KBSuggestedStatus",
    "LoggingEvidenceSink",
    "ManualInjectionDeclaration",
    "OutputBudget",
    "OutputBudgetDecision",
    "PreferenceContextEnricher",
    "PreferenceRequirement",
    "PreferenceStatus",
    "PreparedInvocation",
    "ProfileProvider",
    "PromptInvocationContext",
    "RuntimeVariableValidator",
    "RuntimeVariableValidatorImpl",
    "ValidationResult",
    "ValidationStatus",
    "VoiceProfileStatus",
    "compose_invocation",
]
