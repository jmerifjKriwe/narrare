"""Shared test helpers for TimelineAnalysisService tests (RULE-04 split).

Provides the FakeComposer, model fixtures, and agent-mock helpers used by
both ``test_timeline_analysis_service.py`` (behavioural) and
``test_timeline_analysis_prompt_path.py`` (prompt-path compliance).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from narrare_core.prompts.composer import ComposedPrompt


class FakeComposer:
    """Fake PromptComposer that records build() calls and returns a stub.

    The returned ``ComposedPrompt.system`` carries a distinct marker so tests
    can assert the composed system prompt reaches the agent constructor
    (channel separation: system vs user).
    """

    def __init__(self, system_text: str = "COMPOSED-TIMELINE-SYSTEM") -> None:
        self._system_text = system_text
        self.build = AsyncMock(side_effect=self._build_impl)
        # Recorded call args for assertions
        self.last_intent: object | None = None
        self.last_context: object | None = None

    async def _build_impl(
        self,
        intent: object,
        context: object,
        **_kwargs: object,
    ) -> ComposedPrompt:
        from narrare_core.prompts.composer import ComposedPrompt

        self.last_intent = intent
        self.last_context = context
        # user is intentionally empty: the timeline template has no
        # "## First Message", so the service falls back to the chapter
        # context as the run prompt (runtime data in the user channel).
        return ComposedPrompt(system=self._system_text, user="")


def make_novel_model(**overrides: object) -> MagicMock:
    """Create a mock novel using Novel spec."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_chapter(**overrides: object) -> MagicMock:
    """Create a mock chapter using Chapter spec."""
    from narrare.chapters.models import Chapter

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Chapter 1"),
        "position": overrides.get("position", 0),
        "summary": overrides.get("summary", "A summary"),
        "timeline_position": overrides.get("timeline_position", "Day 1"),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=Chapter)
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


class _FakeEvent:
    """Stand-in for a serialised timeline event."""

    def model_dump(self) -> dict[str, object]:
        return {
            "event_name": "Battle",
            "description": "",
            "timestamp": "Day 1",
            "chapter_reference": "Ch 1",
            "characters_involved": [],
            "location": "",
            "causes": [],
            "consequences": [],
        }


class _FakeAgentResult:
    """Stand-in for the TimelineAgent.run return value."""

    def __init__(self) -> None:
        self.timeline_events = [_FakeEvent()]
        self.temporal_conflicts = ["Conflict 1"]
        self.coverage_gaps = ["Gap 1"]
        self.overall_assessment = "Good"


def fake_agent_result() -> object:
    """Build a fake TimelineAgent.run result."""
    return _FakeAgentResult()


def make_mock_agent() -> MagicMock:
    """Build a TimelineAgent mock with a spec (RULE-TEST-01).

    Returns a ``MagicMock(spec=["run"])`` whose ``run`` is an AsyncMock
    returning a fake agent result. Callers that need to capture the run
    prompt can override ``mock_agent.run``.
    """
    mock_agent = MagicMock(spec=["run"])
    mock_agent.run = AsyncMock(return_value=fake_agent_result())
    return mock_agent
