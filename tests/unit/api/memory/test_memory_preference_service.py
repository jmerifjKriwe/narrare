"""Unit tests for MemoryPreferenceService — get/reset preferences.

Split out of ``test_memory_service.py`` for RULE-04 (one responsibility per
file). Core PreferenceService is faked via fixtures in ``conftest.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from narrare.memory.schemas import (
    PreferenceResponse,
    ResetResponse,
)
from narrare_core.memory.models import PreferenceProfile

if TYPE_CHECKING:
    from tests.unit.api.memory.conftest import FakeCorePreference, FakeFeedbackRepository


class TestGetPreferences:
    async def test_get_preferences_returns_profile(
        self,
        preference_service: Any,
        fake_core_preference: FakeCorePreference,
    ) -> None:
        user_id = uuid4()
        project_id = uuid4()
        profile = PreferenceProfile(
            user_id=user_id,
            project_id=project_id,
            event_count=10,
            confidence=0.5,
            style={"pref_0": "Short sentences"},
            content={"pref_0": "Likes dialogue"},
            constraints=["Avoid cliches"],
        )
        fake_core_preference.profiles[(user_id, project_id)] = profile

        result = await preference_service.get_preferences(user_id, project_id)

        assert isinstance(result, PreferenceResponse)
        assert result.user_id == user_id
        assert result.project_id == project_id
        assert result.event_count == 10
        assert result.confidence == 0.5
        assert result.style == {"pref_0": "Short sentences"}

    async def test_get_preferences_returns_empty_when_no_data(
        self,
        preference_service: Any,
    ) -> None:
        user_id = uuid4()
        project_id = uuid4()

        result = await preference_service.get_preferences(user_id, project_id)

        assert isinstance(result, PreferenceResponse)
        assert result.event_count == 0
        assert result.confidence == 0.0
        assert result.style == {}


class TestResetPreferences:
    async def test_reset_preferences_clears_profile(
        self,
        preference_service: Any,
        fake_core_preference: FakeCorePreference,
        fake_repo: FakeFeedbackRepository,
    ) -> None:
        user_id = uuid4()
        project_id = uuid4()
        fake_repo.deleted_count = 5

        result = await preference_service.reset_preferences(user_id, project_id)

        assert isinstance(result, ResetResponse)
        assert result.message == "Preferences reset successfully"
        assert result.deleted_count == 5
        assert (user_id, project_id) in fake_core_preference.reset_calls

    async def test_reset_preferences_with_zero_events(
        self,
        preference_service: Any,
        fake_repo: FakeFeedbackRepository,
    ) -> None:
        fake_repo.deleted_count = 0

        result = await preference_service.reset_preferences(uuid4(), uuid4())

        assert result.deleted_count == 0
        assert result.message == "Preferences reset successfully"
