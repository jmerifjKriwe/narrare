"""Shared test helpers for TimelineAnalysisService tests (RULE-04 split).

Provides the FakeComposer, model fixtures, and agent-mock helpers used by
both ``test_timeline_analysis_service.py`` (behavioural) and
``test_timeline_analysis_prompt_path.py`` (prompt-path compliance).

Since ADR-086 L22/L23 the timeline services consume model routing as a
``ModelResolution`` instead of a pre-resolved ``model_config``; the
resolution shims below mirror ``_storyboard_test_helpers.py`` (L21
convention):

- ``make_resolved_model`` builds the canned triple the routing cascade
  would return, used by both static and counting resolutions.
- ``make_static_resolution`` covers the mechanical ctor migration of the
  existing fixtures to ``StaticModelResolution`` (ADR-086 regression
  contract #4 — outcomes unchanged).
- ``NoProviderResolution`` simulates the no-provider cascade outcome
  (``ConfigurationError``) for the graceful-degradation nodes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from narrare_core.prompts.composer import ComposedPrompt

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.7,
)


def make_resolved_model(**kw: str | None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=_CASCADE_CONFIG,
        api_key=kw.get("api_key"),
        base_url=kw.get("base_url"),
        source="unit-test",
    )


def make_static_resolution(**kw: str | None) -> StaticModelResolution:
    """A ``StaticModelResolution`` over a canned triple — fixture shim."""
    return StaticModelResolution(make_resolved_model(**kw))


class NoProviderResolution:
    """Fake ``ModelResolution`` — the cascade finds no provider configured.

    Stands in for the eager factory's wiring-time ``except
    ConfigurationError`` swallow, which is first-use service policy after
    ADR-086 L22/L23 (the graceful degradation nodes assert the preserved
    outcomes against this fake).
    """

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")


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
