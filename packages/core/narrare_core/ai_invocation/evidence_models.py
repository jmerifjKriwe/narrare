"""Evidence record model for AI invocation adoption (ADR-038, ADR-045).

Contains the privacy-safe evidence record that proves an invocation
satisfied adoption requirements without exposing raw prompt text.

Privacy guarantee: :class:`FeatureInvocationEvidence` must NEVER contain
raw prompt text or user prose. Use structured metadata, statuses, hashes,
and counts only.

See:
    ADR-038, ADR-045, CONSTRAINTS.md RULE-02/RULE-03/RULE-20.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from narrare_core.ai_invocation._enums import (
        AuditState,
        KBSuggestedStatus,
        PreferenceStatus,
        VoiceProfileStatus,
    )

__all__ = ["FeatureInvocationEvidence"]


class FeatureInvocationEvidence(BaseModel):
    """Privacy-safe evidence record for an AI invocation.

    Proves that an invocation satisfied adoption requirements without
    exposing raw prompt text or user prose. Contains only identifiers,
    statuses, booleans, and structured metadata.
    """

    model_config = ConfigDict(frozen=True)

    invocation_id: UUID | None = None
    # ADR-070: project scope (set on write from context.project_id) and
    # created_at (READ-ONLY — DB-stamped on INSERT; populated by orm_to_domain
    # on reads, omitted by domain_to_orm on writes).
    novel_id: UUID | None = None
    created_at: datetime | None = None
    feature_id: str = Field(min_length=1)
    intent: str = Field(min_length=1, description="Intent value string.")
    mode: str | None = None
    prompt_route: str = Field(min_length=1, description="Resolved prompt route.")
    preference_status: PreferenceStatus
    kb_suggested_status: KBSuggestedStatus
    voice_profile_status: VoiceProfileStatus | None = None
    output_budget_profile: str | None = None
    final_prompt_validated: bool
    validation_errors: tuple[str, ...] = ()
    audit_state: AuditState
    prepared_context_fingerprint: str | None = None
    prompt_fingerprint: str | None = None
    budget_decision_fingerprint: str | None = None
    model_call_marker: str | None = None
    streaming: bool | None = None
    manual_injection_exception: str | None = None
    # ADR-069 D11: adaptive context provenance + weights (NULL when adaptive
    # context is disabled or unavailable — graceful degradation per RULE-11).
    adaptive_source_summary: dict[str, str] | None = None
    adaptive_weights: dict[str, float] | None = None


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs after moving type imports under TYPE_CHECKING."""
    from datetime import datetime
    from uuid import UUID

    from narrare_core.ai_invocation._enums import (
        AuditState,
        KBSuggestedStatus,
        PreferenceStatus,
        VoiceProfileStatus,
    )

    FeatureInvocationEvidence.model_rebuild(
        _types_namespace={
            "datetime": datetime,
            "UUID": UUID,
            "AuditState": AuditState,
            "KBSuggestedStatus": KBSuggestedStatus,
            "PreferenceStatus": PreferenceStatus,
            "VoiceProfileStatus": VoiceProfileStatus,
        },
    )


_rebuild_forward_refs()
