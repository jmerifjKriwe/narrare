"""Unit tests for ChapterSentimentService — edge cases (exception + lazy init).

Extracted to fill coverage gaps in sentiment_service.py:
- Lines 151-160: analyzer exception propagation
- Lines 228-232: _get_analyzer lazy initialization

Uses Fake classes (no MagicMock).
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare.analysis.services.sentiment_service import ChapterSentimentService
from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from narrare_core.analysis.types import EmotionScores, SentimentOverview, VADScores
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos

# ---------------------------------------------------------------------------
# Fake analyzer
# ---------------------------------------------------------------------------


class FakeSentimentAnalyzer:
    """Fake LexiconSentimentAnalyzer — returns predetermined output or raises."""

    def __init__(
        self,
        result: SentimentOverview | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result or SentimentOverview(
            sentence_count=2,
            average_vad=VADScores(valence=0.5, arousal=0.3, dominance=0.4),
            overall_emotions=EmotionScores(),
            dominant_emotions=["joy"],
        )
        self._error = error

    async def analyze(self, **kwargs: object) -> SentimentOverview:
        if self._error:
            raise self._error
        return self._result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service() -> tuple[Any, Any, ChapterSentimentService]:
    novel = make_novel()
    ch = make_chapter(novel_id=novel.id, content="She felt joy. The sun shone.")
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
    nlp: Any = type("FakeNLP", (), {})()  # simple fake — never called
    svc = ChapterSentimentService(
        chapter_repo=cr,
        novel_repo=nr,
        nlp_provider=nlp,
    )
    return novel, ch, svc


# ---------------------------------------------------------------------------
# A. Analyzer exception propagation (lines 151-160)
# ---------------------------------------------------------------------------


class TestAnalyzerExceptionPropagation:
    @pytest.mark.asyncio
    async def test_analyzer_error_re_raises(self) -> None:
        """When analyzer raises, the exception propagates (RULE-11)."""
        novel, ch, svc = _service()
        fake = FakeSentimentAnalyzer(error=RuntimeError("NLP crashed"))
        svc._get_analyzer = lambda: fake  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="NLP crashed"):
            await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )


# ---------------------------------------------------------------------------
# B. _get_analyzer lazy initialization (lines 228-232)
# ---------------------------------------------------------------------------


class TestGetAnalyzerLazyInit:
    def test_creates_analyzer_on_first_call(self) -> None:
        """_get_analyzer creates LexiconSentimentAnalyzer lazily."""
        _, _, svc = _service()
        assert svc._analyzer is None
        analyzer = svc._get_analyzer()
        assert isinstance(analyzer, LexiconSentimentAnalyzer)

    def test_returns_same_instance_on_second_call(self) -> None:
        """_get_analyzer caches the analyzer (singleton per service)."""
        _, _, svc = _service()
        first = svc._get_analyzer()
        second = svc._get_analyzer()
        assert first is second

    def test_analyzer_not_created_at_init(self) -> None:
        """Analyzer is None until _get_analyzer is called."""
        _, _, svc = _service()
        assert svc._analyzer is None
