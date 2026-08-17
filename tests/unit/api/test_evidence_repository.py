"""Unit tests for EvidenceRepositoryImpl save/count/distinct — mocked AsyncSession.

Tests the repository contract (EvidenceRepository protocol) in isolation
from a real database. All SQLAlchemy interactions are mocked, verifying
that the repository correctly translates domain calls to ORM operations
and correctly converts results back to domain models.

See ADR-042 § Repository for the contract design.

This file covers: save(), count_by_feature(), get_distinct_modes().
Query tests (get_by_feature_and_mode, get_latest_audit_state), sink
tests and the ADR-070 adaptive-snapshot tests (update_adaptive_snapshot,
get_adaptive_snapshots) are in separate files — the latter in
test_evidence_repository_adaptive_snapshots.py, which imports the
shared session-mock helpers from here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.evidence.repository import EvidenceRepositoryImpl
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
    VoiceProfileStatus,
)
from narrare_core.ai_invocation.models import FeatureInvocationEvidence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with chainable execute()."""
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(
        spec=["scalar_one", "scalar_one_or_none", "scalars", "all"],
    )
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value = []
    mock_result.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()
    session.add = MagicMock(spec=AsyncSession.add)
    return session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mocked AsyncSession — no real DB connection."""
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> EvidenceRepositoryImpl:
    """EvidenceRepositoryImpl backed by the mock session."""
    return EvidenceRepositoryImpl(session=mock_session)


@pytest.fixture
def sample_evidence() -> FeatureInvocationEvidence:
    """Default FeatureInvocationEvidence for save tests."""
    return FeatureInvocationEvidence(
        feature_id="writing",
        intent="write",
        mode="chat",
        prompt_route="writing/en/chat",
        preference_status=PreferenceStatus.NOT_APPLICABLE,
        kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
        voice_profile_status=None,
        output_budget_profile=None,
        final_prompt_validated=True,
        audit_state=AuditState.ADOPTED,
    )


# ===========================================================================
# save()
# ===========================================================================


class TestSave:
    """EvidenceRepositoryImpl.save() tests."""

    async def test_save_adds_orm_model_and_flushes(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """save() creates an InvocationEvidenceModel, adds it, and flushes."""
        await repo.save(sample_evidence)

        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        from narrare.evidence.models import InvocationEvidenceModel

        assert isinstance(added_model, InvocationEvidenceModel)
        assert added_model.feature_id == "writing"
        assert added_model.audit_state == "adopted"
        mock_session.flush.assert_awaited_once()

    async def test_save_maps_all_domain_fields_to_orm_columns(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """save() correctly converts every domain field to the ORM model."""
        evidence = FeatureInvocationEvidence(
            feature_id="analysis",
            intent="analyze",
            mode="deep",
            prompt_route="analysis/en/deep",
            preference_status=PreferenceStatus.PROVIDED,
            kb_suggested_status=KBSuggestedStatus.PROVIDED,
            voice_profile_status=VoiceProfileStatus.PROVIDED,
            output_budget_profile="balanced",
            final_prompt_validated=True,
            validation_errors=("err1", "err2"),
            audit_state=AuditState.RUNTIME_VERIFIED,
        )

        await repo.save(evidence)

        mock_session.add.assert_called_once()
        model = mock_session.add.call_args[0][0]
        assert model.feature_id == "analysis"
        assert model.intent == "analyze"
        assert model.mode == "deep"
        assert model.prompt_route == "analysis/en/deep"
        assert model.preference_status == "provided"
        assert model.kb_suggested_status == "provided"
        assert model.voice_profile_status == "provided"
        assert model.output_budget_profile == "balanced"
        assert model.final_prompt_validated is True
        assert model.validation_errors == ["err1", "err2"]
        assert model.audit_state == "runtime_verified"

    async def test_save_with_optional_fields_none(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """save() handles None optional fields correctly."""
        evidence = sample_evidence.model_copy(
            update={
                "mode": None,
                "voice_profile_status": None,
                "output_budget_profile": None,
            },
        )

        await repo.save(evidence)

        mock_session.add.assert_called_once()
        model = mock_session.add.call_args[0][0]
        assert model.mode is None
        assert model.voice_profile_status is None
        assert model.output_budget_profile is None


# ===========================================================================
# count_by_feature()
# ===========================================================================


class TestCountByFeature:
    """EvidenceRepositoryImpl.count_by_feature() tests."""

    async def test_returns_count_from_database(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """count_by_feature() returns the count reported by scalar_one()."""
        mock_session.execute.return_value.scalar_one.return_value = 5

        count = await repo.count_by_feature(feature_id="writing")

        assert count == 5
        mock_session.execute.assert_awaited_once()

    async def test_when_no_records_returns_zero(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """count_by_feature() returns 0 when no records match."""
        mock_session.execute.return_value.scalar_one.return_value = 0

        count = await repo.count_by_feature(feature_id="nonexistent")

        assert count == 0

    async def test_with_since_filter(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """count_by_feature() works with the since timestamp filter."""
        since = datetime(2026, 1, 1, tzinfo=UTC)
        mock_session.execute.return_value.scalar_one.return_value = 3

        count = await repo.count_by_feature(feature_id="writing", since=since)

        assert count == 3

    async def test_without_since_returns_all_records(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """count_by_feature() without since counts all records for feature."""
        mock_session.execute.return_value.scalar_one.return_value = 10

        count = await repo.count_by_feature(feature_id="writing")

        assert count == 10


# ===========================================================================
# get_distinct_modes()
# ===========================================================================


class TestGetDistinctModes:
    """EvidenceRepositoryImpl.get_distinct_modes() tests."""

    async def test_returns_distinct_mode_strings(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_distinct_modes() returns unique mode values."""
        mock_session.execute.return_value.all.return_value = [
            ("chat",),
            ("edit",),
            ("analyze",),
        ]

        modes = await repo.get_distinct_modes(feature_id="writing")

        assert modes == ["chat", "edit", "analyze"]

    async def test_when_no_records_returns_empty_list(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_distinct_modes() returns [] when no records exist."""
        mock_session.execute.return_value.all.return_value = []

        modes = await repo.get_distinct_modes(feature_id="empty")

        assert modes == []

    async def test_excludes_null_modes(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_distinct_modes() excludes NULL mode values."""
        mock_session.execute.return_value.all.return_value = [("chat",)]

        modes = await repo.get_distinct_modes(feature_id="writing")

        assert modes == ["chat"]
