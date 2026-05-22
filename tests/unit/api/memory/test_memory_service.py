"""Unit tests for MemoryFeedbackService and MemoryPreferenceService.

Tests the API layer services that wrap core FeedbackService and
PreferenceService with DB persistence. Core services are faked.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.memory.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    PreferenceResponse,
    ResetResponse,
)
from narrare_core.memory.models import PreferenceProfile

# ---------------------------------------------------------------------------
# Fake core services and repositories
# ---------------------------------------------------------------------------


class FakeCoreFeedback:
    """Fake core FeedbackService for testing."""

    def __init__(self) -> None:
        self.recorded: list[Any] = []

    async def record(self, event: Any) -> None:
        self.recorded.append(event)


class FakeCorePreference:
    """Fake core PreferenceService for testing."""

    def __init__(self) -> None:
        self.profiles: dict[tuple[Any, Any], PreferenceProfile] = {}
        self.reset_calls: list[tuple[Any, Any]] = []

    async def get_preferences(self, user_id: Any, project_id: Any) -> PreferenceProfile:
        return self.profiles.get(
            (user_id, project_id),
            PreferenceProfile(user_id=user_id, project_id=project_id),
        )

    async def reset(self, user_id: Any, project_id: Any) -> None:
        self.reset_calls.append((user_id, project_id))
        self.profiles.pop((user_id, project_id), None)


class FakeFeedbackRepository:
    """Fake FeedbackRepository for testing."""

    def __init__(self) -> None:
        self.deleted_count: int = 0

    async def delete_by_user_project(self, user_id: Any, project_id: Any) -> int:
        return self.deleted_count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_core_feedback() -> FakeCoreFeedback:
    return FakeCoreFeedback()


@pytest.fixture
def fake_core_preference() -> FakeCorePreference:
    return FakeCorePreference()


@pytest.fixture
def fake_repo() -> FakeFeedbackRepository:
    return FakeFeedbackRepository()


@pytest.fixture
def feedback_service(
    fake_repo: FakeFeedbackRepository, fake_core_feedback: FakeCoreFeedback
) -> Any:
    from narrare.memory.service import MemoryFeedbackService

    return MemoryFeedbackService(
        repository=fake_repo,  # type: ignore[arg-type]
        core_feedback=fake_core_feedback,  # type: ignore[arg-type]
        event_publisher=None,
    )


@pytest.fixture
def preference_service(
    fake_repo: FakeFeedbackRepository, fake_core_preference: FakeCorePreference
) -> Any:
    from narrare.memory.service import MemoryPreferenceService

    return MemoryPreferenceService(
        repository=fake_repo,  # type: ignore[arg-type]
        core_preference=fake_core_preference,  # type: ignore[arg-type]
    )


def _make_feedback_request(**overrides: Any) -> FeedbackRequest:
    defaults: dict[str, Any] = {
        "action": "accept",
        "suggestion_id": uuid4(),
        "intent": "write",
        "suggestion_text": "The forest was dark and mysterious.",
        "project_id": uuid4(),
    }
    defaults.update(overrides)
    return FeedbackRequest(**defaults)


# ---------------------------------------------------------------------------
# MemoryFeedbackService tests
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    async def test_record_feedback_creates_event_and_calls_core(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        user_id = uuid4()
        request = _make_feedback_request()

        await feedback_service.record_feedback(request, user_id)

        assert len(fake_core_feedback.recorded) == 1
        event = fake_core_feedback.recorded[0]
        assert event.user_id == user_id
        assert event.project_id == request.project_id
        assert event.action.value == "accept"
        assert event.suggestion_text == "The forest was dark and mysterious."

    async def test_record_feedback_with_rating(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = _make_feedback_request(rating=4)

        response = await feedback_service.record_feedback(request, uuid4())

        assert isinstance(response, FeedbackResponse)
        assert response.action == "accept"
        event = fake_core_feedback.recorded[0]
        assert event.rating == 4

    async def test_record_feedback_enriches_context_with_chapter_genre_mode(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        chapter_id = uuid4()
        request = _make_feedback_request(
            chapter_id=chapter_id,
            genre="Fantasy",
            mode="creative",
        )

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert event.context["chapter_id"] == str(chapter_id)
        assert event.context["genre"] == "Fantasy"
        assert event.context["mode"] == "creative"

    async def test_record_feedback_modification_action(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = _make_feedback_request(
            action="modify",
            modification="Changed to past tense.",
        )

        response = await feedback_service.record_feedback(request, uuid4())

        assert response.action == "modify"
        event = fake_core_feedback.recorded[0]
        assert event.modification == "Changed to past tense."

    async def test_record_feedback_validates_required_action(
        self,
    ) -> None:
        """Pydantic validates the action field pattern."""
        with pytest.raises(ValueError):
            FeedbackRequest(
                action="invalid_action",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# MemoryPreferenceService tests
# ---------------------------------------------------------------------------


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
