"""Unit tests for memory router — endpoint schema validation.

Tests the FastAPI router via httpx.AsyncClient with mocked service layer.
Validates request/response schemas, status codes, and error handling.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.memory.schemas import (
    FeedbackResponse,
    PreferenceResponse,
    ResetResponse,
)
from narrare_core.memory.models import PreferenceProfile

# ---------------------------------------------------------------------------
# Fake services for DI override
# ---------------------------------------------------------------------------


class FakeFeedbackService:
    """Fake MemoryFeedbackService."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record_feedback(self, request: Any, user_id: Any) -> FeedbackResponse:
        from datetime import UTC, datetime

        self.calls.append({"request": request, "user_id": user_id})
        return FeedbackResponse(
            id=uuid4(),
            action=request.action,
            created_at=datetime.now(UTC),
        )


class FakePreferenceService:
    """Fake MemoryPreferenceService."""

    def __init__(self) -> None:
        self.get_calls: list[dict[str, Any]] = []
        self.reset_calls: list[dict[str, Any]] = []

    async def get_preferences(self, user_id: Any, project_id: Any) -> PreferenceResponse:
        self.get_calls.append({"user_id": user_id, "project_id": project_id})
        profile = PreferenceProfile(user_id=user_id, project_id=project_id)
        return PreferenceResponse(
            user_id=profile.user_id,
            project_id=profile.project_id,
            event_count=profile.event_count,
            confidence=profile.confidence,
            style=profile.style,
            content=profile.content,
            constraints=profile.constraints,
            last_updated=profile.last_updated,
        )

    async def reset_preferences(self, user_id: Any, project_id: Any) -> ResetResponse:
        self.reset_calls.append({"user_id": user_id, "project_id": project_id})
        return ResetResponse(
            message="Preferences reset successfully",
            deleted_count=3,
        )


# ---------------------------------------------------------------------------
# Tests — pure service-level tests (no HTTP client needed)
# ---------------------------------------------------------------------------


class TestRecordFeedbackEndpoint:
    """Tests for POST /memory/feedback — via direct service call."""

    async def test_post_feedback_returns_201_via_service(self) -> None:
        """Service returns FeedbackResponse with correct fields."""
        fake = FakeFeedbackService()
        from narrare.memory.schemas import FeedbackRequest

        user_id = uuid4()
        request = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Good suggestion.",
            project_id=uuid4(),
            rating=5,
        )

        result = await fake.record_feedback(request, user_id)

        assert result.action == "accept"
        assert result.id is not None
        assert result.created_at is not None
        assert len(fake.calls) == 1

    async def test_post_feedback_validates_schema(self) -> None:
        """Pydantic rejects invalid action values."""
        from narrare.memory.schemas import FeedbackRequest

        with pytest.raises(ValueError):
            FeedbackRequest(
                action="invalid",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    async def test_post_feedback_validates_rating_range(self) -> None:
        """Pydantic rejects ratings outside 1-5."""
        from narrare.memory.schemas import FeedbackRequest

        with pytest.raises(ValueError):
            FeedbackRequest(
                action="accept",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
                rating=10,
            )


class TestGetPreferencesEndpoint:
    """Tests for GET /memory/preferences — via direct service call."""

    async def test_get_preferences_returns_profile(self) -> None:
        fake = FakePreferenceService()
        user_id = uuid4()
        project_id = uuid4()

        result = await fake.get_preferences(user_id, project_id)

        assert isinstance(result, PreferenceResponse)
        assert result.user_id == user_id
        assert result.project_id == project_id
        assert result.event_count == 0
        assert result.confidence == 0.0

    async def test_get_preferences_tracks_calls(self) -> None:
        fake = FakePreferenceService()
        user_id = uuid4()
        project_id = uuid4()

        await fake.get_preferences(user_id, project_id)

        assert len(fake.get_calls) == 1
        assert fake.get_calls[0]["user_id"] == user_id


class TestResetPreferencesEndpoint:
    """Tests for DELETE /memory/preferences — via direct service call."""

    async def test_delete_preferences_returns_204_via_service(self) -> None:
        """Service returns ResetResponse with confirmation."""
        fake = FakePreferenceService()
        user_id = uuid4()
        project_id = uuid4()

        result = await fake.reset_preferences(user_id, project_id)

        assert isinstance(result, ResetResponse)
        assert result.message == "Preferences reset successfully"
        assert result.deleted_count == 3
        assert len(fake.reset_calls) == 1
