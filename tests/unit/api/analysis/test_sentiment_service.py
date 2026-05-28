"""Unit tests for ChapterSentimentService — access control, language, analysis.

No real DB, no real NLP — all dependencies are faked/mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare.analysis.services.sentiment_service import ChapterSentimentService
from narrare_core.analysis.types import (
    EmotionScores,
    SentenceSentiment,
    SentimentOverview,
    VADScores,
)
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos


def _overview(
    *,
    sentence_count: int = 2,
    average_vad: VADScores | None = None,
    overall_emotions: EmotionScores | None = None,
    sentences: list[SentenceSentiment] | None = None,
    dominant_emotions: list[str] | None = None,
) -> SentimentOverview:
    return SentimentOverview(
        sentence_count=sentence_count,
        average_vad=average_vad or VADScores(valence=0.65, arousal=0.4, dominance=0.3),
        overall_emotions=overall_emotions or EmotionScores(joy=0.3, trust=0.2),
        sentences=sentences if sentences is not None else [],
        dominant_emotions=dominant_emotions or ["joy"],
    )


def _service(nr=None, cr=None) -> ChapterSentimentService:
    return ChapterSentimentService(
        chapter_repo=cr or FakeChapterRepository(),
        novel_repo=nr or FakeNovelRepository(),
        nlp_provider=AsyncMock(),
    )


def _setup(novel=None, chapters=None):
    """Seed repos and return (novel, chapter_repo, service)."""
    novel = novel or make_novel()
    chapters = chapters or [make_chapter(novel_id=novel.id)]
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, *chapters, novel_repo=nr, chapter_repo=cr)
    return novel, chapters, cr, _service(nr, cr)


# --- A. analyze_chapter — happy path ---


class TestAnalyzeChapter:
    @pytest.mark.asyncio
    async def test_analyze_chapter_returns_overview(self) -> None:
        novel, (ch, *_), _, svc = _setup()
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id, chapter_id=ch.id, user_id=novel.user_id
            )
        assert isinstance(result, SentimentOverview)
        assert result.sentence_count == 2
        assert result.dominant_emotions == ["joy"]

    @pytest.mark.asyncio
    async def test_analyze_chapter_resolves_language_from_novel(self) -> None:
        novel, (ch, *_), _, svc = _setup(novel=make_novel(writing_language="de"))
        analyzer = AsyncMock(analyze=AsyncMock(return_value=_overview()))
        with patch.object(svc, "_get_analyzer", return_value=analyzer):
            await svc.analyze_chapter(novel_id=novel.id, chapter_id=ch.id, user_id=novel.user_id)
        assert analyzer.analyze.call_args.kwargs["language"] == "de"

    @pytest.mark.asyncio
    async def test_analyze_chapter_uses_language_override(self) -> None:
        novel, (ch, *_), _, svc = _setup(novel=make_novel(writing_language="de"))
        analyzer = AsyncMock(analyze=AsyncMock(return_value=_overview()))
        with patch.object(svc, "_get_analyzer", return_value=analyzer):
            await svc.analyze_chapter(
                novel_id=novel.id, chapter_id=ch.id, user_id=novel.user_id, language="fr"
            )
        assert analyzer.analyze.call_args.kwargs["language"] == "fr"

    @pytest.mark.asyncio
    async def test_analyze_chapter_detects_arc(self) -> None:
        novel, (ch, *_), _, svc = _setup()
        analyzer = AsyncMock(analyze=AsyncMock(return_value=_overview()))
        with patch.object(svc, "_get_analyzer", return_value=analyzer):
            await svc.analyze_chapter(
                novel_id=novel.id, chapter_id=ch.id, user_id=novel.user_id, detect_arc=False
            )
        assert analyzer.analyze.call_args.kwargs["detect_arc"] is False


# --- B. analyze_chapter — error cases ---


class TestAnalyzeChapterErrors:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self) -> None:
        with pytest.raises(NotFoundError, match="Novel"):
            await _service().analyze_chapter(novel_id=uuid4(), chapter_id=uuid4(), user_id=uuid4())

    @pytest.mark.asyncio
    async def test_chapter_not_found_raises(self) -> None:
        novel, _, _, svc = _setup()
        with pytest.raises(NotFoundError, match="Chapter"):
            await svc.analyze_chapter(novel_id=novel.id, chapter_id=uuid4(), user_id=novel.user_id)


# --- C. analyze_chapters — multiple ---


class TestAnalyzeChapters:
    @pytest.mark.asyncio
    async def test_analyze_multiple_chapters_returns_list(self) -> None:
        novel, (ch1, ch2), _, svc = _setup(
            chapters=[
                make_chapter(novel_id=None),
                make_chapter(novel_id=None),
            ]
        )
        novel, chapters, _, svc = _setup(
            novel=novel,
            chapters=[
                make_chapter(novel_id=novel.id),
                make_chapter(novel_id=novel.id),
            ],
        )
        ch1, ch2 = chapters
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            results = await svc.analyze_chapters(
                novel_id=novel.id, chapter_ids=[ch1.id, ch2.id], user_id=novel.user_id
            )
        assert len(results) == 2
        assert all(isinstance(r, SentimentOverview) for r in results)

    @pytest.mark.asyncio
    async def test_results_match_chapter_order(self) -> None:
        novel, chapters, _, svc = _setup(
            chapters=[
                make_chapter(novel_id=None, content="First."),
                make_chapter(novel_id=None, content="Second."),
            ]
        )
        novel, chapters, _, svc = _setup(
            novel=novel,
            chapters=[
                make_chapter(novel_id=novel.id, content="First."),
                make_chapter(novel_id=novel.id, content="Second."),
            ],
        )
        ch_a, ch_b = chapters
        n = 0

        async def _side(**kw):
            nonlocal n
            n += 1
            return _overview(sentence_count=1) if n == 1 else _overview(sentence_count=5)

        with patch.object(
            svc, "_get_analyzer", return_value=AsyncMock(analyze=AsyncMock(side_effect=_side))
        ):
            results = await svc.analyze_chapters(
                novel_id=novel.id, chapter_ids=[ch_a.id, ch_b.id], user_id=novel.user_id
            )
        assert results[0].sentence_count == 1
        assert results[1].sentence_count == 5
