"""ORM ↔ Domain mappers for ``invocation_evidence`` (extracted for RULE-04).

Pure transform functions between ``InvocationEvidenceModel`` (ORM) and
``FeatureInvocationEvidence`` (Core domain). Extracted from
``repository.py`` to keep that file under the 250-line repository cap.

See: ADR-042, CONSTRAINTS.md RULE-04 / RULE-14.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.evidence.models import InvocationEvidenceModel
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence


def domain_to_orm(evidence: FeatureInvocationEvidence) -> dict[str, object]:
    """Convert a domain evidence record to ORM column values.

    Args:
        evidence: Privacy-safe evidence record from an AI invocation.

    Returns:
        Dict of ORM column names to values.
    """
    return {
        "feature_id": evidence.feature_id,
        "intent": evidence.intent,
        "mode": evidence.mode,
        "prompt_route": evidence.prompt_route,
        "preference_status": str(evidence.preference_status),
        "kb_suggested_status": str(evidence.kb_suggested_status),
        "voice_profile_status": str(evidence.voice_profile_status)
        if evidence.voice_profile_status
        else None,
        "output_budget_profile": evidence.output_budget_profile,
        "final_prompt_validated": evidence.final_prompt_validated,
        "validation_errors": list(evidence.validation_errors),
        "audit_state": str(evidence.audit_state),
        # streaming: ORM column is non-nullable; coerce None → False.
        "streaming": evidence.streaming if evidence.streaming is not None else False,
        # ADR-045 §2: correlation fields.
        "invocation_id": evidence.invocation_id,
        # ADR-070: project scope (write path). created_at is intentionally
        # omitted — the DB column has server_default=func.now().
        "novel_id": evidence.novel_id,
        "prepared_context_fingerprint": evidence.prepared_context_fingerprint,
        "prompt_fingerprint": evidence.prompt_fingerprint,
        "budget_decision_fingerprint": evidence.budget_decision_fingerprint,
        "model_call_marker": evidence.model_call_marker,
        "manual_injection_exception": evidence.manual_injection_exception,
        # ADR-069 D11: adaptive context provenance + resolved weights.
        "adaptive_source_summary": evidence.adaptive_source_summary,
        "adaptive_weights": evidence.adaptive_weights,
    }


def orm_to_domain(model: InvocationEvidenceModel) -> FeatureInvocationEvidence:
    """Convert an ORM model instance to a domain evidence record.

    Args:
        model: ORM model instance from the database.

    Returns:
        ``FeatureInvocationEvidence`` domain object.
    """
    from narrare_core.ai_invocation.models import (
        AuditState,
        FeatureInvocationEvidence,
        KBSuggestedStatus,
        PreferenceStatus,
        VoiceProfileStatus,
    )

    errors_raw: list[str] | list[object] = (
        model.validation_errors if model.validation_errors is not None else []
    )
    return FeatureInvocationEvidence(
        feature_id=model.feature_id,
        intent=model.intent,
        mode=model.mode,
        prompt_route=model.prompt_route,
        preference_status=PreferenceStatus(model.preference_status),
        kb_suggested_status=KBSuggestedStatus(model.kb_suggested_status),
        voice_profile_status=VoiceProfileStatus(model.voice_profile_status)
        if model.voice_profile_status
        else None,
        output_budget_profile=model.output_budget_profile,
        final_prompt_validated=model.final_prompt_validated,
        validation_errors=tuple(str(e) for e in errors_raw),
        audit_state=AuditState(model.audit_state),
        streaming=model.streaming,
        # ADR-045 §2: correlation fields.
        invocation_id=model.invocation_id,
        # ADR-070: project scope + read-only DB-stamped timestamp.
        novel_id=model.novel_id,
        created_at=model.created_at,
        prepared_context_fingerprint=model.prepared_context_fingerprint,
        prompt_fingerprint=model.prompt_fingerprint,
        budget_decision_fingerprint=model.budget_decision_fingerprint,
        model_call_marker=model.model_call_marker,
        manual_injection_exception=model.manual_injection_exception,
        # ADR-069 D11: adaptive context provenance + resolved weights.
        adaptive_source_summary=model.adaptive_source_summary,
        adaptive_weights=model.adaptive_weights,
    )


__all__ = [
    "domain_to_orm",
    "orm_to_domain",
]
