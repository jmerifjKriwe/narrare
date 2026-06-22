"""Shared fakes + fixtures for the memory service unit tests.

Provides lightweight, hand-rolled fakes for the core feedback/preference
services and the feedback repository used by ``test_memory_service.py`` and
``test_memory_preference_service.py``. These are intentionally distinct from
the richer ``tests.fakes.*`` doubles (used by the router/analysis tests) and
live here so each service test module stays under RULE-04's 300-line limit.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.memory.schemas import FeedbackRequest
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


def make_feedback_request(**overrides: Any) -> FeedbackRequest:
    """Build a FeedbackRequest with sensible defaults (feedback-service tests)."""
    defaults: dict[str, Any] = {
        "action": "accept",
        "suggestion_id": uuid4(),
        "intent": "write",
        "suggestion_text": "The forest was dark and mysterious.",
        "project_id": uuid4(),
    }
    defaults.update(overrides)
    return FeedbackRequest(**defaults)
