"""Fake memory-related service implementations for unit tests.

Provides:
    - ``FakeCoreFeedbackService`` — fake core FeedbackService for API-layer tests
    - ``FakeEventPublisher`` — fake EventPublisher for API-layer tests
    - ``FakePromptComposer`` — fake PromptComposer for analysis service tests

These Fakes are used when a test needs a service as a *dependency* of the SUT.
For example, MemoryFeedbackService depends on core FeedbackService and EventPublisher.
PreferenceAnalysisService depends on PromptComposer.

Usage:
    fake_core = FakeCoreFeedbackService()
    fake_publisher = FakeEventPublisher()
    service = MemoryFeedbackService(
        repository=fake_repo,
        core_feedback=fake_core,
        event_publisher=fake_publisher,
    )

    fake_composer = FakePromptComposer()
    await fake_composer.build(intent, context, user_prompt="...")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

from tests.fakes._shared import CallRecord


class FakeCoreFeedbackService:
    """In-memory fake for the core FeedbackService (FeedbackCollector protocol).

    Records events without any persistence or mem0 forwarding.
    """

    def __init__(self) -> None:
        self.recorded: list[Any] = []
        self.calls: list[CallRecord] = []

    async def record(self, event: Any) -> None:
        """Record a feedback event (in-memory only)."""
        self.calls.append(CallRecord("record"))
        self.recorded.append(event)

    async def get_history(
        self,
        user_id: object,
        project_id: object,
        *,
        limit: int = 100,
    ) -> list[Any]:
        """Return recorded events matching the user/project pair."""
        self.calls.append(
            CallRecord("get_history", kwargs={"user_id": user_id, "project_id": project_id})
        )
        return self.recorded[:limit]


class FakeEventPublisher:
    """In-memory fake for EventPublisher.

    Tracks published events for assertion in tests.
    Supports failure simulation via ``fail_on_publish()``.
    """

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.calls: list[CallRecord] = []
        self._should_fail: bool = False
        self._fail_error: Exception = ConnectionError("broker down")

    def fail_on_publish(self, error: Exception | None = None) -> None:
        """Configure ``publish_feedback_recorded`` to raise an error on next call.

        Args:
            error: The exception to raise. Defaults to ``ConnectionError("broker down")``.
        """
        self._should_fail = True
        if error is not None:
            self._fail_error = error

    async def publish_feedback_recorded(
        self, user_id: UUID, project_id: UUID, event_id: UUID
    ) -> None:
        """Track a feedback-recorded event, or raise if failure mode is active."""
        if self._should_fail:
            raise self._fail_error
        self.calls.append(
            CallRecord(
                "publish_feedback_recorded",
                kwargs={"user_id": user_id, "project_id": project_id, "event_id": event_id},
            )
        )
        self.published.append({"user_id": user_id, "project_id": project_id, "event_id": event_id})

    async def publish_analysis_triggered(
        self, user_id: UUID, project_id: UUID, event_count: int
    ) -> None:
        """Track an analysis-triggered event."""
        self.calls.append(
            CallRecord(
                "publish_analysis_triggered",
                kwargs={"user_id": user_id, "project_id": project_id, "event_count": event_count},
            )
        )
        self.published.append(
            {"user_id": user_id, "project_id": project_id, "event_count": event_count}
        )


class FakePromptComposer:
    """Fake PromptComposer that returns a fixed ComposedPrompt.

    Tracks all ``build()`` calls for assertion.

    Usage:
        composer = FakePromptComposer()
        result = await composer.build(intent, context, user_prompt="...")
        assert len(composer.build_calls) == 1
    """

    def __init__(self) -> None:
        self.build_calls: list[dict[str, Any]] = []

    async def build(
        self,
        intent: Any,
        context: Any,
        *,
        user_prompt: str = "",
    ) -> Any:
        """Record the build call and return a fixed ComposedPrompt.

        Args:
            intent: The LLMIntent for the prompt.
            context: PromptContext with metadata.
            user_prompt: Optional user-provided text.

        Returns:
            A concrete ``ComposedPrompt`` instance.
        """
        from narrare_core.prompts.composer import ComposedPrompt

        self.build_calls.append(
            {
                "intent": intent,
                "context": context,
                "user_prompt": user_prompt,
            }
        )
        return ComposedPrompt(
            system="You are a preference analyst.",
            user=user_prompt or "Analyze the following feedback history.",
        )
