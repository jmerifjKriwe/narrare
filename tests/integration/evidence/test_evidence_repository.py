"""Integration tests for EvidenceRepositoryImpl — real PostgreSQL.

Tests the full repository contract against a live database. Each test
gets an isolated transaction that is rolled back after the test,
ensuring no cross-test pollution.

See ADR-042 § Repository for the contract design.
"""

from __future__ import annotations

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
    """Create a ``FeatureInvocationEvidence`` with sensible defaults.

    Use this helper in integration tests to quickly build evidence records
    with overridden fields for specific scenarios.

    Args:
        **overrides: Override any default field value.

    Returns:
        A new ``FeatureInvocationEvidence`` instance.
    """
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


@pytest_asyncio.fixture(loop_scope="session")
async def sample_evidence() -> FeatureInvocationEvidence:
    """A default evidence record for testing (mode=chat)."""
    return make_invocation_evidence()


# ===========================================================================
# save() + count_by_feature()
# ===========================================================================


class TestSaveAndCount:
    """Round-trip: save evidence, then count it."""

    async def test_save_then_count_matches_inserted(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """After save(), count_by_feature() returns the correct count."""
        await evidence_repo.save(sample_evidence)

        count = await evidence_repo.count_by_feature(feature_id="writing")
        assert count == 1

    async def test_save_multiple_records_increases_count(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Saving multiple records increases the count accordingly."""
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="edit"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="analysis", mode="deep"),
        )

        writing_count = await evidence_repo.count_by_feature(feature_id="writing")
        assert writing_count == 2

        analysis_count = await evidence_repo.count_by_feature(feature_id="analysis")
        assert analysis_count == 1

    async def test_count_zero_for_unknown_feature(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """count_by_feature() returns 0 when no records exist for feature."""
        count = await evidence_repo.count_by_feature(feature_id="does_not_exist")
        assert count == 0

    async def test_count_with_since_filter(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """count_by_feature() with since only counts recent records."""
        from datetime import UTC, datetime, timedelta

        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )

        now = datetime.now(UTC)
        past = now - timedelta(days=1)
        future = now + timedelta(days=1)

        # Using a since timestamp in the past should find the record
        count_past = await evidence_repo.count_by_feature(
            feature_id="writing",
            since=past,
        )
        assert count_past == 1

        # Using a since timestamp in the future should find nothing
        count_future = await evidence_repo.count_by_feature(
            feature_id="writing",
            since=future,
        )
        assert count_future == 0


# ===========================================================================
# get_distinct_modes()
# ===========================================================================


class TestDistinctModes:
    """Distinct mode queries across saved records."""

    async def test_returns_distinct_modes(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Saving records with different modes returns distinct values."""
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="edit"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )

        modes = await evidence_repo.get_distinct_modes(feature_id="writing")
        assert sorted(modes) == ["chat", "edit"]

    async def test_feature_with_single_mode(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Feature with only one mode returns a single-element list."""
        await evidence_repo.save(
            make_invocation_evidence(feature_id="analysis", mode="deep"),
        )

        modes = await evidence_repo.get_distinct_modes(feature_id="analysis")
        assert modes == ["deep"]

    async def test_unknown_feature_returns_empty_list(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Feature with no records returns empty list."""
        modes = await evidence_repo.get_distinct_modes(feature_id="does_not_exist")
        assert modes == []


# ===========================================================================
# get_by_feature_and_mode()
# ===========================================================================


class TestGetByFeatureAndMode:
    """Filter evidence by feature and mode."""

    async def test_returns_matching_records(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Returns only records that match both feature_id and mode."""
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="edit"),
        )
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )

        chat_records = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )
        assert len(chat_records) == 2
        assert all(r.mode == "chat" for r in chat_records)

        edit_records = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="edit",
        )
        assert len(edit_records) == 1
        assert all(r.mode == "edit" for r in edit_records)

    async def test_returns_newest_first(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        """Results are ordered by created_at DESC."""
        from datetime import UTC, datetime

        # Save records with explicit timestamps via the ORM model
        from narrare.evidence.models import InvocationEvidenceModel

        model_v1 = InvocationEvidenceModel(
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="identified",
            final_prompt_validated=True,
        )
        model_v2 = InvocationEvidenceModel(
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            audit_state="adopted",
            final_prompt_validated=True,
        )

        # Insert in order with manual timestamps
        model_v1.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        model_v2.created_at = datetime(2025, 6, 1, tzinfo=UTC)

        db_session.add_all([model_v1, model_v2])
        await db_session.flush()

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )

        assert len(results) >= 2
        # Newest first: first result should be adopted (June), second identified (Jan)
        assert results[0].audit_state == AuditState.ADOPTED
        assert results[1].audit_state == AuditState.IDENTIFIED

    async def test_unknown_mode_returns_empty_list(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """No records for the given mode returns empty list."""
        await evidence_repo.save(
            make_invocation_evidence(feature_id="writing", mode="chat"),
        )

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="nonexistent",
        )
        assert results == []

    async def test_respects_limit(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        """Only returns up to limit records."""
        for _ in range(10):
            await evidence_repo.save(
                make_invocation_evidence(feature_id="writing", mode="chat"),
            )

        results = await evidence_repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
            limit=3,
        )
        assert len(results) == 3
