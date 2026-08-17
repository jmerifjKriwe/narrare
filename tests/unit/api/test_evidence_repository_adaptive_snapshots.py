"""Unit tests for EvidenceRepositoryImpl adaptive-snapshot methods — mocked AsyncSession.

Tests update_adaptive_snapshot() and get_adaptive_snapshots() (both ADR-070)
in isolation from a real database. All SQLAlchemy interactions are mocked.
These are the unit-level mirrors of the integration scenarios in
tests/integration/evidence/test_evidence_adaptive_snapshots.py: the SQL
semantics (novel scoping, filtering, ordering, LIMIT) are proven there
against a real database; here the rows the database would return are fed
through the mocked session to verify the ORM → domain mapping.

See ADR-042 § Repository for the contract design.

Extracted from test_evidence_repository.py (RULE-04 file-size limit) —
the shared session-mock helpers are imported from there.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.evidence.repository import EvidenceRepositoryImpl
from narrare_core.ai_invocation.models import FeatureInvocationEvidence
from tests.unit.api.test_evidence_repository import _make_mock_session

if TYPE_CHECKING:
    from unittest.mock import AsyncMock
    from uuid import UUID

    from narrare.evidence.models import InvocationEvidenceModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adaptive_row(
    *,
    novel_id: UUID,
    adaptive: dict[str, str],
    created_at: datetime,
) -> InvocationEvidenceModel:
    """Build a real ORM row as ``get_adaptive_snapshots`` would return it.

    Mirrors the ``_row()`` helper from
    ``tests/integration/evidence/test_evidence_adaptive_snapshots.py`` so the
    unit tests exercise the real ``orm_to_domain`` mapping against the real
    ``InvocationEvidenceModel`` — only the session is faked.
    """
    from narrare.evidence.models import InvocationEvidenceModel

    return InvocationEvidenceModel(
        id=uuid4(),
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status="provided",
        kb_suggested_status="not_applicable",
        audit_state="adopted",
        final_prompt_validated=True,
        novel_id=novel_id,
        invocation_id=uuid4(),
        adaptive_source_summary=adaptive,
        adaptive_weights={"preference": 0.7} if adaptive else None,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mocked AsyncSession — no real DB connection.

    Extends the shared session mock (imported from
    test_evidence_repository) with the ADR-070 ``rowcount`` default:
    update_adaptive_snapshot() reads ``rowcount`` off every execute()
    result.
    """
    session = _make_mock_session()
    session.execute.return_value.rowcount = 0
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> EvidenceRepositoryImpl:
    """EvidenceRepositoryImpl backed by the mock session."""
    return EvidenceRepositoryImpl(session=mock_session)


# ===========================================================================
# update_adaptive_snapshot() — ADR-070 / ADR-069 D11
# ===========================================================================


class TestUpdateAdaptiveSnapshot:
    """EvidenceRepositoryImpl.update_adaptive_snapshot() tests (ADR-070)."""

    async def test_executes_scoped_update_with_adaptive_values(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """update_adaptive_snapshot() issues an UPDATE on invocation_evidence.

        Binds the adaptive columns and scopes the statement to the given
        invocation_id — verified via the compiled statement's bound
        parameters (the session is faked, so the statement is the only
        observable output).
        """
        mock_session.execute.return_value.rowcount = 1
        invocation_id = uuid4()

        await repo.update_adaptive_snapshot(
            invocation_id=invocation_id,
            source_summary={"summary": "preferences"},
            weights={"preference": 0.7},
        )

        mock_session.execute.assert_awaited_once()
        stmt = mock_session.execute.call_args[0][0]
        assert stmt.__visit_name__ == "update"
        compiled = stmt.compile()
        assert "invocation_evidence" in str(compiled)
        assert compiled.params["adaptive_source_summary"] == {"summary": "preferences"}
        assert compiled.params["adaptive_weights"] == {"preference": 0.7}
        assert compiled.params["invocation_id_1"] == invocation_id

    async def test_when_no_row_matches_logs_and_does_not_raise(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """rowcount == 0 is a logged no-op, never an exception (ADR-069 D11).

        Invocation evidence is best-effort and MUST NOT block the AI call —
        a missing evidence row (e.g. evidence write skipped) only logs at
        INFO.
        """
        mock_session.execute.return_value.rowcount = 0
        invocation_id = uuid4()

        with capture_logs() as logs:
            await repo.update_adaptive_snapshot(
                invocation_id=invocation_id,
                source_summary={"summary": "preferences"},
                weights={"preference": 0.7},
            )

        matching = [log for log in logs if log.get("event") == "adaptive_snapshot_no_evidence_row"]
        assert len(matching) == 1
        assert matching[0]["invocation_id"] == str(invocation_id)


# ===========================================================================
# get_adaptive_snapshots() — ADR-070
# ===========================================================================


class TestGetAdaptiveSnapshots:
    """EvidenceRepositoryImpl.get_adaptive_snapshots() tests (ADR-070).

    Unit-level mirrors of the integration scenarios in
    ``tests/integration/evidence/test_evidence_adaptive_snapshots.py``:
    the SQL semantics (novel scoping, NULL/jsonb-null filtering, newest-first
    ordering, LIMIT) are proven there against a real database; here the rows
    the database would return are fed through the mocked session to verify
    the ORM → domain mapping carries the ADR-070 fields.
    """

    async def test_returns_adaptive_rows_mapped_to_domain(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """Adaptive-bearing rows map to domain records carrying ADR-070 fields."""
        novel = uuid4()
        row = _make_adaptive_row(
            novel_id=novel,
            adaptive={"summary": "preferences"},
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        mock_session.execute.return_value.scalars.return_value = [row]

        results = await repo.get_adaptive_snapshots(novel_id=novel)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, FeatureInvocationEvidence)
        assert result.novel_id == novel
        assert result.adaptive_source_summary == {"summary": "preferences"}
        assert result.adaptive_weights == {"preference": 0.7}
        assert result.created_at == datetime(2026, 7, 1, tzinfo=UTC)

    async def test_returns_rows_newest_first_as_delivered_by_database(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """Rows arrive newest-first (SQL ORDER BY) and keep their timestamps.

        Mirrors the integration ordering scenario: the database delivers
        ``created_at DESC``; the repository must pass that order and the
        DB-stamped ``created_at`` through unmangled.
        """
        novel = uuid4()
        new_row = _make_adaptive_row(
            novel_id=novel,
            adaptive={"summary": "new"},
            created_at=datetime(2026, 7, 23, tzinfo=UTC),
        )
        old_row = _make_adaptive_row(
            novel_id=novel,
            adaptive={"summary": "old"},
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        mock_session.execute.return_value.scalars.return_value = [new_row, old_row]

        results = await repo.get_adaptive_snapshots(novel_id=novel)

        summaries = [r.adaptive_source_summary for r in results]
        assert summaries == [{"summary": "new"}, {"summary": "old"}]
        assert [r.created_at for r in results] == [
            datetime(2026, 7, 23, tzinfo=UTC),
            datetime(2026, 7, 1, tzinfo=UTC),
        ]

    async def test_when_no_matching_rows_returns_empty(
        self,
        repo: EvidenceRepositoryImpl,
        mock_session: AsyncMock,
    ) -> None:
        """get_adaptive_snapshots() returns [] when no rows match."""
        mock_session.execute.return_value.scalars.return_value = []

        results = await repo.get_adaptive_snapshots(novel_id=uuid4())

        assert results == []
