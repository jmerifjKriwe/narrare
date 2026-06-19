"""Evidence building helpers for the invocation pipeline.

Pure functions that construct :class:`FeatureInvocationEvidence` from
pipeline state. Extracted from :mod:`pipeline` per RULE-04.

ADR-045 Phase 3 correlation fields (invocation_id, streaming, and the
three privacy-safe fingerprints) are populated here from the canonical
:mod:`correlation` helpers. The fingerprints are one-way digests over
*structural* metadata only (keys, lengths, profile names) — never raw
prompt text or user prose.

See:
    ADR-038, ADR-045, INFRA-013, CONSTRAINTS.md RULE-04/RULE-06/RULE-20.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
)
from narrare_core.ai_invocation.correlation import (
    fingerprint_budget_decision,
    fingerprint_prepared_context,
    fingerprint_prompt,
)
from narrare_core.ai_invocation.models import (
    FeatureInvocationEvidence,
    PromptInvocationContext,
    ValidationResult,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import PreparedInvocation
    from narrare_core.prompts.composer import ComposedPrompt


def build_invocation_evidence(
    context: PromptInvocationContext,
    prepared: PreparedInvocation | None,
    final_validation: ValidationResult,
    final_validator_ran: bool,
    *,
    prompt: ComposedPrompt | None = None,
) -> FeatureInvocationEvidence:
    """Build a privacy-safe evidence record from pipeline state.

    Populates ADR-045 Phase 3 correlation fields:

    - ``invocation_id``: ``context.invocation_id`` (generated if absent) so
      evidence can be correlated across prepare → compose → model boundary.
    - ``streaming``: ``context.streaming``.
    - ``prepared_context_fingerprint``: digest from
      :func:`correlation.fingerprint_prepared_context` over the *prepared*
      (enriched) context's dynamic-input keys/counts — not their values.
    - ``prompt_fingerprint``: digest from :func:`correlation.fingerprint_prompt`
      when a ``prompt`` is supplied (lengths + presence, never raw text).
    - ``budget_decision_fingerprint``: digest from
      :func:`correlation.fingerprint_budget_decision` (profile + max tokens +
      source, never the free-form reason).

    Args:
        context: The invocation context that produced the prompt.
        prepared: Optional prepared invocation from the prepare phase.
        final_validation: Final prompt validation result.
        final_validator_ran: Whether the final validator actually ran.
        prompt: Optional composed prompt, used only to derive the
            privacy-safe prompt fingerprint. Never stored.

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

    # --- ADR-045 Phase 3: correlation fields ---------------------------
    # invocation_id: preserve the caller's id, else mint one so every
    # evidence record is correlatable even when the caller forgot to set it.
    invocation_id: UUID = context.invocation_id or uuid4()

    # Fingerprint the *prepared* (enriched) context when available, since
    # that is what actually flowed into prompt composition. Falls back to
    # the bare invocation context when prepare() did not run.
    fingerprinted_context = prepared.context if prepared is not None else context
    prepared_context_fingerprint = fingerprint_prepared_context(fingerprinted_context).digest

    prompt_fingerprint = fingerprint_prompt(prompt).digest if prompt is not None else None

    budget_fp: str | None = None
    if prepared is not None and prepared.budget is not None:
        budget_decision_fp = fingerprint_budget_decision(prepared.budget)
        if budget_decision_fp is not None:
            budget_fp = budget_decision_fp.digest

    return FeatureInvocationEvidence(
        invocation_id=invocation_id,
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
        prepared_context_fingerprint=prepared_context_fingerprint,
        prompt_fingerprint=prompt_fingerprint,
        budget_decision_fingerprint=budget_fp,
        streaming=context.streaming,
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
