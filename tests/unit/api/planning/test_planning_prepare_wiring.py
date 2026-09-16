"""Task 6b-2 wiring tests — planning domain resolves via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for the planning call sites —
each resolves the model via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) and forwards the coherent
``(model, model_settings, usage_limits)`` triple to ``agent.run``:

- ``TimelineAnalysisService.generate_timeline`` (PLAN)
- ``TimelineExtractionService.stream_extraction`` (PLAN)
- ``_timeline_consistency_helpers.run_llm_consistency_checks`` (PLAN)

(The fourth site, ``CharacterArcService.generate_character_arc``, lives
in ``test_character_arc_prepare_wiring.py`` — RULE-04 split when the
ADR-086 L20 slice's ctor migration crossed the 400-line test limit; the
shared fixtures moved to ``_prepare_wiring_helpers.py``.)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these planning paths. The capability intent is a static property of
each site — PLAN, the same intent the composer call sites (Mode 1
invocation contexts, ``composer.build``) resolve for the planning
features (timeline analysis/extraction/consistency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.agents.temporal_extraction_types import TemporalExtractionOutput
from narrare_core.llm.intents import LLMIntent
from tests.unit.api.planning._prepare_wiring_helpers import (
    USER_BASE_URL,
    USER_KEY,
    ComposedInvocation,
    RecordingPrepareRegistry,
    as_model_registry,
    assert_prepare_wiring,
    composer,
    novel,
    novel_repo_with,
    static_resolution,
    user_config,
)

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.planning.models import TimelineEvent


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


class TestTimelineAnalysisPrepareWiring:
    """TimelineAgent resolves via prepare(PLAN) with user credentials."""

    async def test_timeline_analysis_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.timeline_analysis_service import TimelineAnalysisService

        config = user_config()
        registry = RecordingPrepareRegistry()
        chapter_repo = AsyncMock(list_by_novel=AsyncMock(return_value=[_chapter()]))
        service = TimelineAnalysisService(
            novel_repo=novel_repo_with(novel()),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=as_model_registry(registry),
            model_resolution=static_resolution(config),
            composer=composer(),
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

        assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=USER_KEY,
            base_url=USER_BASE_URL,
        )


class TestTimelineExtractionPrepareWiring:
    """TemporalExtractionAgent resolves via prepare(PLAN) with user credentials
    (ADR-086 L24: the resolved triple threads through the lazy seam)."""

    async def test_timeline_extraction_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.timeline_extraction_service import TimelineExtractionService

        config = user_config()
        registry = RecordingPrepareRegistry()
        chapter_repo = AsyncMock(list_by_novel=AsyncMock(return_value=[_chapter()]))
        service = TimelineExtractionService(
            novel_repo=novel_repo_with(novel()),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=as_model_registry(registry),
            model_resolution=static_resolution(config),
            composer=composer(),
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
                new=AsyncMock(return_value=ComposedInvocation()),
            ),
        ):
            yielded = [event async for event in service.stream_extraction(uuid4(), uuid4(), None)]

        assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=USER_KEY,
            base_url=USER_BASE_URL,
        )
        # The single chapter produced no expressions — nothing streamed.
        assert yielded == []


class TestTimelineConsistencyHelpersPrepareWiring:
    """The LLM consistency-check helper resolves via prepare(PLAN)."""

    async def test_llm_consistency_checks_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning._timeline_consistency_helpers import run_llm_consistency_checks

        config = user_config()
        registry = RecordingPrepareRegistry()
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
                new=AsyncMock(return_value=ComposedInvocation()),
            ),
        ):
            issues = await run_llm_consistency_checks(
                events=cast("list[TimelineEvent]", events),
                novel=novel(),
                novel_id=uuid4(),
                registry=as_model_registry(registry),
                config=config,
                composer=composer(),
                invocation_pipeline=None,
            )

        assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=None,
            base_url=None,
        )
        # No conflicts found — the helper surfaces no LLM issues.
        assert issues == []
