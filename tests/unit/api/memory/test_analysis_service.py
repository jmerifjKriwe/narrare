"""Unit tests for PreferenceAnalysisService — analysis orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic_ai.models.test import (
    TestModel,
)  # narrare: allow-agent reason="unit test registry returns pydantic-ai TestModel"

from narrare.memory.schemas import AnalyzeResponse
from narrare_core.llm.gateway import ModelRegistry
from tests.fakes import FakeFeedbackRepository, FakePreferenceProfileRepository, FakePromptComposer

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import ResolvedModelConfig


@dataclass
class FakeFeedbackEvent:
    """Minimal fake feedback event for analysis service tests.

    Provides the same attributes accessed by
    ``PreferenceAnalysisService._format_events_for_agent``.
    """

    action: str = "accept"
    intent: str = "write"
    suggestion_text: str = "Good text."
    modification: str | None = None
    rating: int | None = None
    context: dict[str, Any] = field(default_factory=dict)


class FakeModelRegistry(ModelRegistry):
    """ModelRegistry test double that returns a valid pydantic-ai test model."""

    def __init__(self, model: TestModel | None = None) -> None:
        self.model = model or TestModel()

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> TestModel:
        """Return the configured pydantic-ai TestModel without provider lookup."""
        return self.model


class TestPreferenceAnalysisService:
    def _make_service(
        self, event_count: int = 10
    ) -> tuple[Any, FakeFeedbackRepository, FakePreferenceProfileRepository]:
        from narrare.memory.analysis_service import PreferenceAnalysisService
        from narrare_core.llm import ResolvedModelConfig

        registry = FakeModelRegistry()
        feedback_repo = FakeFeedbackRepository()
        profile_repo = FakePreferenceProfileRepository()
        composer = FakePromptComposer()
        service = PreferenceAnalysisService(
            registry=registry,
            feedback_repo=feedback_repo,
            profile_repo=profile_repo,
            composer=composer,
            config=ResolvedModelConfig(
                provider_name="zai",
                model_id="glm-4.7",
                temperature=0.7,
                max_tokens=4096,
            ),
        )
        return service, feedback_repo, profile_repo

    def _seed_events(
        self,
        feedback_repo: FakeFeedbackRepository,
        user_id: object,
        project_id: object,
        count: int,
    ) -> None:
        """Seed the fake repo with minimal event-like objects for analysis."""
        from narrare.memory.models import FeedbackEventModel

        for _ in range(count):
            event = FeedbackEventModel(
                user_id=user_id,  # type: ignore[arg-type]
                project_id=project_id,  # type: ignore[arg-type]
                suggestion_id=uuid4(),
                action="accept",
                intent="write",
                suggestion_text="Seeded event.",
            )
            feedback_repo.seed(event)

    async def test_analyze_raises_with_too_few_events(self) -> None:
        service, feedback_repo, _ = self._make_service()
        user_id = uuid4()
        project_id = uuid4()
        self._seed_events(feedback_repo, user_id, project_id, 3)

        try:
            await service.analyze(user_id, project_id)
            raise AssertionError("Should have raised ValueError")
        except ValueError as exc:
            assert "at least 5" in str(exc)

    async def test_analyze_with_enough_events_succeeds(self) -> None:
        service, feedback_repo, _ = self._make_service()
        user_id = uuid4()
        project_id = uuid4()
        self._seed_events(feedback_repo, user_id, project_id, 10)

        result = await service.analyze(user_id, project_id)

        assert isinstance(result, AnalyzeResponse)
        assert result.user_id == user_id
        assert result.project_id == project_id

    async def test_get_profile_returns_none_when_not_found(self) -> None:
        service, _, _ = self._make_service()
        result = await service.get_profile(uuid4(), uuid4())
        assert result is None

    async def test_get_profile_returns_after_analyze(self) -> None:
        service, feedback_repo, _ = self._make_service()
        user_id = uuid4()
        project_id = uuid4()
        self._seed_events(feedback_repo, user_id, project_id, 10)

        await service.analyze(user_id, project_id)

        profile = await service.get_profile(user_id, project_id)
        assert profile is not None
        assert profile.user_id == user_id

    def test_format_events_includes_rating(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService

        event = FakeFeedbackEvent(rating=4)

        text = PreferenceAnalysisService._format_events_for_agent([event])  # type: ignore[arg-type]
        assert "rating: 4/5" in text

    def test_format_events_includes_modification(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService

        event = FakeFeedbackEvent(
            action="modify", intent="edit", suggestion_text="Original.", modification="Changed."
        )

        text = PreferenceAnalysisService._format_events_for_agent([event])  # type: ignore[arg-type]
        assert "modified to" in text
