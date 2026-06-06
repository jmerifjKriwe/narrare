"""Readability analysis service — orchestrates deterministic metrics + AI sentence analysis.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control. Delegates computation to core's ``FormulaReadabilityAnalyzer``
and ``ReadabilityAgent``.

No DB queries — delegated to repositories (RULE-06).
LLM calls go through ``ReadabilityAgent`` via ``ModelRegistry`` (RULE-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog

from narrare_core.analysis.readability import FormulaReadabilityAnalyzer
from narrare_core.analysis.types import ReadabilityResult
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm.model_config import ResolvedModelConfig

logger = structlog.get_logger(__name__)


class ReadabilityService:
    """Implements ``ReadabilityServiceProtocol`` (see ``analysis/contracts.py``).

    Orchestrates: validate access → fetch chapters → resolve language →
    run deterministic metrics → run AI sentence analysis → combine →
    return ``ReadabilityResult``.

    Args:
        chapter_repo: For fetching chapter content.
        novel_repo: For resolving novel language and access control.
        model_registry: LLM model registry for constructing the
            ``ReadabilityAgent``.
        model_config: Resolved model configuration (provider, model_id,
            temperature, max_tokens).
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._model_registry = model_registry
        self._model_config = model_config
        self._formula_analyzer = FormulaReadabilityAnalyzer()
        self._invocation_pipeline = invocation_pipeline

    # -------------------------------------------------------------------
    # Public API — matches ReadabilityServiceProtocol
    # -------------------------------------------------------------------

    async def analyze(
        self,
        *,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
        language: str = "en",
    ) -> list[ReadabilityResult]:
        """Analyze readability for one or more chapters.

        Steps:
        1. Validate novel access (user owns it).
        2. Resolve effective language (override → novel default → ``"en"``).
        3. For each chapter:
           a. Fetch chapter content (404 if missing).
           b. Run ``FormulaReadabilityAnalyzer`` — deterministic metrics.
           c. Run ``ReadabilityAgent`` — AI sentence analysis.
           d. Merge AI results into the deterministic ``ReadabilityResult``.
        4. Return list of ``ReadabilityResult`` (same order as ``chapter_ids``).

        Args:
            novel_id: The project containing the chapters.
            chapter_ids: Chapters to analyse (1-5).
            user_id: The user requesting analysis (for access control).
            language: Language override. Defaults to ``"en"``.

        Returns:
            One ``ReadabilityResult`` per chapter, in the same order.

        Raises:
            NotFoundError: If the novel or any chapter does not exist
                or is not accessible.
        """
        # 1. Novel access check + language resolution
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        effective_language = language if language != "auto" else (novel.writing_language or "en")

        # 2. Process each chapter
        results: list[ReadabilityResult] = []
        for chapter_id in chapter_ids:
            result = await self._analyze_chapter(
                novel_id=novel_id,
                chapter_id=chapter_id,
                language=effective_language,
            )
            results.append(result)

        logger.info(
            "readability_analysis_complete",
            novel_id=str(novel_id),
            chapter_count=len(chapter_ids),
            language=effective_language,
        )

        return results

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _analyze_chapter(
        self,
        *,
        novel_id: UUID,
        chapter_id: UUID,
        language: str,
    ) -> ReadabilityResult:
        """Run both deterministic + AI analysis for a single chapter.

        Args:
            novel_id: The novel (for logging / context).
            chapter_id: The chapter to analyze.
            language: Resolved language code.

        Returns:
            Combined ``ReadabilityResult``.

        Raises:
            NotFoundError: If the chapter does not exist.
        """
        # 1. Fetch chapter
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        content = chapter.content or ""

        # 2. Phase 1: Deterministic metrics (instant)
        result = await self._formula_analyzer.analyze(content, language=language)

        # 3. Phase 2: AI sentence analysis (skip for empty content)
        if content.strip():
            try:
                # 3a. Record invocation evidence (ADR-040)
                from narrare._app.invocation_context import safe_record_evidence
                from narrare_core.llm.intents import LLMIntent

                await safe_record_evidence(
                    self._invocation_pipeline,
                    feature_id="analysis_readability",
                    intent=LLMIntent.ANALYSE,
                    language=language,
                )

                agent = self._get_agent()
                agent_result = await agent.run(
                    prompt="Analyze readability of this text.",
                    deps=_build_deps(content, language),
                )

                # Merge AI results into the formula result
                result = self._merge_agent_result(result, agent_result)
            except Exception as exc:
                logger.error(
                    "readability_agent_failed",
                    chapter_id=str(chapter_id),
                    language=language,
                    error=str(exc),
                    exc_info=True,
                )
                # Graceful degradation — return deterministic metrics only
        else:
            logger.info(
                "readability_skipped_empty_chapter",
                chapter_id=str(chapter_id),
            )

        logger.info(
            "readability_chapter_analyzed",
            chapter_id=str(chapter_id),
            flesch_reading_ease=result.metrics.flesch_reading_ease,
            sentence_count=result.metrics.sentence_count,
            sentence_analyses_count=len(result.sentence_analyses),
        )

        return result

    def _get_agent(self) -> ReadabilityAgent:
        """Construct a ``ReadabilityAgent`` from the model registry.

        Returns a fresh agent per call — agents are lightweight wrappers
        around the model.
        """
        from narrare_core.agents.readability_agent import ReadabilityAgent

        model = self._model_registry.get_model(self._model_config)
        return ReadabilityAgent(model=model)

    @staticmethod
    def _merge_agent_result(
        formula_result: ReadabilityResult,
        agent_output: object,
    ) -> ReadabilityResult:
        """Merge AI sentence analyses into the deterministic result.

        Maps ``ReadabilityAgentOutput.problematic_sentences`` to
        ``list[SentenceAnalysis]`` and carries over the
        ``overall_assessment``.

        Args:
            formula_result: Deterministic result from ``FormulaReadabilityAnalyzer``.
            agent_output: ``ReadabilityAgentOutput`` from the AI agent.

        Returns:
            Merged ``ReadabilityResult`` with both metrics and AI analysis.
        """
        from narrare_core.agents.readability_types import ReadabilityAgentOutput
        from narrare_core.analysis.types import SentenceAnalysis

        output = ReadabilityAgentOutput.model_validate(agent_output)

        sentence_analyses: list[SentenceAnalysis] = []
        for ps in output.problematic_sentences:
            raw_issues: Any = ps.get("issues", [])
            if isinstance(raw_issues, list):
                issue_list = cast("list[Any]", raw_issues)
                issue_strs: list[str] = [str(i) for i in issue_list]
            else:
                issue_strs = [str(raw_issues)]

            raw_suggestions: Any = ps.get("suggestions", [])
            suggestion_strs: list[str] = []
            if isinstance(raw_suggestions, list):
                sugg_list = cast("list[Any]", raw_suggestions)
                for s in sugg_list:
                    if isinstance(s, dict):
                        s_dict = cast("dict[str, Any]", s)
                        alt: str = str(s_dict.get("alternative", s))
                        suggestion_strs.append(alt)
                    else:
                        suggestion_strs.append(str(s))
            else:
                suggestion_strs = [str(raw_suggestions)]

            sentence_analyses.append(
                SentenceAnalysis(
                    sentence=str(ps.get("sentence", "")),
                    sentence_index=int(ps.get("sentence_index", 0)),
                    issues=issue_strs,
                    readability_score=float(ps.get("readability_score", 0.5)),
                    suggestions=suggestion_strs,
                )
            )

        return ReadabilityResult(
            metrics=formula_result.metrics,
            genre_benchmarks=formula_result.genre_benchmarks,
            sentence_analyses=sentence_analyses,
            overall_assessment=output.overall_assessment or None,
        )


def _build_deps(text: str, language: str) -> ReadabilityDeps:
    """Build ``ReadabilityDeps`` — helper to keep import out of module top-level.

    Args:
        text: Chapter content.
        language: Resolved language code.

    Returns:
        A ``ReadabilityDeps`` instance.
    """
    from narrare_core.agents.readability_agent import ReadabilityDeps

    return ReadabilityDeps(text=text, language=language)
