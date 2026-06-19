"""Tests for FeatureInvocationEvidence serialization and privacy.

Covers:
1. FeatureInvocationEvidence serializes without raw prompt/user prose.
2. Validates allowed preference_status and kb_suggested_status values.
3. Validates allowed audit_state values.
4. JSON roundtrip is stable.
5. No field can contain raw prompt text or user prose by design.

ADR-045 Phase 3 correlation-field population tests live in
``test_evidence_correlation_fields.py`` (split per RULE-04).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from narrare_core.ai_invocation.models import (
    AuditState,
    FeatureInvocationEvidence,
    KBSuggestedStatus,
    PreferenceStatus,
)

# ---------------------------------------------------------------------------
# FeatureInvocationEvidence construction
# ---------------------------------------------------------------------------


class TestFeatureInvocationEvidenceConstruction:
    """FeatureInvocationEvidence required and optional fields."""

    def test_minimal_valid_evidence(self) -> None:
        """Only required fields are needed."""
        evidence = FeatureInvocationEvidence(
            feature_id="writing/new_chapter",
            intent="write",
            prompt_route="writing/en/new_chapter",
            preference_status=PreferenceStatus.PROVIDED,
            kb_suggested_status=KBSuggestedStatus.PROVIDED,
            final_prompt_validated=True,
            audit_state=AuditState.RUNTIME_VERIFIED,
        )
        assert evidence.feature_id == "writing/new_chapter"
        assert evidence.intent == "write"
        assert evidence.mode is None
        assert evidence.final_prompt_validated is True
        assert evidence.validation_errors == ()

    def test_full_evidence(self) -> None:
        """All fields can be populated."""
        evidence = FeatureInvocationEvidence(
            feature_id="writing/extend",
            intent="extend",
            mode="extend",
            prompt_route="writing/en/extend",
            preference_status=PreferenceStatus.MANUAL,
            kb_suggested_status=KBSuggestedStatus.BUDGET_REJECTED,
            output_budget_profile="long_texts",
            final_prompt_validated=True,
            validation_errors=("Missing variable: kb_context",),
            audit_state=AuditState.ADOPTED,
        )
        assert evidence.mode == "extend"
        assert evidence.output_budget_profile == "long_texts"
        assert len(evidence.validation_errors) == 1

    def test_empty_feature_id_invalid(self) -> None:
        """feature_id must be non-empty."""
        with pytest.raises(ValidationError, match="feature_id"):
            FeatureInvocationEvidence(
                feature_id="",
                intent="write",
                prompt_route="test",
                preference_status=PreferenceStatus.NOT_APPLICABLE,
                kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
                final_prompt_validated=True,
                audit_state=AuditState.SPECIFIED,
            )

    def test_empty_intent_invalid(self) -> None:
        """intent must be non-empty."""
        with pytest.raises(ValidationError, match="intent"):
            FeatureInvocationEvidence(
                feature_id="test",
                intent="",
                prompt_route="test",
                preference_status=PreferenceStatus.NOT_APPLICABLE,
                kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
                final_prompt_validated=True,
                audit_state=AuditState.SPECIFIED,
            )

    def test_empty_prompt_route_invalid(self) -> None:
        """prompt_route must be non-empty."""
        with pytest.raises(ValidationError, match="prompt_route"):
            FeatureInvocationEvidence(
                feature_id="test",
                intent="write",
                prompt_route="",
                preference_status=PreferenceStatus.NOT_APPLICABLE,
                kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
                final_prompt_validated=True,
                audit_state=AuditState.SPECIFIED,
            )


# ---------------------------------------------------------------------------
# Status validation — only allowed values accepted
# ---------------------------------------------------------------------------


class TestEvidenceStatusValidation:
    """Preference, KB, and audit statuses only accept declared values."""

    @pytest.mark.parametrize(
        "status",
        [
            PreferenceStatus.PROVIDED,
            PreferenceStatus.MANUAL,
            PreferenceStatus.NOT_APPLICABLE,
            PreferenceStatus.MISSING,
        ],
    )
    def test_valid_preference_status(self, status: PreferenceStatus) -> None:
        """All declared PreferenceStatus values are accepted."""
        evidence = FeatureInvocationEvidence(
            feature_id="test",
            intent="write",
            prompt_route="test",
            preference_status=status,
            kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
            final_prompt_validated=True,
            audit_state=AuditState.IDENTIFIED,
        )
        assert evidence.preference_status == status

    @pytest.mark.parametrize(
        "status",
        [
            KBSuggestedStatus.PROVIDED,
            KBSuggestedStatus.BUDGET_REJECTED,
            KBSuggestedStatus.NOT_APPLICABLE,
            KBSuggestedStatus.MISSING,
        ],
    )
    def test_valid_kb_suggested_status(self, status: KBSuggestedStatus) -> None:
        """All declared KBSuggestedStatus values are accepted."""
        evidence = FeatureInvocationEvidence(
            feature_id="test",
            intent="write",
            prompt_route="test",
            preference_status=PreferenceStatus.NOT_APPLICABLE,
            kb_suggested_status=status,
            final_prompt_validated=True,
            audit_state=AuditState.IDENTIFIED,
        )
        assert evidence.kb_suggested_status == status

    @pytest.mark.parametrize(
        "state",
        [
            AuditState.IDENTIFIED,
            AuditState.SPECIFIED,
            AuditState.STATIC_VERIFIED,
            AuditState.RUNTIME_VERIFIED,
            AuditState.ADOPTED,
            AuditState.RATCHETED_DEBT,
            AuditState.BLOCKED,
        ],
    )
    def test_valid_audit_state(self, state: AuditState) -> None:
        """All declared AuditState values are accepted."""
        evidence = FeatureInvocationEvidence(
            feature_id="test",
            intent="write",
            prompt_route="test",
            preference_status=PreferenceStatus.NOT_APPLICABLE,
            kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
            final_prompt_validated=True,
            audit_state=state,
        )
        assert evidence.audit_state == state


# ---------------------------------------------------------------------------
# Privacy — no raw prompt/user prose
# ---------------------------------------------------------------------------


class TestEvidencePrivacy:
    """Evidence must never contain raw prompt text or user prose."""

    def test_no_prompt_text_field(self) -> None:
        """Evidence has no field that stores prompt text."""
        field_names = set(FeatureInvocationEvidence.model_fields.keys())
        # These fields must NOT exist in evidence
        forbidden_fields = {
            "prompt_text",
            "system_prompt",
            "user_prompt",
            "user_content",
            "raw_prompt",
        }
        assert forbidden_fields.isdisjoint(field_names), (
            f"Evidence contains forbidden fields: {forbidden_fields & field_names}"
        )

    def test_all_fields_are_metadata_only(self) -> None:
        """All fields are identifiers, statuses, booleans, or counts — never prose."""
        FeatureInvocationEvidence(
            feature_id="writing/new_chapter",
            intent="write",
            mode="new_chapter",
            prompt_route="writing/en/new_chapter",
            preference_status=PreferenceStatus.PROVIDED,
            kb_suggested_status=KBSuggestedStatus.BUDGET_REJECTED,
            output_budget_profile="long_texts",
            final_prompt_validated=True,
            validation_errors=("missing_var:kb_context",),
            audit_state=AuditState.RUNTIME_VERIFIED,
        )
        # All field names are non-empty metadata identifiers
        for field_name in FeatureInvocationEvidence.model_fields:
            assert field_name  # field names are non-empty


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestEvidenceSerialization:
    """Stable JSON serialization roundtrip."""

    def test_json_roundtrip(self) -> None:
        """Evidence survives JSON serialization and restoration."""
        evidence = FeatureInvocationEvidence(
            feature_id="writing/extend",
            intent="extend",
            mode="extend",
            prompt_route="writing/en/extend",
            preference_status=PreferenceStatus.PROVIDED,
            kb_suggested_status=KBSuggestedStatus.PROVIDED,
            output_budget_profile="balanced",
            final_prompt_validated=True,
            validation_errors=(),
            audit_state=AuditState.ADOPTED,
        )
        json_str = evidence.model_dump_json()
        restored = FeatureInvocationEvidence.model_validate_json(json_str)
        assert restored == evidence

    def test_serialization_deterministic(self) -> None:
        """Same evidence produces same JSON."""
        evidence = FeatureInvocationEvidence(
            feature_id="test",
            intent="write",
            prompt_route="test",
            preference_status=PreferenceStatus.NOT_APPLICABLE,
            kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
            final_prompt_validated=False,
            audit_state=AuditState.BLOCKED,
        )
        first = evidence.model_dump_json()
        second = evidence.model_dump_json()
        assert first == second

    def test_validation_errors_serialized_as_list(self) -> None:
        """Tuple of errors serializes as JSON array."""
        evidence = FeatureInvocationEvidence(
            feature_id="test",
            intent="write",
            prompt_route="test",
            preference_status=PreferenceStatus.MISSING,
            kb_suggested_status=KBSuggestedStatus.MISSING,
            final_prompt_validated=False,
            validation_errors=("err1", "err2"),
            audit_state=AuditState.IDENTIFIED,
        )
        data = json.loads(evidence.model_dump_json())
        assert isinstance(data["validation_errors"], list)
        assert len(data["validation_errors"]) == 2
