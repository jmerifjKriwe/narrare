"""Sentiment analysis service — orchestrates deterministic sentiment computation.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control. Delegates computation to core's ``LexiconSentimentAnalyzer``.

No DB queries — delegated to repositories (RULE-06).
No LLM calls — purely deterministic (ADR-021).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
    from narrare_core.analysis.types import SentimentOverview
    from narrare_core.nlp.contracts import NLPProvider

logger = structlog.get_logger(__name__)


class ChapterSentimentService:
    """Implements the ``SentimentService`` Protocol (see ``analysis/contracts.py``).

    Orchestrates: validate access → fetch chapter → resolve language →
    run deterministic analysis → return ``SentimentOverview``.

    All results are **deterministic** — same text always produces
    identical scores (ADR-021). No LLM calls involved.

    Args:
        chapter_repo: For fetching chapter content.
        novel_repo: For resolving novel language and access control.
        nlp_provider: Core NLP provider (spaCy-based, lazy-loaded).
            Used to construct the ``LexiconSentimentAnalyzer``.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        nlp_provider: NLPProvider,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._nlp_provider = nlp_provider
        self._analyzer: LexiconSentimentAnalyzer | None = None

    # -------------------------------------------------------------------
    # Public API — matches SentimentService Protocol
    # -------------------------------------------------------------------

    async def analyze_chapter(
        self,
        *,
        novel_id: UUID,
        chapter_id: UUID,
        user_id: UUID,
        language: str | None = None,
        detect_arc: bool = True,
    ) -> SentimentOverview:
        """Analyze sentiment for a single chapter.

        Steps:
        1. Fetch novel for access control and language resolution.
        2. Fetch chapter content.
        3. Resolve effective language (override → novel default → ``"en"``).
        4. Collect data-quality warnings (word count < 500, arc detection
           on single chapter).
        5. Run deterministic sentiment analysis via core.
        6. Return ``SentimentOverview`` with any warnings attached.

        Args:
            novel_id: The project containing the chapter.
            chapter_id: The chapter to analyze.
            user_id: The user requesting analysis (for access control).
            language: Optional language override. If ``None``, uses
                the novel's ``writing_language`` (fallback ``"en"``).
            detect_arc: Whether to detect narrative arc. Default ``True``.
                Automatically disabled for single-chapter analysis with
                a warning (ANAL-002: requires 3+ chapters).

        Returns:
            A ``SentimentOverview`` with per-sentence breakdown,
            aggregate scores, and any data-quality ``warnings``.

        Raises:
            NotFoundError: If the novel or chapter does not exist or
                is not accessible.
            narrare_core.shared.errors.NLPProviderError: If the NLP
                provider is not available for the resolved language.
        """
        # 1. Novel access check + language resolution
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # 2. Fetch chapter
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        # 3. Resolve effective language
        effective_language = language or novel.writing_language or "en"

        # 4. Data-quality warnings
        warnings: list[str] = []

        word_count = len(chapter.content.split())
        if word_count < 500:
            msg = (
                f"Chapter has {word_count} words; analysis may be "
                "unreliable with fewer than 500 words."
            )
            warnings.append(msg)
            logger.warning(
                "chapter_word_count_low",
                chapter_id=str(chapter_id),
                word_count=word_count,
                minimum=500,
            )

        effective_detect_arc = detect_arc
        if detect_arc:
            msg = "Arc detection requires 3+ chapters; disabled for single-chapter analysis."
            warnings.append(msg)
            effective_detect_arc = False
            logger.warning(
                "arc_detection_disabled",
                chapter_id=str(chapter_id),
                reason="single_chapter",
            )

        # 5. Run deterministic analysis
        analyzer = self._get_analyzer()
        try:
            result = await analyzer.analyze(
                text=chapter.content,
                language=effective_language,
                detect_arc=effective_detect_arc,
            )
        except Exception as exc:
            logger.error(
                "sentiment_analysis_failed",
                novel_id=str(novel_id),
                chapter_id=str(chapter_id),
                language=effective_language,
                error=str(exc),
                exc_info=True,
            )
            raise

        # 6. Attach warnings to result
        if warnings:
            result.warnings = warnings

        logger.info(
            "sentiment_analyzed",
            novel_id=str(novel_id),
            chapter_id=str(chapter_id),
            language=effective_language,
            sentence_count=result.sentence_count,
            warning_count=len(warnings),
        )

        return result

    async def analyze_chapters(
        self,
        *,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
        language: str | None = None,
        detect_arc: bool = True,
    ) -> list[SentimentOverview]:
        """Analyze sentiment for multiple chapters.

        Processes each chapter independently and sequentially. Results
        are returned in the same order as ``chapter_ids``.

        Args:
            novel_id: The project containing the chapters.
            chapter_ids: The chapters to analyze (preserves order).
            user_id: The user requesting analysis.
            language: Optional language override for all chapters.
            detect_arc: Whether to detect narrative arc.

        Returns:
            List of ``SentimentOverview``, one per chapter.

        Raises:
            NotFoundError: If the novel or any chapter is not accessible.
            narrare_core.shared.errors.NLPProviderError: If the NLP
                provider is not available for the resolved language.
        """
        results: list[SentimentOverview] = []
        for cid in chapter_ids:
            result = await self.analyze_chapter(
                novel_id=novel_id,
                chapter_id=cid,
                user_id=user_id,
                language=language,
                detect_arc=detect_arc,
            )
            results.append(result)
        return results

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _get_analyzer(self) -> LexiconSentimentAnalyzer:
        """Lazy-init the ``LexiconSentimentAnalyzer``.

        The analyzer itself is cheap to create (no I/O). The underlying
        ``SpacyNLPProvider`` does lazy-load on first ``nlp()`` call.
        """
        if self._analyzer is None:
            from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer

            self._analyzer = LexiconSentimentAnalyzer(nlp_provider=self._nlp_provider)
        return self._analyzer
