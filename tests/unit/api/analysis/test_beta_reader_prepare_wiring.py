"""Task 7 wiring tests — beta reader resolves via ModelRegistry.prepare().

Pins the Task-6a-6d structural contract for the last two bare
``get_model`` call sites in the analysis domain — the model is resolved
via the SINGLE assembly point (``ModelRegistry.prepare``, Task 4) and
the coherent ``(model, model_settings, usage_limits)`` triple is
forwarded to the agent run:

- ``BetaReaderService.analyze`` (BETA_READ, phase 1) — the full triple
  reaches ``agent.run_phase1`` through the ``run_phase1`` runner helper.
- ``BetaReaderService.deep_dive`` (BETA_READ, phase 2) — the full triple
  reaches ``agent.run_phase2`` through the ``run_phase2`` runner helper
  (core kwargs pass-through landed in Task 1; service-side wiring into
  ``run_phase2`` landed in Task 2 of the follow-ups plan).

Root cause pinned here (structural audit): the sites resolved via bare
``get_model`` and ran the agent with NO model_settings and NO
usage_limits, so the intent-aware thinking policy and the ADR-045
output cap never applied to the beta-reader path. The capability intent
(``LLMIntent.BETA_READ``) is a static property of the site — the same
intent both invocation contexts (``analysis_beta_read`` /
``analysis_beta_read_deepdive``) already resolve.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.contracts import FeedbackCategory
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderOverallAssessment,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import (
    AgentOverallAssessment,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b/6c recording fakes.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to the agent run is assertable), and the
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


def _phase1_output() -> BetaReaderPhase1Output:
    return BetaReaderPhase1Output(
        strengths=[],
        feedback=[],
        questions=[],
        overall=AgentOverallAssessment(
            summary="Test",
            reader_engagement=5,
            emotional_impact=5,
            pacing_score=5,
            prose_quality=5,
            plot_progression=5,
            character_development=5,
        ),
    )


def _make_service(
    registry: _RecordingPrepareRegistry,
    config: ResolvedModelConfig,
    *,
    cache_hit: str | None = None,
) -> BetaReaderService:
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cache_hit)
    cache.set = AsyncMock()
    cache.hash_chapter_ids = BetaReaderCache.hash_chapter_ids

    assembler = AsyncMock()
    deps = BetaReaderDeps(
        language="en",
        chapter_text="Test chapter content " * 200,
        chapter_titles=["Chapter 1"],
        word_count=3000,
        genre="Fantasy",
    )
    assembler.build_context = AsyncMock(return_value=deps)

    composed = MagicMock(spec=["system"])
    composed.system = "System prompt"
    composer = AsyncMock()
    composer.build = AsyncMock(return_value=composed)

    return BetaReaderService(
        context_assembler=assembler,
        cache=cache,
        registry=cast("ModelRegistry", registry),
        config=config,
        composer=composer,
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


def _cached_phase1_response() -> BetaReaderResponse:
    return BetaReaderResponse(
        novel_id=str(uuid4()),
        chapter_ids=[str(uuid4())],
        total_word_count=3000,
        strengths=[],
        feedback=[],
        questions=[],
        overall=BetaReaderOverallAssessment(
            summary="Good",
            reader_engagement=5,
            emotional_impact=5,
            pacing_score=5,
            prose_quality=5,
            plot_progression=5,
            character_development=5,
        ),
        analyzed_at=datetime.now(tz=UTC).isoformat(),
        cache_key="abc123",
    )


class TestBetaReaderPrepareWiring:
    """Beta reader resolves via prepare(BETA_READ) + user credentials."""

    async def test_analyze_resolves_via_prepare_and_forwards_triple(self) -> None:
        config = _user_config()
        registry = _RecordingPrepareRegistry()
        service = _make_service(registry, config)

        agent = AsyncMock()
        agent.run_phase1 = AsyncMock(return_value=_phase1_output())

        with patch(
            "narrare.analysis.beta_reader_service.BetaReaderAgent",
            return_value=agent,
        ) as mock_agent_cls:
            response = await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )

        # The full pipeline ran (mapping worked on the real output).
        assert isinstance(response, BetaReaderResponse)
        # Single assembly point with the site intent + user credentials.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.BETA_READ
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        registry.get_model.assert_awaited_once()
        # The coherent triple reaches the agent boundary, and the agent ran.
        prepared = cast("PreparedModelCall", call["prepared"])
        assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
        run_kwargs: dict[str, Any] = agent.run_phase1.call_args.kwargs
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
        # No run-limit resolver is wired on this path (Task 7 concern,
        # same as 6a/6b/6c/6d): the pass-through value is None.
        assert prepared.usage_limits is None
        agent.run_phase1.assert_awaited_once()

    async def test_deep_dive_resolves_via_prepare_and_forwards_full_triple(self) -> None:
        config = _user_config()
        registry = _RecordingPrepareRegistry()
        phase1 = _cached_phase1_response()
        service = _make_service(registry, config, cache_hit=phase1.model_dump_json())

        agent = AsyncMock()
        agent.run_phase2 = AsyncMock(
            return_value=BetaReaderPhase2Output(
                detailed_feedback=[],
                revision_suggestions=[],
                category_score=5,
            )
        )

        with patch(
            "narrare.analysis.beta_reader_service.BetaReaderAgent",
            return_value=agent,
        ):
            response = await service.deep_dive(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderDeepDiveRequest(
                    chapter_ids=[str(uuid4())],
                    category=FeedbackCategory.PLOT,
                    cache_key="abc123",
                ),
            )

        assert response.detailed_feedback == []
        # Single assembly point for the phase-2 site as well.
        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is config
        assert call["intent"] is LLMIntent.BETA_READ
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        registry.get_model.assert_awaited_once()
        prepared = cast("PreparedModelCall", call["prepared"])
        # The full prepared triple flows into the phase-2 agent run
        # (Task 2 service-side wiring through the run_phase2 helper).
        run_kwargs: dict[str, Any] = agent.run_phase2.call_args.kwargs
        assert run_kwargs["model"] is prepared.model
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits

    async def test_prepared_settings_reach_the_phase2_agent_run_site(self) -> None:
        """Core pass-through landed (Task 1): ``run_phase2`` kwargs reach
        the ephemeral phase-2 agent's inner run.

        Former CORE BOUNDARY pin (RULE-01b): ``BetaReaderAgent.run_phase2``
        ran the phase-2 agent without ``model_settings``/``usage_limits``.
        The kwargs now flow through; the service-side wiring that passes
        ``prepared.model_settings``/``prepared.usage_limits`` from
        ``deep_dive`` landed as Task 2 (pinned in the deep-dive wiring
        test above).
        """
        agent = BetaReaderAgent(model=TestModel())
        deps = BetaReaderDeps(chapter_text="Test chapter content.")
        expected = BetaReaderPhase2Output(
            detailed_feedback=[],
            revision_suggestions=[],
            category_score=5,
        )
        sentinel_settings: ModelSettings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        with patch.object(NarrareAgent, "run", new=AsyncMock(return_value=expected)) as mock_run:
            result = await agent.run_phase2(
                "Deep-dive on plot",
                deps,
                model=TestModel(),
                system_prompt="Phase 2 system prompt.",
                model_settings=sentinel_settings,
                usage_limits=sentinel_limits,
            )

        assert result is expected
        run_call = mock_run.call_args
        assert run_call is not None
        assert run_call.kwargs["model_settings"] is sentinel_settings
        assert run_call.kwargs["usage_limits"] is sentinel_limits
