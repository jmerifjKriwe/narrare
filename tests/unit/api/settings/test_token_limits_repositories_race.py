"""Race-safety regression tests for the token-limits repositories.

Covers ``UserTokenLimitsRepository.get()`` and
``ProjectTokenLimitsRepository.get()`` — same defect class as
``ProjectAiSettingsRepository`` (benchmark run
``2026-09-07-clean-failed-1``): the old get-or-create (SELECT, then
``add()`` + flush) raised ``IntegrityError`` (UniqueViolation on
``user_token_limits_pkey`` / ``project_token_limits_pkey``) when a
concurrent request inserted the same row between our SELECT and our
INSERT.

Fix: PostgreSQL ``INSERT ... ON CONFLICT (<pk>) DO NOTHING`` followed by
a re-SELECT — under READ COMMITTED the second snapshot sees the
concurrent winner's committed row. The fakes below simulate exactly those
semantics (ADR-030 fake-based testing; the statement shape is pinned by
compiling the captured INSERT against the PostgreSQL dialect).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits
from narrare.settings.token_limits.repository import (
    ProjectTokenLimitsRepository,
    UserTokenLimitsRepository,
)
from tests.fakes.fake_db_session import FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ======================================================================
# Fakes simulating the concurrent-insert race at DB level
# ======================================================================


class _ConcurrentWinnerSession:
    """A concurrent transaction INSERTs the row between our SELECT (which
    still sees no row) and our INSERT.

    Old code path: ``add()`` + ``flush()`` → the DB rejects the duplicate
    INSERT with UniqueViolation → modeled by raising ``IntegrityError``
    from ``flush()``.
    Upsert code path: the INSERT carries ``ON CONFLICT DO NOTHING`` so the
    DB does not raise; the re-SELECT returns the winner's row.
    """

    def __init__(self, winner: UserTokenLimits | ProjectTokenLimits) -> None:
        self._winner = winner
        self._select_count = 0
        self.statements: list[Any] = []
        self.added: list[Any] = []
        self.flush_count = 0

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        self.flush_count += 1
        raise IntegrityError(
            "INSERT INTO token_limits (...) VALUES (...) RETURNING ...",
            None,
            Exception('duplicate key value violates unique constraint "<table>_pkey"'),
        )

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> FakeResult:
        self.statements.append(stmt)
        if isinstance(stmt, Select):
            self._select_count += 1
            if self._select_count == 1:
                return FakeResult(value=None)  # snapshot: row not yet visible
            return FakeResult(value=self._winner)  # re-select: winner's row
        return FakeResult(value=None)  # INSERT ... ON CONFLICT DO NOTHING


class _FreshCreateSession:
    """No race: the row does not exist yet.

    The upsert INSERT succeeds and the re-SELECT reads back the row this
    session just inserted. ``add()``/``flush()`` must never be reached.
    """

    def __init__(self) -> None:
        self._created: UserTokenLimits | ProjectTokenLimits | None = None
        self._select_count = 0
        self.statements: list[Any] = []

    def arm_created(self, created: UserTokenLimits | ProjectTokenLimits) -> None:
        """Provide the row the re-SELECT will read back after the INSERT."""
        self._created = created

    def add(self, entity: Any) -> None:
        raise AssertionError("add() must not be called in the upsert path")

    async def flush(self) -> None:
        raise AssertionError("flush() must not be called in the upsert path")

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> FakeResult:
        self.statements.append(stmt)
        if isinstance(stmt, Select):
            self._select_count += 1
            if self._select_count == 1:
                return FakeResult(value=None)
            assert self._created is not None
            return FakeResult(value=self._created)
        return FakeResult(value=None)


def _split_statements(
    statements: list[Any],
) -> tuple[list[Any], list[Any]]:
    """Split captured statements into (selects, others)."""
    selects = [stmt for stmt in statements if isinstance(stmt, Select)]
    others = [stmt for stmt in statements if not isinstance(stmt, Select)]
    return selects, others


# ======================================================================
# Tests — UserTokenLimitsRepository (PK: user_id)
# ======================================================================


class TestUserTokenLimitsRepositoryRace:
    async def test_get_race_loser_returns_winner_row_without_integrity_error(self) -> None:
        """The INSERT-race loser gets the winner's row instead of a 500."""
        winner = UserTokenLimits(user_id="user-1")
        session = _ConcurrentWinnerSession(winner)
        repo = UserTokenLimitsRepository(cast("AsyncSession", session))

        result = await repo.get("user-1")

        assert result is winner
        assert result.user_id == "user-1"
        # The old IntegrityError source (add + flush) must be gone.
        assert session.added == []
        assert session.flush_count == 0

    async def test_get_race_upsert_uses_on_conflict_do_nothing_on_user_id(self) -> None:
        """The INSERT is postgres-dialect with ON CONFLICT (user_id) DO NOTHING."""
        session = _ConcurrentWinnerSession(UserTokenLimits(user_id="user-1"))
        repo = UserTokenLimitsRepository(cast("AsyncSession", session))

        await repo.get("user-1")

        selects, inserts = _split_statements(session.statements)
        assert len(inserts) == 1
        assert len(selects) == 2  # initial miss + re-select of the winner's row
        compiled = str(inserts[0].compile(dialect=postgresql.dialect()))
        assert "INSERT INTO user_token_limits" in compiled
        assert "ON CONFLICT (user_id) DO NOTHING" in compiled

    async def test_get_without_race_creates_row_via_upsert_and_reselect(self) -> None:
        """Happy path: miss → upsert INSERT → re-SELECT returns the new row."""
        created = UserTokenLimits(user_id="user-1")
        session = _FreshCreateSession()
        session.arm_created(created)
        repo = UserTokenLimitsRepository(cast("AsyncSession", session))

        result = await repo.get("user-1")

        assert result is created
        selects, inserts = _split_statements(session.statements)
        assert len(selects) == 2
        assert len(inserts) == 1


# ======================================================================
# Tests — ProjectTokenLimitsRepository (PK: project_id)
# ======================================================================


class TestProjectTokenLimitsRepositoryRace:
    async def test_get_race_loser_returns_winner_row_without_integrity_error(self) -> None:
        """The INSERT-race loser gets the winner's row instead of a 500."""
        winner = ProjectTokenLimits(project_id="proj-1")
        session = _ConcurrentWinnerSession(winner)
        repo = ProjectTokenLimitsRepository(cast("AsyncSession", session))

        result = await repo.get("proj-1")

        assert result is winner
        assert result.project_id == "proj-1"
        # The old IntegrityError source (add + flush) must be gone.
        assert session.added == []
        assert session.flush_count == 0

    async def test_get_race_upsert_uses_on_conflict_do_nothing_on_project_id(self) -> None:
        """The INSERT is postgres-dialect with ON CONFLICT (project_id) DO NOTHING."""
        session = _ConcurrentWinnerSession(ProjectTokenLimits(project_id="proj-1"))
        repo = ProjectTokenLimitsRepository(cast("AsyncSession", session))

        await repo.get("proj-1")

        selects, inserts = _split_statements(session.statements)
        assert len(inserts) == 1
        assert len(selects) == 2  # initial miss + re-select of the winner's row
        compiled = str(inserts[0].compile(dialect=postgresql.dialect()))
        assert "INSERT INTO project_token_limits" in compiled
        assert "ON CONFLICT (project_id) DO NOTHING" in compiled

    async def test_get_without_race_creates_row_via_upsert_and_reselect(self) -> None:
        """Happy path: miss → upsert INSERT → re-SELECT returns the new row."""
        created = ProjectTokenLimits(project_id="proj-1")
        session = _FreshCreateSession()
        session.arm_created(created)
        repo = ProjectTokenLimitsRepository(cast("AsyncSession", session))

        result = await repo.get("proj-1")

        assert result is created
        selects, inserts = _split_statements(session.statements)
        assert len(selects) == 2
        assert len(inserts) == 1
