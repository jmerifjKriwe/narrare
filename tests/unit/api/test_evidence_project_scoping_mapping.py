"""Tests for FeatureInvocationEvidence novel_id + created_at mapping (ADR-070).

Verifies the asymmetric mapping contract:
- novel_id round-trips Core ↔ ORM both ways.
- created_at is READ-ONLY: populated by orm_to_domain, omitted by domain_to_orm
  (the DB column has server_default=func.now()).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from narrare.evidence._mappers import domain_to_orm, orm_to_domain
from narrare.evidence.models import InvocationEvidenceModel
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence


def _make_evidence(*, novel_id: object | None = "unset") -> FeatureInvocationEvidence:
    kwargs: dict[str, object] = {
        "feature_id": "dialogue_coach",
        "intent": "dialogue_coach",
        "mode": "dialogue_coach",
        "prompt_route": "ai_assist/dialogue_coach",
        "preference_status": PreferenceStatus.PROVIDED,
        "kb_suggested_status": KBSuggestedStatus.NOT_APPLICABLE,
        "final_prompt_validated": True,
        "audit_state": AuditState.ADOPTED,
        "invocation_id": uuid4(),
        "adaptive_source_summary": {"summary": "preferences"},
        "adaptive_weights": {"preference": 0.7},
    }
    if novel_id != "unset":
        kwargs["novel_id"] = novel_id
    return FeatureInvocationEvidence(**kwargs)  # type: ignore[arg-type]


class TestNovelIdMapping:
    """novel_id round-trips Core ↔ ORM."""

    def test_domain_to_orm_includes_novel_id(self) -> None:
        novel = uuid4()
        evidence = _make_evidence(novel_id=novel)
        values = domain_to_orm(evidence)
        assert values["novel_id"] == novel

    def test_domain_to_orm_novel_id_none_when_unset(self) -> None:
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        assert values["novel_id"] is None

    def test_orm_to_domain_restores_novel_id(self) -> None:
        novel = uuid4()
        evidence = _make_evidence(novel_id=novel)
        model = InvocationEvidenceModel(**domain_to_orm(evidence))  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.novel_id == novel


class TestCreatedAtAsymmetric:
    """created_at is read-only (DB-stamped); domain_to_orm omits it."""

    def test_domain_to_orm_omits_created_at(self) -> None:
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        assert "created_at" not in values

    def test_orm_to_domain_restores_created_at(self) -> None:
        stamped = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        values["created_at"] = stamped
        model = InvocationEvidenceModel(**values)  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.created_at == stamped
