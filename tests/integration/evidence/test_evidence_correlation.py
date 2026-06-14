"""Integration test for ADR-045 evidence correlation fields round-trip.

Proves that ``invocation_id``, ``prepared_context_fingerprint``,
``prompt_fingerprint``, ``budget_decision_fingerprint``,
``model_call_marker``, and ``manual_injection_exception`` survive a
save → get round-trip through the persistent evidence repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio

from narrare.evidence.repository import EvidenceRepositoryImpl
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(loop_scope="session")
async def evidence_repo(db_session: AsyncSession) -> EvidenceRepositoryImpl:
    return EvidenceRepositoryImpl(session=db_session)


class TestCorrelationFieldsRoundTrip:
    """ADR-045 correlation fields survive save/get round-trip."""

    async def test_correlation_fields_preserved(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """All ADR-045 correlation fields survive a save → get round-trip."""
        import uuid

        invocation_id = uuid.uuid4()
        original = FeatureInvocationEvidence(
            feature_id="writing",
            intent="write",
            mode="interactive_session",
            prompt_route="writing/en/interactive_session",
            preference_status=PreferenceStatus.NOT_APPLICABLE,
            kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
            final_prompt_validated=True,
            audit_state=AuditState.RUNTIME_VERIFIED,
            invocation_id=invocation_id,
            prepared_context_fingerprint="sha256:abc123",
            prompt_fingerprint="sha256:def456",
            budget_decision_fingerprint="balanced:2000",
            model_call_marker="test/test-model/balanced/stream",
            manual_injection_exception="agent_deps:chapter_context",
        )
        await evidence_repo.save(original)

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="interactive_session",
        )
        assert len(results) == 1
        retrieved = results[0]

        assert retrieved.invocation_id == invocation_id
        assert retrieved.prepared_context_fingerprint == "sha256:abc123"
        assert retrieved.prompt_fingerprint == "sha256:def456"
        assert retrieved.budget_decision_fingerprint == "balanced:2000"
        assert retrieved.model_call_marker == "test/test-model/balanced/stream"
        assert retrieved.manual_injection_exception == "agent_deps:chapter_context"
