"""AI invocation value objects and data models.

Defines the runtime data types for the AI invocation adoption contract
(ADR-038, INFRA-013). These types carry request-scoped data through the
enrichment, validation, budget, and evidence pipeline.

Enums live in :mod:`_enums`, output budget types in :mod:`budgets`.

Privacy guarantee: :class:`FeatureInvocationEvidence` must NEVER contain
raw prompt text or user prose. Use structured metadata, statuses, hashes,
and counts only.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-02/RULE-03/RULE-20.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
    ValidationStatus,
    VoiceProfileStatus,
)
from narrare_core.ai_invocation.budgets import OutputBudget, OutputBudgetDecision
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

# Re-export enums and budget types so public imports stay in __init__.py
__all__ = [
    "AdoptionPolicy",
    "AuditState",
    "ContextEnrichmentResult",
    "FeatureInvocationEvidence",
    "InvocationWarning",
    "KBSuggestedRequirement",
    "KBSuggestedStatus",
    "OutputBudget",
    "OutputBudgetDecision",
    "PreferenceRequirement",
    "PreferenceStatus",
    "PromptInvocationContext",
    "ValidationResult",
    "ValidationStatus",
    "VoiceProfileStatus",
]


class InvocationWarning(BaseModel):
    """Non-blocking warning discovered during invocation validation.

    Warnings indicate gaps or concerns that do not block the invocation
    but should be tracked for adoption audit purposes.
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1, description="Machine-readable warning code.")
    message: str = Field(min_length=1, description="Human-readable description.")
    field: str | None = Field(
        default=None,
        description="Optional field name that triggered the warning.",
    )


class AdoptionPolicy(BaseModel):
    """Defines what a feature mode requires for adoption claims.

    Each feature mode declares its adoption requirements. A feature can
    only claim ``adopted`` when both static and runtime evidence satisfy
    the declared policy.
    """

    model_config = ConfigDict(frozen=True)

    preference_requirement: PreferenceRequirement = PreferenceRequirement.NOT_APPLICABLE
    kb_suggested_requirement: KBSuggestedRequirement = KBSuggestedRequirement.NOT_APPLICABLE
    requires_output_budget: bool = True
    requires_final_validation: bool = True


class ValidationResult(BaseModel):
    """Outcome of a validation check (variable or final prompt).

    Validation failures block the invocation; warnings are recorded but
    do not block.
    """

    model_config = ConfigDict(frozen=True)

    status: ValidationStatus
    errors: tuple[str, ...] = ()
    warnings: tuple[InvocationWarning, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Whether the validation passed."""
        return self.status == ValidationStatus.PASS


class ContextEnrichmentResult(BaseModel):
    """Result of running enrichers against an invocation context.

    Records which fields were enriched, where the data came from, and
    any warnings encountered during enrichment.
    """

    model_config = ConfigDict(frozen=True)

    enriched_fields: frozenset[str] = frozenset()
    enrichment_sources: tuple[tuple[str, str], ...] = ()
    warnings: tuple[InvocationWarning, ...] = ()


class PromptInvocationContext(BaseModel):
    """Typed context for a single AI invocation.

    Carries request-scoped data through the enrichment, validation,
    budget resolution, and evidence pipeline. Feature services create
    this before every AI call.

    Immutable — enrichers return new instances via
    ``model_copy(update={...})``.
    """

    model_config = ConfigDict(frozen=True)

    feature_id: str = Field(min_length=1, description="Feature identifier.")
    intent: LLMIntent
    mode: str | None = Field(default=None, description="Mode within the feature.")
    user_id: object | None = None
    project_id: object | None = None
    invocation_id: UUID | None = None
    language: str = Field(default="en", min_length=2, max_length=5)
    output_language: str | None = None
    streaming: bool = False
    required_features: frozenset[str] = frozenset()
    optional_features: frozenset[str] = frozenset()
    dynamic_inputs: dict[str, str] = Field(default_factory=dict)
    adoption_policy: AdoptionPolicy | None = None
    prompt_context: PromptContext | None = None


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs after moving type imports under TYPE_CHECKING."""
    from uuid import UUID as _UUID

    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    PromptInvocationContext.model_rebuild(
        _types_namespace={
            "UUID": _UUID,
            "LLMIntent": LLMIntent,
            "PromptContext": PromptContext,
        },
    )


_rebuild_forward_refs()
