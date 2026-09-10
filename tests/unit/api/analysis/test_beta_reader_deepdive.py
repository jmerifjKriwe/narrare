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

from narrare._app.dependencies_services import StaticModelResolution
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
from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.llm import ResolvedModel
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

# Minimal protocols for spec'd mocks (RULE-TEST-01)


class _ModelRegistryProto(Protocol):
    async def get_model(
        self,
        config: object,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object: ...

    async def prepare(
        self,
        config: object,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object: ...


class _ComposedPromptProto(Protocol):
    system: str


class _ComposedInvocationProto(Protocol):
    composed_prompt: _ComposedPromptProto


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

    # Registry mock — spec'd (RULE-TEST-01); prepare bridges to the same
    # recording get_model so credential/call assertions hold (Task-6a
    # bridge pattern).
    registry = MagicMock(spec=_ModelRegistryProto)
    registry.get_model = AsyncMock(return_value=object())
    registry.prepare = AsyncMock(
        return_value=PreparedModelCall(
            model=registry.get_model.return_value,
            model_settings={"max_tokens": 12_345},
            usage_limits=None,
        )
    )

    # Composer mock — composed is spec'd (RULE-TEST-01)
    composed = MagicMock(spec=_ComposedPromptProto)
    composed.system = "System prompt"
    composer = AsyncMock()
    composer.build = AsyncMock(return_value=composed)

    # Config — real instance instead of bare MagicMock (RULE-TEST-01),
    # wrapped in StaticModelResolution (ADR-086: the service resolves at
    # first use via ModelResolution, never via a bare config).
    from narrare_core.llm import ResolvedModelConfig

    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test",
        temperature=0.7,
        max_tokens=4096,
    )

    async def _default_budget_assembler() -> AnalysisContextAssembler:
        """Default (uncapped) budget assembler — pre-ADR-086 unit default."""
        return AnalysisContextAssembler()

    return BetaReaderService(
        context_assembler=assembler,
        cache=cache,
        registry=registry,
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        composer=composer,
        budget_assembler_factory=_default_budget_assembler,
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
# Invocation composition — verifies compose_invocation (ADR-048 Mode 1)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify Phase 2 routes through compose_invocation in Mode 1 (composer-driven)."""

    @pytest.mark.asyncio
    async def test_phase2_compose_invocation_called(self) -> None:
        """Deep-dive invokes compose_invocation with composer= (Mode 1), not manual_injection=."""
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

        service = _make_service(cache_hit=phase1_cached.model_dump_json())

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run_phase2 = AsyncMock(
            return_value=BetaReaderPhase2Output(
                detailed_feedback=[],
                revision_suggestions=[],
                category_score=5,
            )
        )

        fake_invocation = MagicMock(spec=_ComposedInvocationProto)
        fake_invocation.composed_prompt = MagicMock(spec=_ComposedPromptProto)
        fake_invocation.composed_prompt.system = "System prompt"

        with (
            patch(
                "narrare.analysis.beta_reader_service.BetaReaderAgent",
                return_value=mock_agent_instance,
            ),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=fake_invocation),
            ) as mock_compose,
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

        mock_compose.assert_awaited_once()
        kwargs = mock_compose.call_args.kwargs
        # Mode 1: composer-driven (composer= + prompt_context= + intent=)
        assert kwargs.get("composer") is not None, (
            "compose_invocation must be called with composer= (Mode 1, "
            "composer-driven), not manual_injection= (Mode 2)."
        )
        assert kwargs.get("prompt_context") is not None, (
            "compose_invocation must be called with prompt_context= (Mode 1)."
        )
        assert kwargs.get("intent") == LLMIntent.BETA_READ, (
            f"Expected intent=LLMIntent.BETA_READ, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1."
        )
        invocation_ctx = kwargs.get("invocation_context")
        assert invocation_ctx is not None
        assert invocation_ctx.feature_id == "analysis_beta_read_deepdive"
