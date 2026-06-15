"""Unit tests for PersistentEvidenceSink — mocked session factory.

Tests the PostgreSQL-backed evidence sink in isolation, mocking the
session factory and the underlying session. Verifies that the sink
correctly acquires sessions, delegates to the repository, commits,
and handles errors gracefully.

Also tests the ``get_evidence_sink()`` factory that wires the sink into
the production InvocationPipeline based on the ``use_persistent_evidence``
setting (ADR-042 § Wiring in Production).

See ADR-042 § Hybrid Evidence Architecture.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.evidence.dependencies import get_evidence_sink
from narrare.evidence.sink import PersistentEvidenceSink
from narrare_core.ai_invocation import LoggingEvidenceSink
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


class TestGetEvidenceSinkFactory:
    """Factory selection tests for ``get_evidence_sink()`` (ADR-042 wiring)."""

    def test_default_returns_logging_sink(self) -> None:
        """When ``use_persistent_evidence`` is False, return LoggingEvidenceSink."""
        fake_settings = SimpleNamespace(use_persistent_evidence=False)

        with patch(
            "narrare.evidence.dependencies.get_settings",
            return_value=fake_settings,
        ):
            sink = get_evidence_sink()

        assert isinstance(sink, LoggingEvidenceSink)

    def test_persistent_flag_returns_persistent_sink(self) -> None:
        """When ``use_persistent_evidence`` is True, return PersistentEvidenceSink.

        The sink must hold the real session factory from
        ``get_session_factory()`` so each ``record()`` call can acquire its
        own session and evidence reaches the ``invocation_evidence`` table.
        """
        fake_settings = SimpleNamespace(use_persistent_evidence=True)

        with patch(
            "narrare.evidence.dependencies.get_settings",
            return_value=fake_settings,
        ):
            sink = get_evidence_sink()

        assert isinstance(sink, PersistentEvidenceSink)
        # The sink must hold a callable session factory (not None) so that
        # evidence actually persists to the invocation_evidence table.
        assert callable(sink._session_factory)
