"""Integration tests for EvidenceRepositoryImpl state queries — real PostgreSQL.

Tests get_latest_audit_state() and round-trip field preservation against a
live database. Each test gets an isolated transaction that is rolled back.

See ADR-042 § Repository for the contract design.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest_asyncio

from narrare.evidence.repository import EvidenceRepositoryImpl
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
    VoiceProfileStatus,
)
from narrare_core.ai_invocation.models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_invocation_evidence(**overrides: object) -> FeatureInvocationEvidence:
    """Create a ``FeatureInvocationEvidence`` with sensible defaults."""
    return FeatureInvocationEvidence(
        feature_id=cast("str", overrides.pop("feature_id", "writing")),
        intent=cast("str", overrides.pop("intent", "write")),
        mode=cast("str", overrides.pop("mode", "chat")),
        prompt_route=cast("str", overrides.pop("prompt_route", "writing/en/chat")),
        preference_status=cast(
            "PreferenceStatus", overrides.pop("preference_status", PreferenceStatus.NOT_APPLICABLE)
        ),
        kb_suggested_status=cast(
            "KBSuggestedStatus",
            overrides.pop("kb_suggested_status", KBSuggestedStatus.NOT_APPLICABLE),
        ),
        voice_profile_status=cast(
            "VoiceProfileStatus | None", overrides.pop("voice_profile_status", None)
        ),
        output_budget_profile=cast("str | None", overrides.pop("output_budget_profile", None)),
        final_prompt_validated=cast("bool", overrides.pop("final_prompt_validated", True)),
        validation_errors=cast("tuple[str, ...]", overrides.pop("validation_errors", ())),
        audit_state=cast("AuditState", overrides.pop("audit_state", AuditState.ADOPTED)),
        **cast("Any", overrides),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def evidence_repo(db_session: AsyncSession) -> EvidenceRepositoryImpl:
    """EvidenceRepositoryImpl bound to the transactional test session."""
    return EvidenceRepositoryImpl(session=db_session)


# ===========================================================================
# get_latest_audit_state()
# ===========================================================================


class TestGetLatestAuditState:
    """Most recent audit state queries."""

    async def test_returns_most_recent_state(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        """Returns the audit state from the most recent record.

        Uses explicit ``created_at`` timestamps because ``now()`` is
        constant within a transaction — without the override both records
        would share the same timestamp and ordering would be undefined.
        """
        from datetime import UTC, datetime

        from narrare.evidence.models import InvocationEvidenceModel

        older = InvocationEvidenceModel(
            id=uuid.uuid4(),
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="identified",
            final_prompt_validated=True,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newer = InvocationEvidenceModel(
            id=uuid.uuid4(),
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="adopted",
            final_prompt_validated=True,
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        db_session.add_all([older, newer])
        await db_session.flush()

        state = await evidence_repo.get_latest_audit_state(feature_id="writing")
        assert state == AuditState.ADOPTED

    async def test_with_mode_filter_returns_state_for_mode(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """With mode filter, returns latest state for that specific mode."""
        await evidence_repo.save(
            make_invocation_evidence(
                feature_id="writing",
                mode="chat",
                audit_state=AuditState.IDENTIFIED,
            ),
        )
        await evidence_repo.save(
            make_invocation_evidence(
                feature_id="writing",
                mode="edit",
                audit_state=AuditState.ADOPTED,
            ),
        )

        chat_state = await evidence_repo.get_latest_audit_state(
            feature_id="writing",
            mode="chat",
        )
        assert chat_state == AuditState.IDENTIFIED

        edit_state = await evidence_repo.get_latest_audit_state(
            feature_id="writing",
            mode="edit",
        )
        assert edit_state == AuditState.ADOPTED

    async def test_without_mode_returns_latest_across_modes(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        """Without mode filter, returns latest state across all modes.

        Uses explicit ``created_at`` timestamps because ``now()`` is
        constant within a transaction.
        """
        from datetime import UTC, datetime

        from narrare.evidence.models import InvocationEvidenceModel

        older = InvocationEvidenceModel(
            id=uuid.uuid4(),
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="identified",
            final_prompt_validated=True,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newer = InvocationEvidenceModel(
            id=uuid.uuid4(),
            feature_id="writing",
            intent="write",
            mode="edit",
            prompt_route="writing/en/edit",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="adopted",
            final_prompt_validated=True,
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        db_session.add_all([older, newer])
        await db_session.flush()

        state = await evidence_repo.get_latest_audit_state(feature_id="writing")
        assert state == AuditState.ADOPTED

    async def test_no_records_returns_none(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """No records for feature returns None."""
        state = await evidence_repo.get_latest_audit_state(
            feature_id="does_not_exist",
        )
        assert state is None


# ===========================================================================
# Round-trip: field preservation
# ===========================================================================


class TestRoundTrip:
    """Domain model fields survive save/get round-trip."""

    async def test_all_fields_preserved(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """All fields match after save() followed by get_by_feature_and_mode()."""
        original = make_invocation_evidence(
            feature_id="analysis",
            intent="analyze",
            mode="deep",
            prompt_route="analysis/en/deep",
            preference_status=PreferenceStatus.PROVIDED,
            kb_suggested_status=KBSuggestedStatus.PROVIDED,
            voice_profile_status=VoiceProfileStatus.PROVIDED,
            output_budget_profile="balanced",
            final_prompt_validated=True,
            validation_errors=("warning_1",),
            audit_state=AuditState.RUNTIME_VERIFIED,
        )
        await evidence_repo.save(original)

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="analysis",
            mode="deep",
        )
        assert len(results) == 1
        retrieved = results[0]

        assert retrieved.feature_id == original.feature_id
        assert retrieved.intent == original.intent
        assert retrieved.mode == original.mode
        assert retrieved.prompt_route == original.prompt_route
        assert retrieved.preference_status == original.preference_status
        assert retrieved.kb_suggested_status == original.kb_suggested_status
        assert retrieved.voice_profile_status == original.voice_profile_status
        assert retrieved.output_budget_profile == original.output_budget_profile
        assert retrieved.final_prompt_validated == original.final_prompt_validated
        assert retrieved.audit_state == original.audit_state

    async def test_validation_errors_round_trip(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Validation errors tuple survives save/get round-trip."""
        original = make_invocation_evidence(
            feature_id="writing",
            intent="write",
            mode="chat",
            validation_errors=("err_a", "err_b", "err_c"),
        )
        await evidence_repo.save(original)

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )
        assert len(results) == 1
        retrieved = results[0]

        assert tuple(retrieved.validation_errors) == ("err_a", "err_b", "err_c")

    async def test_optional_fields_none_round_trip(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """None optional fields are preserved through save/get."""
        original = make_invocation_evidence(
            feature_id="writing",
            mode="chat",
            voice_profile_status=None,
            output_budget_profile=None,
        )
        await evidence_repo.save(original)

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )
        assert len(results) == 1
        retrieved = results[0]

        assert retrieved.voice_profile_status is None
        assert retrieved.output_budget_profile is None
