"""Unit tests for BetaReaderService — Phase 1 (analyze) orchestration.

Tests cache hit/miss, response mapping for the full analysis pipeline.
Split from test_beta_reader_service.py to stay under 300 lines (RULE-04).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.schemas import (
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare_core.agents.beta_reader_types import (
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from tests.unit.api.analysis._fakes import SpyInvocationPipeline

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

# Minimal protocols for spec'd mocks (RULE-TEST-01)


class _ModelRegistryProto(Protocol):
    async def get_model(self, config: object) -> object: ...


class _ComposedPromptProto(Protocol):
    system: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    cache_hit: str | None = None,
    phase1_output: BetaReaderPhase1Output | None = None,
    phase2_output: BetaReaderPhase2Output | None = None,
    word_count: int = 3000,
    invocation_pipeline: InvocationPipeline | None = None,
) -> BetaReaderService:
    """Create a BetaReaderService with mocked dependencies.

    Args:
        cache_hit: If set, the cache will return this value for get().
        phase1_output: If set, the agent will return this Phase 1 output.
        phase2_output: If set, the agent will return this Phase 2 output.
        word_count: Word count in the assembled context.
    """
    # Cache mock
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cache_hit)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.hash_chapter_ids = BetaReaderCache.hash_chapter_ids

    # Context assembler mock
    assembler = AsyncMock()
    deps = BetaReaderDeps(
        language="en",
        chapter_text="Test chapter content " * 200,
        chapter_titles=["Chapter 1"],
        word_count=word_count,
        genre="Fantasy",
    )
    assembler.build_context = AsyncMock(return_value=deps)

    # Registry mock — spec'd (RULE-TEST-01)
    registry = MagicMock(spec=_ModelRegistryProto)
    registry.get_model = AsyncMock(return_value=object())

    # Composer mock — composed is spec'd (RULE-TEST-01)
    composed = MagicMock(spec=_ComposedPromptProto)
    composed.system = "System prompt"
    composer = AsyncMock()
    composer.build = AsyncMock(return_value=composed)

    # Config — real instance instead of bare MagicMock (RULE-TEST-01)
    from narrare_core.llm import ResolvedModelConfig

    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test",
        temperature=0.7,
        max_tokens=4096,
    )

    service = BetaReaderService(
        context_assembler=assembler,
        cache=cache,
        registry=registry,
        config=config,
        composer=composer,
        invocation_pipeline=invocation_pipeline,
    )

    return service


def _sample_response() -> BetaReaderResponse:
    """Create a sample cached BetaReaderResponse."""
    from narrare.analysis.contracts import FeedbackCategory
    from narrare.analysis.schemas import (
        BetaReaderOverallAssessment,
        BetaReaderStrength,
    )

    return BetaReaderResponse(
        novel_id=str(uuid4()),
        chapter_ids=[str(uuid4())],
        total_word_count=3000,
        strengths=[
            BetaReaderStrength(
                category=FeedbackCategory.PLOT,
                title="Good plot",
                description="Engaging",
            )
        ],
        feedback=[],
        questions=[],
        overall=BetaReaderOverallAssessment(
            summary="Good",
            reader_engagement=7,
            emotional_impact=6,
            pacing_score=5,
            prose_quality=7,
            plot_progression=6,
            character_development=5,
        ),
        analyzed_at=datetime.now(tz=UTC).isoformat(),
        cache_key="abc123",
    )


# ---------------------------------------------------------------------------
# Cache hit returns cached response
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Cached result is returned without running the agent."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        """When cache has a result, it's returned directly."""
        cached_response = _sample_response()
        service = _make_service(cache_hit=cached_response.model_dump_json())

        result = await service.analyze(
            novel_id=uuid4(),
            user_id=uuid4(),
            request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
        )

        assert isinstance(result, BetaReaderResponse)
        assert result.novel_id == cached_response.novel_id


# ---------------------------------------------------------------------------
# Cache miss runs agent and caches
# ---------------------------------------------------------------------------


class TestCacheMiss:
    """Cache miss triggers full analysis pipeline."""

    @pytest.mark.asyncio
    async def test_cache_miss_runs_agent_and_caches(self) -> None:
        """When cache is empty, agent runs and result is cached."""
        service = _make_service(cache_hit=None, word_count=3000)

        # Mock the agent execution to return a known Phase 1 output
        phase1_output = BetaReaderPhase1Output(
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

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run_phase1 = AsyncMock(return_value=phase1_output)

        with patch(
            "narrare.analysis.beta_reader_service.BetaReaderAgent",
            return_value=mock_agent_instance,
        ):
            result = await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )

        assert isinstance(result, BetaReaderResponse)
        # Cache set should have been called
        service._cache.set.assert_awaited_once()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Response mapping correctness
# ---------------------------------------------------------------------------


class TestResponseMapping:
    """Phase 1 output maps correctly to public BetaReaderResponse."""

    def test_map_phase1_maps_fields(self) -> None:
        """All fields are mapped correctly."""
        from narrare.analysis.beta_reader_mapper import map_phase1_response
        from narrare.analysis.contracts import FeedbackCategory

        novel_id = uuid4()
        chapter_ids = [str(uuid4())]

        output = BetaReaderPhase1Output(
            strengths=[
                AgentStrength(
                    category="plot",
                    title="Strong plot",
                    description="Engaging narrative",
                    text_excerpt="excerpt",
                )
            ],
            feedback=[
                AgentFeedbackItem(
                    category="character",
                    severity="moderate",
                    title="Flat dialogue",
                    description="Needs work",
                    suggestion="Add personality",
                )
            ],
            questions=[
                AgentReaderQuestion(
                    category="plot",
                    question="Why now?",
                    context="Motivation unclear",
                )
            ],
            overall=AgentOverallAssessment(
                summary="Promising",
                reader_engagement=8,
                emotional_impact=7,
                pacing_score=6,
                prose_quality=7,
                plot_progression=8,
                character_development=5,
            ),
        )

        result = map_phase1_response(output, novel_id, chapter_ids, 3000)

        assert result.novel_id == str(novel_id)
        assert result.chapter_ids == chapter_ids
        assert result.total_word_count == 3000
        assert len(result.strengths) == 1
        assert result.strengths[0].category == FeedbackCategory.PLOT
        assert len(result.feedback) == 1
        assert result.feedback[0].severity.value == "moderate"
        assert len(result.questions) == 1
        assert result.overall.reader_engagement == 8


# ---------------------------------------------------------------------------
# Invocation composition — verifies compose_invocation (ADR-048 Mode 2)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify Phase 1 routes through compose_invocation, not safe_record_evidence."""

    @pytest.mark.asyncio
    async def test_phase1_compose_invocation_called(self) -> None:
        """Phase 1 analysis invokes compose_invocation with feature_id analysis_beta_read."""
        spy = SpyInvocationPipeline()
        service = _make_service(cache_hit=None, word_count=3000, invocation_pipeline=spy)

        phase1_output = BetaReaderPhase1Output(
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
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run_phase1 = AsyncMock(return_value=phase1_output)

        with patch(
            "narrare.analysis.beta_reader_service.BetaReaderAgent",
            return_value=mock_agent_instance,
        ):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )

        assert len(spy.prepare_calls) == 1
        assert spy.prepare_calls[0].feature_id == "analysis_beta_read"
        assert len(spy.finalize_calls) == 1
