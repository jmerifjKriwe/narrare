"""Evidence building helpers for the invocation pipeline.

Pure functions that construct :class:`FeatureInvocationEvidence` from
pipeline state. Extracted from :mod:`pipeline` per RULE-04.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-04/RULE-06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
)
from narrare_core.ai_invocation.models import (
    FeatureInvocationEvidence,
    PromptInvocationContext,
    ValidationResult,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import PreparedInvocation


def build_invocation_evidence(
    context: PromptInvocationContext,
    prepared: PreparedInvocation | None,
    final_validation: ValidationResult,
    final_validator_ran: bool,
) -> FeatureInvocationEvidence:
    """Build a privacy-safe evidence record from pipeline state.

    Args:
        context: The invocation context that produced the prompt.
        prepared: Optional prepared invocation from the prepare phase.
        final_validation: Final prompt validation result.
        final_validator_ran: Whether the final validator actually ran.

    Returns:
        FeatureInvocationEvidence with all metadata populated.
    """
    preference_status = _determine_preference_status(context)
    kb_suggested_status = _determine_kb_suggested_status(context)

    # Combine validation errors from both phases
    variable_errors: tuple[str, ...] = ()
    if prepared is not None:
        variable_errors = prepared.validation.errors
    all_errors = variable_errors + final_validation.errors

    # Determine audit state
    audit_state = _determine_audit_state(
        variable_validation=prepared.validation if prepared else None,
        final_validation=final_validation,
        final_validator_ran=final_validator_ran,
    )

    # Budget profile from prepared result
    budget_profile: str | None = None
    if prepared is not None and prepared.budget is not None:
        budget_profile = prepared.budget.budget.profile

    # Whether final validation ran and passed
    final_validated = final_validator_ran and final_validation.is_valid

    return FeatureInvocationEvidence(
        feature_id=context.feature_id,
        intent=context.intent.value,
        mode=context.mode,
        prompt_route=f"{context.intent.value}/{context.mode or 'default'}",
        preference_status=preference_status,
        kb_suggested_status=kb_suggested_status,
        output_budget_profile=budget_profile,
        final_prompt_validated=final_validated,
        validation_errors=all_errors,
        audit_state=audit_state,
    )


def _determine_preference_status(
    context: PromptInvocationContext,
) -> PreferenceStatus:
    """Determine preference delivery status from context."""
    if context.dynamic_inputs.get("user_preferences"):
        return PreferenceStatus.PROVIDED
    if (
        context.adoption_policy is None
        or context.adoption_policy.preference_requirement == PreferenceRequirement.NOT_APPLICABLE
    ):
        return PreferenceStatus.NOT_APPLICABLE
    return PreferenceStatus.MISSING


def _determine_kb_suggested_status(
    context: PromptInvocationContext,
) -> KBSuggestedStatus:
    """Determine KB-suggested delivery status from context."""
    if context.dynamic_inputs.get("kb_suggested"):
        return KBSuggestedStatus.PROVIDED
    if (
        context.adoption_policy is None
        or context.adoption_policy.kb_suggested_requirement == KBSuggestedRequirement.NOT_APPLICABLE
    ):
        return KBSuggestedStatus.NOT_APPLICABLE
    return KBSuggestedStatus.MISSING


def _determine_audit_state(
    variable_validation: ValidationResult | None,
    final_validation: ValidationResult,
    final_validator_ran: bool,
) -> AuditState:
    """Compute audit state from validation results.

    Args:
        variable_validation: Variable validation result, or None if no
            validator was configured.
        final_validation: Final prompt validation result.
        final_validator_ran: Whether the final validator actually ran.

    Returns:
        AuditState: BLOCKED if any validation failed, RUNTIME_VERIFIED
        if all configured validators ran and passed, STATIC_VERIFIED
        otherwise.
    """
    has_failure = (variable_validation is not None and not variable_validation.is_valid) or (
        final_validator_ran and not final_validation.is_valid
    )
    if has_failure:
        return AuditState.BLOCKED

    variable_ran_and_passed = variable_validation is not None and variable_validation.is_valid
    final_ran_and_passed = final_validator_ran and final_validation.is_valid
    any_ran = variable_validation is not None or final_validator_ran

    if any_ran and variable_ran_and_passed and final_ran_and_passed:
        return AuditState.RUNTIME_VERIFIED

    return AuditState.STATIC_VERIFIED
