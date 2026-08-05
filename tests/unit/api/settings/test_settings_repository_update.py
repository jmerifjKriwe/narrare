"""Tests for settings repository update methods (lines 52-56, 87-91).

Covers:
1. UserSettingsRepository.update — modifies existing settings fields
2. UserSettingsRepository.update — creates settings when missing, then updates
3. ProjectSettingsRepository.update — modifies existing settings fields
4. ProjectSettingsRepository.update — creates settings when missing, then updates
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from narrare.settings.schemas import (
    UpdateProjectSettingsRequest,
    UpdateUserSettingsRequest,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.settings.models import ProjectSettings, UserSettings


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _UpdateSession:
    """Fake session that tracks state for update testing.

    On first execute returns None (triggers create in get()),
    then stores created entity for subsequent queries.
    """

    def __init__(self) -> None:
        self._stored: UserSettings | ProjectSettings | None = None
        self.added: list[Any] = []

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        # Simulate successful flush — store the created entity
        if self.added:
            self._stored = self.added[-1]

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self._stored)

    async def rollback(self) -> None:
        pass


class TestUserSettingsRepositoryUpdate:
    """UserSettingsRepository.update coverage."""

    async def test_update_user_settings_creates_then_modifies(self) -> None:
        """Update when no settings exist creates then modifies fields (lines 52-56)."""
        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        session = _UpdateSession()
        repo = UserSettingsRepository(cast("AsyncSession", session))

        request = UpdateUserSettingsRequest(display_name="New Name", ui_language="de")
        result = await repo.update(user_id, request)

        assert result.user_id == user_id
        assert result.display_name == "New Name"
        assert result.ui_language == "de"
        assert len(session.added) >= 1

    async def test_update_user_settings_with_existing_modifies_in_place(
        self,
    ) -> None:
        """Update existing settings modifies fields in place (lines 52-56)."""
        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        session = _UpdateSession()
        repo = UserSettingsRepository(cast("AsyncSession", session))

        # First call creates
        first = await repo.update(user_id, UpdateUserSettingsRequest(display_name="Initial"))
        assert first.display_name == "Initial"

        # Second call modifies
        second = await repo.update(
            user_id, UpdateUserSettingsRequest(display_name="Updated", theme="dark")
        )
        assert second.display_name == "Updated"
        assert second.theme == "dark"

    async def test_update_user_settings_with_empty_request_no_changes(
        self,
    ) -> None:
        """Update with no fields set makes no changes (line 52-56 edge)."""
        from typing import cast as _cast

        from narrare.settings.repository import UserSettingsRepository

        user_id = uuid4()
        session = _UpdateSession()
        repo = UserSettingsRepository(_cast("AsyncSession", session))

        result = await repo.update(user_id, UpdateUserSettingsRequest())
        assert result.user_id == user_id


class TestProjectSettingsRepositoryUpdate:
    """ProjectSettingsRepository.update coverage."""

    async def test_update_project_settings_creates_then_modifies(self) -> None:
        """Update when no settings exist creates then modifies fields (lines 87-91)."""
        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        session = _UpdateSession()
        repo = ProjectSettingsRepository(cast("AsyncSession", session))

        request = UpdateProjectSettingsRequest(ai_provider="openai", ai_model="gpt-4o")
        result = await repo.update(novel_id, request)

        assert result.novel_id == novel_id
        assert result.ai_provider == "openai"
        assert result.ai_model == "gpt-4o"

    async def test_update_project_settings_with_existing_modifies_in_place(
        self,
    ) -> None:
        """Update existing settings modifies fields in place (lines 87-91)."""
        from narrare.settings.repository import ProjectSettingsRepository

        novel_id = uuid4()
        session = _UpdateSession()
        repo = ProjectSettingsRepository(cast("AsyncSession", session))

        first = await repo.update(novel_id, UpdateProjectSettingsRequest(default_language="en"))
        assert first.default_language == "en"

        second = await repo.update(
            novel_id, UpdateProjectSettingsRequest(default_language="de", autosave_interval=300)
        )
        assert second.default_language == "de"
        assert second.autosave_interval == 300

    async def test_update_project_settings_use_series_voice_false_is_persisted(
        self,
    ) -> None:
        """Spec 3: a ``False`` opt-out survives ``exclude_none`` (not dropped).

        ``UpdateProjectSettingsRequest.use_series_voice`` defaults to ``None``
        (omitted → skipped by ``exclude_none``). An explicit ``False`` MUST
        persist (the repository uses ``exclude_none=True``, which keeps
        ``False``) — this is the regression guard for the per-novel
        series-voice opt-out (ADR-078).
        """
        from narrare.settings.repository import ProjectSettingsRepository

        # 1. Explicit False reaches the ORM column (the critical opt-out case).
        novel_id = uuid4()
        repo = ProjectSettingsRepository(cast("AsyncSession", _UpdateSession()))
        result = await repo.update(novel_id, UpdateProjectSettingsRequest(use_series_voice=False))
        assert result.use_series_voice is False

        # 2. Schema-level: an omitted field is NOT in the dump (PATCH leaves
        #    the column untouched — verified at the schema boundary so the
        #    fake-session carry-over does not muddy the assertion).
        omitted = UpdateProjectSettingsRequest(default_language="en")
        assert "use_series_voice" not in omitted.model_dump(exclude_none=True)
        assert omitted.model_dump(exclude_none=True) == {"default_language": "en"}
