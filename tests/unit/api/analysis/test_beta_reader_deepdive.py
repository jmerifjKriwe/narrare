"""Unit tests for BetaReaderService — Phase 2 (deepdive) and validation.

Tests Phase 2 cache miss error and word count validation.
Split from test_beta_reader_service.py to stay under 300 lines (RULE-04).
"""

from __future__ import annotations

from typing import Protocol
from unittest.mock import AsyncMock, MagicMock
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
from narrare.analysis.schemas import BetaReaderDeepDiveRequest, BetaReaderRequest
from narrare_core.agents.beta_reader_types import BetaReaderDeps

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
