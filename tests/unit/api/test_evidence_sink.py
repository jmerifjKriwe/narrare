"""Unit tests for PersistentEvidenceSink — mocked session factory.

Tests the PostgreSQL-backed evidence sink in isolation, mocking the
session factory and the underlying session. Verifies that the sink
correctly acquires sessions, delegates to the repository, commits,
and handles errors gracefully.

See ADR-042 § Hybrid Evidence Architecture.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.evidence.sink import PersistentEvidenceSink
from narrare_core.ai_invocation.models import FeatureInvocationEvidence


@pytest.fixture
def sample_evidence() -> FeatureInvocationEvidence:
    """Default FeatureInvocationEvidence for sink tests."""
    from narrare_core.ai_invocation._enums import (
        AuditState,
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


class TestPersistentEvidenceSink:
    """PersistentEvidenceSink tests — session factory mocking."""

    async def test_record_creates_session_and_commits(
        self,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """record() acquires a session, saves evidence, and commits."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__.return_value = mock_session
        session_factory = MagicMock(
            spec=lambda: AsyncSession,
            return_value=mock_session,
        )

        sink = PersistentEvidenceSink(session_factory=session_factory)
        await sink.record(sample_evidence)

        # Repository save (add + flush)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        # Sink commit
        mock_session.commit.assert_awaited_once()

    async def test_record_with_session_factory_error_does_not_raise(
        self,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """record() logs and swallows DB errors from the session factory."""
        session_factory = MagicMock(
            spec=lambda: AsyncSession,
            side_effect=ValueError("DB connection failed"),
        )

        sink = PersistentEvidenceSink(session_factory=session_factory)

        # Must not raise despite the factory error
        await sink.record(sample_evidence)

    async def test_record_with_commit_error_does_not_raise(
        self,
        sample_evidence: FeatureInvocationEvidence,
    ) -> None:
        """record() logs and swallows commit errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__.return_value = mock_session
        mock_session.commit.side_effect = RuntimeError("Commit failed")
        session_factory = MagicMock(
            spec=lambda: AsyncSession,
            return_value=mock_session,
        )

        sink = PersistentEvidenceSink(session_factory=session_factory)

        # Must not raise despite the commit error
        await sink.record(sample_evidence)
