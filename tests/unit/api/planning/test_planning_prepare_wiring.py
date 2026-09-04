"""Task 6b-2 wiring tests — planning domain resolves via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for the four planning call
sites — each resolves the model via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) and forwards the coherent
 ``(model, model_settings, usage_limits)`` triple to ``agent.run``:

- ``CharacterArcService.generate_character_arc`` (PLAN)
- ``TimelineAnalysisService.generate_timeline`` (PLAN)
- ``TimelineExtractionService.stream_extraction`` (PLAN)
- ``_timeline_consistency_helpers.run_llm_consistency_checks`` (PLAN)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these planning paths. The capability intent is a static property of
each site — PLAN, the same intent the composer call sites (Mode 1
invocation contexts, ``composer.build``) resolve for the four planning
features (``planning_character_arc``, timeline analysis/extraction/
consistency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare.planning.schemas import CharacterArcRequest
from narrare_core.agents.character_arc_types import CharacterArcOutput
from narrare_core.agents.temporal_extraction_types import TemporalExtractionOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.models import TimelineEvent
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

    async def build(self, intent: object, context: object) -> ComposedPrompt:
        return ComposedPrompt(system="System prompt.", user="User prompt.")


class _ComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The services only read ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight attribute carrier is sufficient.
    """

    def __init__(self) -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(
            system="System prompt.", user="User prompt."
        )


def _novel() -> MagicMock:
    """Mock novel carrying the real string values the services read."""
    return MagicMock(
        spec=["title", "genre", "writing_language"],
        title="Test Novel",
        genre="Fantasy",
        writing_language="en",
    )


def _chapter(**overrides: object) -> MagicMock:
    """Mock chapter carrying the real values ``format_chapter_context`` reads."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "position": 0,
        "title": "Chapter 1",
        "summary": "Three days later, the hero arrived at the castle.",
        "timeline_position": "day 1",
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=["id", "position", "title", "summary", "timeline_position"])
    for key, value in defaults.items():
        setattr(chapter, key, value)
    return chapter


def _arc_request() -> CharacterArcRequest:
    return CharacterArcRequest(
        character_name="Lyra",
        character_current_state="A timid orphan",
        character_goal_state="A confident leader",
    )


def _arc_output() -> CharacterArcOutput:
    return CharacterArcOutput(
        character_name="Lyra",
        starting_state="timid",
        ending_state="confident",
        arc_type="growth",
        phases=[],
        key_relationships=[],
        internal_conflict="fear vs duty",
        resolution="embraces duty",
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
    """Assert the full Task-6a wiring contract for one agent invocation."""
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
    # No run-limit resolver is wired on these planning paths (Task 6b-2
    # concern): the pass-through value is None (no output caps).
    assert prepared.usage_limits is None
    assert mock_agent_cls.return_value.run.await_count == 1


class TestCharacterArcPrepareWiring:
    """CharacterArcAgent resolves via prepare(PLAN) with user credentials."""

    async def test_character_arc_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.character_arc_service import CharacterArcService

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        service = CharacterArcService(
            novel_repo=cast(
                "NovelRepository", AsyncMock(get_by_id=AsyncMock(return_value=_novel()))
            ),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", _FakeComposer()),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        agent = AsyncMock(run=AsyncMock(return_value=_arc_output()))

        with (
            patch(
                "narrare_core.agents.character_arc_agent.CharacterArcAgent",
                return_value=agent,
            ) as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            await service.generate_character_arc(uuid4(), uuid4(), _arc_request())

        _assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )


class TestTimelineAnalysisPrepareWiring:
    """TimelineAgent resolves via prepare(PLAN) with user credentials."""

    async def test_timeline_analysis_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.timeline_analysis_service import TimelineAnalysisService

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        chapter_repo = AsyncMock(list_by_novel=AsyncMock(return_value=[_chapter()]))
        service = TimelineAnalysisService(
            novel_repo=cast(
                "NovelRepository", AsyncMock(get_by_id=AsyncMock(return_value=_novel()))
            ),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", _FakeComposer()),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        agent = AsyncMock(
            run=AsyncMock(
                return_value=MagicMock(
                    spec=[
                        "timeline_events",
                        "temporal_conflicts",
                        "coverage_gaps",
                        "overall_assessment",
                    ],
                    timeline_events=[],
                    temporal_conflicts=[],
                    coverage_gaps=[],
                    overall_assessment="No issues.",
                )
            )
        )

        with patch(
            "narrare_core.agents.timeline_agent.TimelineAgent", return_value=agent
        ) as MockAgent:
            await service.generate_timeline(uuid4(), uuid4())

        _assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )


class TestTimelineExtractionPrepareWiring:
    """TemporalExtractionAgent resolves via prepare(PLAN) — no credential
    overrides exist on this service (they default to None)."""

    async def test_timeline_extraction_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.timeline_extraction_service import TimelineExtractionService

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        chapter_repo = AsyncMock(list_by_novel=AsyncMock(return_value=[_chapter()]))
        service = TimelineExtractionService(
            novel_repo=cast(
                "NovelRepository", AsyncMock(get_by_id=AsyncMock(return_value=_novel()))
            ),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", _FakeComposer()),
        )
        agent = AsyncMock(
            run=AsyncMock(
                return_value=TemporalExtractionOutput(
                    extracted=[],
                    chapter_temporal_markers=[],
                    extraction_notes="",
                )
            )
        )

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
                return_value=agent,
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            yielded = [event async for event in service.stream_extraction(uuid4(), uuid4(), None)]

        _assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=None,
            base_url=None,
        )
        # The single chapter produced no expressions — nothing streamed.
        assert yielded == []


class TestTimelineConsistencyHelpersPrepareWiring:
    """The LLM consistency-check helper resolves via prepare(PLAN)."""

    async def test_llm_consistency_checks_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning._timeline_consistency_helpers import run_llm_consistency_checks

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        events = [
            MagicMock(
                spec=["event_name", "temporal_order", "timestamp_raw"],
                event_name="Coronation",
                temporal_order=1,
                timestamp_raw="day 1",
            )
        ]
        agent = AsyncMock(
            run=AsyncMock(
                return_value=MagicMock(spec=["temporal_conflicts"], temporal_conflicts=[])
            )
        )

        with (
            patch(
                "narrare_core.agents.timeline_agent.TimelineAgent", return_value=agent
            ) as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            issues = await run_llm_consistency_checks(
                events=cast("list[TimelineEvent]", events),
                novel=_novel(),
                novel_id=uuid4(),
                registry=cast("ModelRegistry", registry),
                config=config,
                composer=cast("PromptComposer", _FakeComposer()),
                invocation_pipeline=None,
            )

        _assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=None,
            base_url=None,
        )
        # No conflicts found — the helper surfaces no LLM issues.
        assert issues == []
