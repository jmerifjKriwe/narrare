"""Unit tests for EvidenceRepositoryImpl query methods — mocked AsyncSession.

Tests get_by_feature_and_mode() and get_latest_audit_state() in isolation
from a real database. All SQLAlchemy interactions are mocked.

See ADR-042 § Repository for the contract design.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.evidence.repository import EvidenceRepositoryImpl
from narrare_core.ai_invocation._enums import AuditState
from narrare_core.ai_invocation.models import FeatureInvocationEvidence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Defaults for every attribute ``_orm_to_domain`` reads off the ORM model.
# Kept in sync with ``InvocationEvidenceModel`` (apps/api/narrare/evidence/models.py)
# and the correlation fields added by ADR-045 §2. ``MagicMock(spec=[])`` blocks
# access to unset attributes, so callers that don't care about a field still
# need a default here or the repository mapping raises ``AttributeError``.
_ORM_MODEL_DEFAULTS: dict[str, object] = {
    # ADR-045 §2 correlation fields (migration 0030) + streaming (migration 0028).
    "streaming": False,
    "invocation_id": None,
    "prepared_context_fingerprint": None,
    "prompt_fingerprint": None,
    "budget_decision_fingerprint": None,
    "model_call_marker": None,
    "manual_injection_exception": None,
    # ADR-069 D11: adaptive context provenance + resolved weights.
    "adaptive_source_summary": None,
    "adaptive_weights": None,
}


def _make_orm_model_mock(**kwargs: object) -> MagicMock:
    """Create a mock ORM model instance with the given attributes.

    The mock mimics an ``InvocationEvidenceModel`` instance, providing
    attribute access that ``_orm_to_domain`` reads during conversion.
    Caller-supplied ``kwargs`` override ``_ORM_MODEL_DEFAULTS`` so tests can
    exercise specific correlation-field values without repeating the defaults.
    """
    model = MagicMock(spec=[])
    for key, value in {**_ORM_MODEL_DEFAULTS, **kwargs}.items():
        setattr(model, key, value)
    return model


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
    """Default FeatureInvocationEvidence for query tests."""
    from narrare_core.ai_invocation._enums import (
        KBSuggestedStatus,
        PreferenceStatus,
    )

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
# get_by_feature_and_mode()
# ===========================================================================


class TestGetByFeatureAndMode:
    """EvidenceRepositoryImpl.get_by_feature_and_mode() tests."""

    async def test_returns_domain_model_instances(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_by_feature_and_mode() returns FeatureInvocationEvidence list."""
        mock_model = _make_orm_model_mock(
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            voice_profile_status=None,
            output_budget_profile=None,
            final_prompt_validated=True,
            validation_errors=[],
            audit_state="adopted",
        )
        mock_session.execute.return_value.scalars.return_value = [mock_model]

        results = await repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )

        assert len(results) == 1
        assert isinstance(results[0], FeatureInvocationEvidence)
        assert results[0].feature_id == "writing"
        assert results[0].mode == "chat"
        assert results[0].audit_state == AuditState.ADOPTED

    async def test_respects_limit_parameter(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_by_feature_and_mode() respects the limit parameter."""
        mock_models = [
            _make_orm_model_mock(
                feature_id="writing",
                intent="write",
                mode="chat",
                prompt_route="writing/en/chat",
                preference_status="not_applicable",
                kb_suggested_status="not_applicable",
                voice_profile_status=None,
                output_budget_profile=None,
                final_prompt_validated=True,
                validation_errors=[],
                audit_state="adopted",
            )
            for _ in range(5)
        ]
        mock_session.execute.return_value.scalars.return_value = mock_models

        results = await repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
            limit=5,
        )

        assert len(results) == 5

    async def test_uses_default_limit_of_100(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_by_feature_and_mode() defaults to limit=100."""
        mock_models = [
            _make_orm_model_mock(
                feature_id="writing",
                intent="write",
                mode="chat",
                prompt_route="writing/en/chat",
                preference_status="not_applicable",
                kb_suggested_status="not_applicable",
                voice_profile_status=None,
                output_budget_profile=None,
                final_prompt_validated=True,
                validation_errors=[],
                audit_state="adopted",
            )
            for _ in range(100)
        ]
        mock_session.execute.return_value.scalars.return_value = mock_models

        results = await repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )

        assert len(results) == 100

    async def test_when_no_records_returns_empty_list(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_by_feature_and_mode() returns [] when no records match."""
        mock_session.execute.return_value.scalars.return_value = []

        results = await repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="nonexistent",
        )

        assert results == []

    async def test_returns_newest_first(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_by_feature_and_mode() orders by created_at DESC."""
        mock_model_a = _make_orm_model_mock(
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            voice_profile_status=None,
            output_budget_profile=None,
            final_prompt_validated=True,
            validation_errors=[],
            audit_state="adopted",
        )
        mock_model_b = _make_orm_model_mock(
            feature_id="writing",
            intent="write",
            mode="chat",
            prompt_route="writing/en/chat",
            preference_status="not_applicable",
            kb_suggested_status="not_applicable",
            voice_profile_status=None,
            output_budget_profile=None,
            final_prompt_validated=True,
            validation_errors=[],
            audit_state="blocked",
        )
        mock_session.execute.return_value.scalars.return_value = [
            mock_model_a,
            mock_model_b,
        ]

        results = await repo.get_by_feature_and_mode(
            feature_id="writing",
            mode="chat",
        )

        assert len(results) == 2


# ===========================================================================
# get_latest_audit_state()
# ===========================================================================


class TestGetLatestAuditState:
    """EvidenceRepositoryImpl.get_latest_audit_state() tests."""

    async def test_returns_audit_state(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_audit_state() returns the most recent AuditState."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = "adopted"

        state = await repo.get_latest_audit_state(feature_id="writing")

        assert state == AuditState.ADOPTED

    async def test_with_mode_filter_returns_state_for_mode(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_audit_state() with mode returns state for that mode."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = "blocked"

        state = await repo.get_latest_audit_state(
            feature_id="writing",
            mode="edit",
        )

        assert state == AuditState.BLOCKED

    async def test_without_mode_filter_returns_global_latest(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_audit_state() with mode=None returns latest across modes."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = "identified"

        state = await repo.get_latest_audit_state(feature_id="writing", mode=None)

        assert state == AuditState.IDENTIFIED

    async def test_when_no_records_returns_none(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_audit_state() returns None when no records exist."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        state = await repo.get_latest_audit_state(feature_id="empty")

        assert state is None

    async def test_when_unknown_feature_returns_none(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_audit_state() returns None for non-existent feature."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        state = await repo.get_latest_audit_state(feature_id="does_not_exist")

        assert state is None
