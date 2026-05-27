"""Regression tests for settings repository race condition (Bug 1).

Simulates the IntegrityError that occurs when two concurrent requests
both call get() for the same user_id / novel_id, both see None, and
both attempt INSERT — the second should recover gracefully.

The fake session below simulates this by raising IntegrityError on the
first flush, then returning a pre-existing row on re-select.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from narrare.settings.models import ProjectSettings, UserSettings

# ======================================================================
# Minimal fake for SQLAlchemy Result proxy
# ======================================================================


class _FakeResult:
    """Minimal fake for SQLAlchemy Result — only scalar_one_or_none()."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


# ======================================================================
# Fake async session that simulates the race condition
# ======================================================================


class _RaceConditionSession:
    """Fake session that raises IntegrityError on first flush.

    After rollback() is called, subsequent execute() calls return
    the pre-existing settings object (simulating the "winner" of
    the race).
    """

    def __init__(self, winner: UserSettings | ProjectSettings) -> None:
        self._winner = winner
        self._flush_count = 0
        self._rolled_back = False
        self.added: list[Any] = []

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        self._flush_count += 1
        if self._flush_count == 1 and not self._rolled_back:
            # First flush attempt — simulate concurrent INSERT
            raise IntegrityError("statement", "params", Exception("duplicate key"))

    async def refresh(self, entity: Any) -> None:
        # Only called after a successful flush (second attempt)
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        if self._rolled_back:
            return _FakeResult(self._winner)
        return _FakeResult(None)

    async def rollback(self) -> None:
        self._rolled_back = True


# ======================================================================
# Normal session (no race)
# ======================================================================


class _NormalSession:
    """Fake session where no race occurs — first select returns None,
    flush succeeds, entity is created normally.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        pass

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(None)

    async def rollback(self) -> None:
        pass


# ======================================================================
# Existing-row session (no insert needed)
# ======================================================================


class _ExistingRowSession:
    """Fake session where the row already exists — select returns it,
    so no INSERT is attempted.
    """

    def __init__(self, existing: UserSettings | ProjectSettings) -> None:
        self._existing = existing

    def add(self, entity: Any) -> None:
        raise AssertionError("add() should not be called when row exists")

    async def flush(self) -> None:
        pass

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self._existing)

    async def rollback(self) -> None:
        pass


# ======================================================================
# Tests — UserSettingsRepository
# ======================================================================


class TestUserSettingsRepositoryRaceCondition:
    """Regression tests for IntegrityError on concurrent get()."""

    async def test_get_recovers_from_integrity_error(self) -> None:
        """When two concurrent get() calls race, the loser recovers."""
        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        winner = UserSettings(user_id=user_id)
        session = _RaceConditionSession(winner)
        repo = UserSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(user_id)

        assert result is winner
        assert result.user_id == user_id
        assert session._rolled_back is True

    async def test_get_creates_new_when_no_race(self) -> None:
        """Normal case — no existing row, flush succeeds."""
        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        session = _NormalSession()
        repo = UserSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(user_id)

        assert result.user_id == user_id
        assert len(session.added) == 1
        assert isinstance(session.added[0], UserSettings)

    async def test_get_returns_existing_without_insert(self) -> None:
        """When row exists, no INSERT is attempted."""
        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        existing = UserSettings(user_id=user_id)
        session = _ExistingRowSession(existing)
        repo = UserSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(user_id)

        assert result is existing


# ======================================================================
# Tests — ProjectSettingsRepository
# ======================================================================


class TestProjectSettingsRepositoryRaceCondition:
    """Regression tests for IntegrityError on concurrent get()."""

    async def test_get_recovers_from_integrity_error(self) -> None:
        """When two concurrent get() calls race, the loser recovers."""
        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        winner = ProjectSettings(novel_id=novel_id)
        session = _RaceConditionSession(winner)
        repo = ProjectSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(novel_id)

        assert result is winner
        assert result.novel_id == novel_id
        assert session._rolled_back is True

    async def test_get_creates_new_when_no_race(self) -> None:
        """Normal case — no existing row, flush succeeds."""
        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        session = _NormalSession()
        repo = ProjectSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(novel_id)

        assert result.novel_id == novel_id
        assert len(session.added) == 1
        assert isinstance(session.added[0], ProjectSettings)

    async def test_get_returns_existing_without_insert(self) -> None:
        """When row exists, no INSERT is attempted."""
        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        existing = ProjectSettings(novel_id=novel_id)
        session = _ExistingRowSession(existing)
        repo = ProjectSettingsRepository(session)  # type: ignore[arg-type]

        result = await repo.get(novel_id)

        assert result is existing
