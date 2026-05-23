"""Unit tests for PreferenceAnalysisService — analysis orchestration."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from narrare.memory.schemas import AnalyzeResponse
from narrare_core.prompts.composer import ComposedPrompt


class FakeFeedbackRepo:
    """Fake FeedbackRepository for testing."""

    def __init__(self, event_count: int = 10) -> None:
        self._event_count = event_count
        self._events: list[Any] = []

    async def get_event_count(self, user_id: Any, project_id: Any) -> int:
        return self._event_count

    async def get_events_batch(
        self, user_id: Any, project_id: Any, *, limit: int = 50
    ) -> list[Any]:
        return self._events


class FakeProfileRepo:
    """Fake PreferenceProfileRepository for testing."""

    def __init__(self) -> None:
        self._profiles: dict[str, Any] = {}

    async def upsert(self, profile: Any) -> Any:
        from datetime import UTC, datetime

        if profile.id is None:
            profile.id = uuid4()
        if profile.created_at is None:
            profile.created_at = datetime.now(UTC)
        if profile.updated_at is None:
            profile.updated_at = datetime.now(UTC)
        key = f"{profile.user_id}:{profile.project_id}"
        self._profiles[key] = profile
        return profile

    async def get(self, user_id: Any, project_id: Any) -> Any | None:
        key = f"{user_id}:{project_id}"
        return self._profiles.get(key)


def _make_composer() -> AsyncMock:
    """Create a mock PromptComposer that returns a ComposedPrompt."""
    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a preference analyst.",
            user="Analyze the following feedback history.",
        )
    )
    return composer


class TestPreferenceAnalysisService:
    def _make_service(self, event_count: int = 10) -> tuple[Any, FakeFeedbackRepo, FakeProfileRepo]:
        from narrare.memory.analysis_service import PreferenceAnalysisService

        registry = MagicMock()  # narrare: allow-mock — Mocking ModelRegistry for service unit test
        feedback_repo = FakeFeedbackRepo(event_count=event_count)
        profile_repo = FakeProfileRepo()
        composer = _make_composer()
        service = PreferenceAnalysisService(
            registry=registry,
            feedback_repo=feedback_repo,  # type: ignore[arg-type]
            profile_repo=profile_repo,  # type: ignore[arg-type]
            composer=composer,
        )
        return service, feedback_repo, profile_repo

    async def test_analyze_raises_with_too_few_events(self) -> None:
        service, _, _ = self._make_service(event_count=3)

        try:
            await service.analyze(uuid4(), uuid4())
            raise AssertionError("Should have raised ValueError")
        except ValueError as exc:
            assert "at least 5" in str(exc)

    async def test_analyze_with_enough_events_succeeds(self) -> None:
        service, feedback_repo, _ = self._make_service(event_count=10)
        # Seed some fake events
        for _ in range(10):
            event = MagicMock()  # narrare: allow-mock — Fake feedback event for service test
            event.action = "accept"
            event.intent = "write"
            event.suggestion_text = "Good text."
            event.modification = None
            event.rating = None
            feedback_repo._events.append(event)

        user_id = uuid4()
        project_id = uuid4()
        result = await service.analyze(user_id, project_id)

        assert isinstance(result, AnalyzeResponse)
        assert result.user_id == user_id
        assert result.project_id == project_id

    async def test_get_profile_returns_none_when_not_found(self) -> None:
        service, _, _ = self._make_service()
        result = await service.get_profile(uuid4(), uuid4())
        assert result is None

    async def test_get_profile_returns_after_analyze(self) -> None:
        service, feedback_repo, _profile_repo = self._make_service(event_count=10)
        for _ in range(10):
            event = MagicMock()  # narrare: allow-mock — Fake feedback event for service test
            event.action = "accept"
            event.intent = "write"
            event.suggestion_text = "Text."
            event.modification = None
            event.rating = None
            feedback_repo._events.append(event)

        user_id = uuid4()
        project_id = uuid4()
        await service.analyze(user_id, project_id)

        profile = await service.get_profile(user_id, project_id)
        assert profile is not None
        assert profile.user_id == user_id

    def test_format_events_includes_rating(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService

        event = MagicMock()  # narrare: allow-mock — Fake feedback event for format test
        event.action = "accept"
        event.intent = "write"
        event.suggestion_text = "Short."
        event.modification = None
        event.rating = 4

        text = PreferenceAnalysisService._format_events_for_agent([event])
        assert "rating: 4/5" in text

    def test_format_events_includes_modification(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService

        event = MagicMock()  # narrare: allow-mock — Fake feedback event for format test
        event.action = "modify"
        event.intent = "edit"
        event.suggestion_text = "Original."
        event.modification = "Changed."
        event.rating = None

        text = PreferenceAnalysisService._format_events_for_agent([event])
        assert "modified to" in text
