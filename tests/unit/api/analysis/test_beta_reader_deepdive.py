"""Unit tests for BetaReaderService — Phase 2 (deepdive) and validation.

Tests Phase 2 cache miss error and word count validation.
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
from narrare.analysis.contracts import FeedbackCategory
from narrare.analysis.errors import (
    CacheRetrievalError,
    ExcessiveWordCountError,
    InsufficientWordCountError,
)
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderOverallAssessment,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare_core.agents.beta_reader_types import BetaReaderDeps, BetaReaderPhase2Output
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
    word_count: int = 3000,
    invocation_pipeline: InvocationPipeline | None = None,
) -> BetaReaderService:
    """Create a BetaReaderService with mocked dependencies.

    Args:
        cache_hit: If set, the cache will return this value for get().
        word_count: Word count in the assembled context.
    """
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cache_hit)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.hash_chapter_ids = BetaReaderCache.hash_chapter_ids

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

    return BetaReaderService(
        context_assembler=assembler,
        cache=cache,
        registry=registry,
        config=config,
        composer=composer,
        invocation_pipeline=invocation_pipeline,
    )


# ---------------------------------------------------------------------------
# Phase 2 cache miss raises
# ---------------------------------------------------------------------------


class TestPhase2CacheMiss:
    """Phase 2 without Phase 1 cache raises CacheRetrievalError."""

    @pytest.mark.asyncio
    async def test_phase2_without_phase1_raises(self) -> None:
        """Deep-dive without prior Phase 1 analysis raises error."""
        service = _make_service(cache_hit=None)

        with pytest.raises(CacheRetrievalError):
            await service.deep_dive(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderDeepDiveRequest(
                    chapter_ids=[str(uuid4())],
                    category=FeedbackCategory.PLOT,
                    cache_key="abc123",
                ),
            )


# ---------------------------------------------------------------------------
# Word count validation
# ---------------------------------------------------------------------------


class TestWordCountValidation:
    """Word count outside [1000, 10000] raises errors."""

    @pytest.mark.asyncio
    async def test_too_short_raises(self) -> None:
        """Word count below 1000 raises InsufficientWordCountError."""
        service = _make_service(cache_hit=None, word_count=500)

        with pytest.raises(InsufficientWordCountError):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )

    @pytest.mark.asyncio
    async def test_too_long_raises(self) -> None:
        """Word count above 10000 raises ExcessiveWordCountError."""
        service = _make_service(cache_hit=None, word_count=15000)

        with pytest.raises(ExcessiveWordCountError):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderRequest(chapter_ids=[str(uuid4())]),
            )


# ---------------------------------------------------------------------------
# Invocation composition — verifies compose_invocation (ADR-048 Mode 2)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify Phase 2 routes through compose_invocation, not safe_record_evidence."""

    @pytest.mark.asyncio
    async def test_phase2_compose_invocation_called(self) -> None:
        """Deep-dive invokes compose_invocation with feature_id analysis_beta_read_deepdive."""
        phase1_cached = BetaReaderResponse(
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

        spy = SpyInvocationPipeline()
        service = _make_service(
            cache_hit=phase1_cached.model_dump_json(),
            invocation_pipeline=spy,
        )

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run_phase2 = AsyncMock(
            return_value=BetaReaderPhase2Output(
                detailed_feedback=[],
                revision_suggestions=[],
                category_score=5,
            )
        )

        with patch(
            "narrare.analysis.beta_reader_service.BetaReaderAgent",
            return_value=mock_agent_instance,
        ):
            await service.deep_dive(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=BetaReaderDeepDiveRequest(
                    chapter_ids=[str(uuid4())],
                    category=FeedbackCategory.PLOT,
                    cache_key="abc123",
                ),
            )

        assert len(spy.prepare_calls) == 1
        assert spy.prepare_calls[0].feature_id == "analysis_beta_read_deepdive"
        assert len(spy.finalize_calls) == 1
