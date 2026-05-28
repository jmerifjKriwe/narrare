"""Unit tests for ChapterSentimentService — data-quality warnings (ANAL-002).

Extracted from test_sentiment_service.py to keep file sizes within limits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis.test_sentiment_service import _overview, _service, _setup


def _long_content() -> str:
    """Generate chapter content with 500+ words."""
    return " ".join(["word"] * 501)


class TestWordCountWarning:
    @pytest.mark.asyncio
    async def test_short_chapter_adds_word_count_warning(self) -> None:
        """Chapters below 500 words get a word-count warning."""
        novel, (ch, *_), _, svc = _setup()
        # Default content is ~12 words, well below 500
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )
        assert any("500 words" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_short_chapter_warning_includes_word_count(self) -> None:
        """Warning message contains the actual word count."""
        novel, (ch, *_), _, svc = _setup(
            chapters=[make_chapter(novel_id=None, content="One two three.")]
        )
        novel, chapters, _, svc = _setup(
            novel=novel,
            chapters=[make_chapter(novel_id=novel.id, content="One two three.")],
        )
        ch = chapters[0]
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )
        assert any("3 words" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_long_chapter_no_word_count_warning(self) -> None:
        """Chapters with 500+ words produce no word-count warning."""
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content=_long_content())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr, cr)
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )
        assert not any("500 words" in w for w in result.warnings)


class TestArcDetectionWarning:
    @pytest.mark.asyncio
    async def test_detect_arc_true_adds_warning(self) -> None:
        """detect_arc=True on a single chapter adds arc-detection warning."""
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content=_long_content())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr, cr)
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=True,
            )
        assert any("3+ chapters" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_detect_arc_true_passes_false_to_analyzer(self) -> None:
        """detect_arc=True is overridden to False for single-chapter analysis."""
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content=_long_content())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr, cr)
        analyzer = AsyncMock(analyze=AsyncMock(return_value=_overview()))
        with patch.object(svc, "_get_analyzer", return_value=analyzer):
            await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=True,
            )
        assert analyzer.analyze.call_args.kwargs["detect_arc"] is False

    @pytest.mark.asyncio
    async def test_detect_arc_false_no_arc_warning(self) -> None:
        """detect_arc=False produces no arc-detection warning."""
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content=_long_content())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr, cr)
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )
        assert not any("3+ chapters" in w for w in result.warnings)


class TestCombinedWarnings:
    @pytest.mark.asyncio
    async def test_short_chapter_with_arc_both_warnings(self) -> None:
        """Short chapter + detect_arc=True produces both warnings."""
        novel, (ch, *_), _, svc = _setup()
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=True,
            )
        assert len(result.warnings) == 2
        assert any("500 words" in w for w in result.warnings)
        assert any("3+ chapters" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_long_chapter_no_arc_no_warnings(self) -> None:
        """Long chapter + detect_arc=False produces no warnings."""
        novel = make_novel()
        ch = make_chapter(novel_id=novel.id, content=_long_content())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr, cr)
        with patch.object(
            svc,
            "_get_analyzer",
            return_value=AsyncMock(analyze=AsyncMock(return_value=_overview())),
        ):
            result = await svc.analyze_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                detect_arc=False,
            )
        assert result.warnings == []
