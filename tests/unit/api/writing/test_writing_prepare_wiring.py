"""Task 6c-1 wiring tests — writing domain resolves via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for the two bare ``get_model`` +
``agent.run()`` writing call sites — each resolves the model via the
SINGLE assembly point (``ModelRegistry.prepare``, Task 4) and forwards
the coherent ``(model, model_settings, usage_limits)`` triple to
``agent.run``:

- ``ChapterSummaryService.summarize`` (SUMMARIZE)
- ``StorySuggestService.suggest`` (SUGGEST)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these writing paths. The capability intent is a static property of
each site — the same intent the composer call sites (Mode 1 invocation
contexts, ``composer.build``) resolve for the two writing features
(``writing_summary``, ``writing_story_suggest``).

Out of scope (verified, already compliant): the interview-draft,
inline-suggest, and WS-turn streaming paths route through
``ModelRegistry.stream(intent=...)`` which applies
``build_runtime_model_settings`` internally (gateway.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.agents.story_suggest_types import (
    StorySuggestion,
    StorySuggestionType,
    StorySuggestOutput,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.schemas_story_suggest import StorySuggestRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b recording fake.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to ``agent.run`` is assertable), and the
    ``usage_limits`` pass-through. Calls are recorded in
    ``prepare_calls`` for wiring assertions.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))
        self.prepare_calls: list[dict[str, object]] = []

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        prepared = PreparedModelCall(
            model=model,
            model_settings={"max_tokens": 12_345},
            usage_limits=usage_limits,
        )
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": prepared,
            }
        )
        return prepared


class _FakeComposer:
    """Fake PromptComposer returning simple prompts."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
        )


class _ComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The services only read ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight attribute carrier is sufficient.
    """

    def __init__(self) -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(
            system="System prompt.", user="User prompt."
        )


def _assert_prepare_wiring(
    registry: _RecordingPrepareRegistry,
    config: ResolvedModelConfig,
    *,
    mock_agent_cls: MagicMock,
    intent: LLMIntent,
    api_key: str | None,
    base_url: str | None,
) -> None:
    """Assert the full Task-6c wiring contract for one agent invocation."""
    assert len(registry.prepare_calls) == 1
    call = registry.prepare_calls[0]
    assert call["config"] is config
    assert call["intent"] is intent
    assert call["api_key"] == api_key
    assert call["base_url"] == base_url
    # One prepare() → exactly one model resolution (no duplicate).
    registry.get_model.assert_awaited_once()
    # The coherent triple reaches the agent boundary, and the agent ran.
    prepared = call["prepared"]
    assert isinstance(prepared, PreparedModelCall)
    assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
    run_kwargs = mock_agent_cls.return_value.run.call_args.kwargs
    assert run_kwargs["model_settings"] is prepared.model_settings
    assert run_kwargs["usage_limits"] is prepared.usage_limits
    # Task 3 follow-up: the ADR-045 run-limit resolver is wired on these
    # writing paths — the pass-through value is a resolved, non-None
    # UsageLimits (capped to the config's max_tokens).
    assert prepared.usage_limits is not None
    assert mock_agent_cls.return_value.run.await_count == 1


class TestSummaryPrepareWiring:
    """ChapterSummaryAgent resolves via prepare(SUMMARIZE) with user credentials."""

    async def test_summarize_resolves_via_prepare_with_summarize_intent(self) -> None:
        from narrare.writing.summary_service import ChapterSummaryService
        from narrare_core.agents.summary_types import SummaryOutput
        from tests.factories import make_chapter
        from tests.unit.api.writing._writing_factories import (
            make_static_summary_runtime_factory,
        )

        registry = _RecordingPrepareRegistry()
        chapter = make_chapter(content="Once upon a time in a faraway land...", title="Chapter 1")
        chapter_repo = AsyncMock(get=AsyncMock(return_value=chapter), update_summary=AsyncMock())
        novel_repo = AsyncMock(
            get_by_id=AsyncMock(return_value=SimpleNamespace(id=uuid4(), user_id=uuid4()))
        )
        service = ChapterSummaryService(
            registry=cast("ModelRegistry", registry),
            # ADR-086 L38: the user credential triple arrives through the
            # frozen first-use runtime (verbatim values pinned below).
            runtime_factory=make_static_summary_runtime_factory(
                _user_config(), api_key=_USER_KEY, base_url=_USER_BASE_URL
            ),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            novel_repo=cast("NovelRepository", novel_repo),
            composer=cast("PromptComposer", _FakeComposer()),
        )
        output = MagicMock(spec=SummaryOutput)
        output.summary = "A hero begins their journey."
        output.word_count = 5
        output.key_points = ["Hero introduction"]
        agent = AsyncMock(run=AsyncMock(return_value=output))

        with (
            patch(
                "narrare.writing._summary_invocation.ChapterSummaryAgent",
                return_value=agent,
            ) as MockAgent,
            patch(
                "narrare.writing._summary_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            result = await service.summarize(
                chapter_id=chapter.id, max_sentences=3, user_id=str(uuid4())
            )

        # The config triple is the frozen runtime's (ADR-086 L38) — pinned
        # by identity, the exact object prepare() received.
        runtime = await service.ensure_resolved()
        _assert_prepare_wiring(
            registry,
            runtime.config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.SUMMARIZE,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        assert result.summary == "A hero begins their journey."


def _story_suggest_request() -> StorySuggestRequest:
    from narrare.writing.schemas_story_suggest import StorySuggestRequest

    return StorySuggestRequest(novel_id=uuid4(), chapter_id=None, author_instructions=None)


def _novel() -> MagicMock:
    """Mock novel carrying the real string values the service reads."""
    return MagicMock(
        spec=["title", "genre", "writing_language", "story_structure"],
        title="Test Novel",
        genre="Fantasy",
        writing_language="en",
        story_structure="three_act",
    )


def _story_suggest_output() -> StorySuggestOutput:
    return StorySuggestOutput(
        suggestions=[
            StorySuggestion(
                type=StorySuggestionType.PLOT_DEVELOPMENT,
                title="The Hidden Heir",
                description="A long-lost heir emerges from the shadows.",
                connection="Ties to the prophecy thread from chapter 3.",
            )
        ]
    )


class TestStorySuggestPrepareWiring:
    """StorySuggestAgent resolves via prepare(SUGGEST) — no credential
    overrides exist on this service (they default to None)."""

    async def test_suggest_resolves_via_prepare_with_suggest_intent(self) -> None:
        from narrare.writing.story_suggest_service import StorySuggestService

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        novel_repo = AsyncMock(get_by_id=AsyncMock(return_value=_novel()))
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare_core.llm.model_routing import ResolvedModel

        service = StorySuggestService(
            novel_repo=cast("NovelRepository", novel_repo),
            model_registry=cast("ModelRegistry", registry),
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=None, base_url=None, source="unit-test")
            ),
            composer=cast("PromptComposer", _FakeComposer()),
        )
        agent = AsyncMock(run=AsyncMock(return_value=_story_suggest_output()))
        request = _story_suggest_request()

        with (
            patch(
                "narrare_core.agents.story_suggest_agent.StorySuggestAgent",
                return_value=agent,
            ) as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            events = [event async for event in service.suggest(request.novel_id, uuid4(), request)]

        _assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.SUGGEST,
            api_key=None,
            base_url=None,
        )
        # The SSE stream terminates with the final done event.
        assert events[-1].is_final is True
