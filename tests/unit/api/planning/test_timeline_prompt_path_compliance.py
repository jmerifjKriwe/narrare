"""Prompt-Path-Compliance tests for TimelineConsistencyService (CR-AUFG-02-06).

Verifies that temporal consistency prompt resolution goes through
``PromptComposer.build()`` (RULE-02b) and that dynamic event context is
passed in the user prompt channel, NOT baked into the system prompt.

See:
    ADR-046 — Prompt-Path-Compliance
    CR-02 retrofit spec, section CR-AUFG-02-06
    CONSTRAINTS.md RULE-02/02a/02b, RULE-07, RULE-11
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.planning.timeline_consistency_service import TimelineConsistencyService
from narrare_core.agents.timeline_types import TimelineOutput
from narrare_core.llm import ResolvedModelConfig

if TYPE_CHECKING:
    from narrare.planning.models import TimelineEvent
    from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeComposer:
    """Fake PromptComposer that records build() calls and returns a stub.

    The returned ``ComposedPrompt.system`` is intentionally distinct from any
    event data so tests can assert channel separation (system vs user).
    """

    def __init__(self, system_text: str = "COMPOSED-SYSTEM-PROMPT") -> None:
        self._system_text = system_text
        self.build = AsyncMock(side_effect=self._build_impl)
        # Recorded call args for assertions
        self.last_intent: object | None = None
        self.last_context: object | None = None

    async def _build_impl(
        self, intent: object, context: object, **_kwargs: object
    ) -> ComposedPrompt:
        from narrare_core.prompts.composer import ComposedPrompt

        self.last_intent = intent
        self.last_context = context
        return ComposedPrompt(system=self._system_text, user="")


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub model."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
) -> TimelineConsistencyService:
    """Build a TimelineConsistencyService wired for LLM checks."""
    return TimelineConsistencyService(
        event_repo=MagicMock(spec=["list_by_novel"]),
        novel_repo=MagicMock(spec=["get_by_id"]),
        character_age_service=None,
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        invocation_pipeline=None,
        composer=composer,  # type: ignore[arg-type]
    )


def _make_novel(
    title: str = "Test Novel", genre: str = "Fantasy", language: str = "en"
) -> MagicMock:
    novel = MagicMock(spec=["title", "genre", "writing_language"])
    novel.title = title
    novel.genre = genre
    novel.writing_language = language
    return novel


def _make_event(name: str = "The Battle", order: int = 1, raw: str = "year 1") -> MagicMock:
    event = MagicMock(spec=["event_name", "temporal_order", "timestamp_raw"])
    event.event_name = name
    event.temporal_order = order
    event.timestamp_raw = raw
    return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4096,
    )


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


# ---------------------------------------------------------------------------
# AC-1 / AC-7: Temporal consistency instructions resolve via PromptComposer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeline_consistency_uses_prompt_composer(
    config: ResolvedModelConfig,
    composer: FakeComposer,
) -> None:
    """REGRESSION (CR-AUFG-02-06): TimelineConsistencyService must resolve the
    temporal consistency system prompt via ``PromptComposer.build()``, not via
    the app-layer ``_prompt_loader.py``.

    Before ADR-046: ``_prompt_loader.py`` loaded the bundled template directly
    via ``importlib.resources`` + manual ``.replace()`` calls.

    After ADR-046: ``PromptComposer.build()`` resolves the prompt with proper
    cascade, variable validation, and override support.
    """
    service = _make_service(composer, config)
    novel = _make_novel()
    events = cast("list[TimelineEvent]", [_make_event()])

    with patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(
            return_value=MagicMock(spec=TimelineOutput, temporal_conflicts=[])
        )
        MockAgent.return_value = mock_agent

        await service._run_llm_checks(novel_id=uuid4(), events=events, novel=novel)

    # AC-1: PromptComposer.build() was called exactly once
    assert composer.build.called, "PromptComposer.build() was never called"
    composer.build.assert_awaited_once()

    # AC-1: build() was called with LLMIntent.PLAN
    from narrare_core.llm.intents import LLMIntent

    assert composer.last_intent == LLMIntent.PLAN, (
        f"Expected LLMIntent.PLAN, got {composer.last_intent!r}"
    )

    # AC-1: build() was called with mode="temporal_consistency" in the context
    context_mode = getattr(composer.last_context, "mode", None)
    assert context_mode == "temporal_consistency", (
        f"Expected mode='temporal_consistency', got {context_mode!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Dynamic event context in user prompt, NOT in system prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_context_in_user_prompt_not_system(
    config: ResolvedModelConfig,
    composer: FakeComposer,
) -> None:
    """AC-2: Event context (dynamic data) must be passed as the user prompt
    (``prompt=`` parameter), NOT baked into the system prompt.

    The system prompt comes entirely from ``PromptComposer.build()`` — it must
    not contain event data.
    """
    service = _make_service(composer, config)
    novel = _make_novel()
    events = cast(
        "list[TimelineEvent]",
        [_make_event(name="The Coronation", order=1, raw="spring 1242")],
    )

    captured_kwargs: dict[str, object] = {}

    with patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])

        async def capture_run(prompt: str, **kwargs: object) -> object:
            captured_kwargs["prompt"] = prompt
            captured_kwargs.update(kwargs)
            return MagicMock(spec=TimelineOutput, temporal_conflicts=[])

        mock_agent.run = capture_run
        MockAgent.return_value = mock_agent

        await service._run_llm_checks(novel_id=uuid4(), events=events, novel=novel)

    # The event data must appear in the user prompt (prompt= parameter)
    user_prompt = str(captured_kwargs.get("prompt", ""))
    assert "The Coronation" in user_prompt, (
        "Event data must be in the user prompt (prompt= parameter)"
    )

    # The system prompt must NOT contain the event data — it must be the
    # composed prompt from PromptComposer (our fake returns a distinct marker).
    system_prompt = str(captured_kwargs.get("system_prompt", ""))
    assert "The Coronation" not in system_prompt, (
        "Event data must NOT be baked into the system prompt"
    )
    assert system_prompt == "COMPOSED-SYSTEM-PROMPT", (
        "System prompt must come from PromptComposer.build(), not from a "
        "file loader or inline construction"
    )


# ---------------------------------------------------------------------------
# AC-8: No importlib.resources import for prompt loading
# ---------------------------------------------------------------------------


def test_no_importlib_resources_in_timeline_service() -> None:
    """AC-8: timeline_consistency_service.py must not import ``importlib.resources``
    for prompt loading.

    The app-layer ``_prompt_loader.py`` used ``importlib.resources.files()``
    to load bundled prompts directly — a RULE-02b violation. This test ensures
    the violation does not regress.
    """
    import inspect

    from narrare.planning import timeline_consistency_service as module

    source = inspect.getsource(module)
    assert "importlib.resources" not in source, (
        "timeline_consistency_service.py must not import importlib.resources "
        "(RULE-02b: prompt resolution is exclusively core/prompts/ responsibility)"
    )
    assert "importlib" not in source, (
        "timeline_consistency_service.py must not import importlib at all "
        "(RULE-02b: prompt resolution is exclusively core/prompts/ responsibility)"
    )


# ---------------------------------------------------------------------------
# AC-5: _prompt_loader.py is removed
# ---------------------------------------------------------------------------


def test_prompt_loader_module_removed() -> None:
    """AC-5: The app-layer ``_prompt_loader.py`` module must not exist.

    The module reimplemented cascade resolution and variable substitution in
    the app layer (RULE-02b/RULE-07 violation). ADR-046 CR-AUFG-02-06 removes
    it entirely.
    """
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("narrare.planning._prompt_loader")
