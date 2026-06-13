"""Tests for settings repository IntegrityError edge cases (lines 48, 81).

Covers the case where a concurrent IntegrityError occurs AND the
re-select also returns None — should re-raise the IntegrityError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _IntegrityThenNoneSession:
    """Fake session: first flush raises, re-select returns None."""

    def __init__(self) -> None:
        self._flush_count = 0
        self._rolled_back = False

    def add(self, entity: Any) -> None:
        pass

    async def flush(self) -> None:
        self._flush_count += 1
        if self._flush_count == 1 and not self._rolled_back:
            raise IntegrityError("stmt", "params", Exception("dup key"))

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(None)  # Always returns None

    async def rollback(self) -> None:
        self._rolled_back = True


class TestUserSettingsRepositoryIntegrityReRaise:
    """IntegrityError re-raise when re-select also returns None."""

    async def test_get_raises_when_retry_also_returns_none(self) -> None:
        """Concurrent IntegrityError + re-select=None propagates (line 48)."""
        from typing import cast

        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        session = _IntegrityThenNoneSession()
        repo = UserSettingsRepository(cast("AsyncSession", session))

        with pytest.raises(IntegrityError):
            await repo.get(user_id)

        assert session._rolled_back is True


class TestProjectSettingsRepositoryIntegrityReRaise:
    """IntegrityError re-raise when re-select also returns None."""

    async def test_get_raises_when_retry_also_returns_none(self) -> None:
        """Concurrent IntegrityError + re-select=None propagates (line 81)."""
        from typing import cast

        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        session = _IntegrityThenNoneSession()
        repo = ProjectSettingsRepository(cast("AsyncSession", session))

        with pytest.raises(IntegrityError):
            await repo.get(novel_id)

        assert session._rolled_back is True
