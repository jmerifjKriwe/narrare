"""Tests for FeatureInvocationEvidence adaptive field mapping (ADR-069 D11).

Verifies that the new adaptive_source_summary + adaptive_weights fields
round-trip through domain_to_orm / orm_to_domain without data loss.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.evidence._mappers import domain_to_orm, orm_to_domain
from narrare.evidence.models import InvocationEvidenceModel
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence


def _make_evidence(
    *,
    adaptive_source_summary: dict[str, str] | None = None,
    adaptive_weights: dict[str, float] | None = None,
) -> FeatureInvocationEvidence:
    return FeatureInvocationEvidence(
        feature_id="test_feature",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status=PreferenceStatus.PROVIDED,
        kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
        final_prompt_validated=True,
        audit_state=AuditState.ADOPTED,
        invocation_id=uuid4(),
        adaptive_source_summary=adaptive_source_summary,
        adaptive_weights=adaptive_weights,
    )


class TestAdaptiveEvidenceMapping:
    """adaptive_source_summary + adaptive_weights round-trip Core ↔ ORM."""

    def test_domain_to_orm_includes_adaptive_fields(self) -> None:
        evidence = _make_evidence(
            adaptive_source_summary={"preferences": "5 events", "voices": "2 chars"},
            adaptive_weights={"preference": 0.7, "voice_fidelity": 0.9},
        )
        values = domain_to_orm(evidence)
        assert values["adaptive_source_summary"] == {
            "preferences": "5 events",
            "voices": "2 chars",
        }
        assert values["adaptive_weights"] == {
            "preference": 0.7,
            "voice_fidelity": 0.9,
        }

    def test_domain_to_orm_adaptive_fields_none_when_unset(self) -> None:
        evidence = _make_evidence()
        values = domain_to_orm(evidence)
        assert values["adaptive_source_summary"] is None
        assert values["adaptive_weights"] is None

    def test_orm_to_domain_restores_adaptive_fields(self) -> None:
        evidence = _make_evidence(
            adaptive_source_summary={"voices": "3 chars"},
            adaptive_weights={"avoidance": 1.0},
        )
        values = domain_to_orm(evidence)
        model = InvocationEvidenceModel(**values)  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.adaptive_source_summary == {"voices": "3 chars"}
        assert restored.adaptive_weights == {"avoidance": 1.0}

    def test_orm_to_domain_adaptive_fields_none_when_unset(self) -> None:
        evidence = _make_evidence()
        values = domain_to_orm(evidence)
        model = InvocationEvidenceModel(**values)  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.adaptive_source_summary is None
        assert restored.adaptive_weights is None
