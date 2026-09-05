"""Readability analysis service — orchestrates deterministic metrics + AI sentence analysis.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control. Delegates computation to core's ``FormulaReadabilityAnalyzer``
and ``ReadabilityAgent``.

No DB queries — delegated to repositories (RULE-06).
LLM calls go through ``ReadabilityAgent`` via ``ModelRegistry`` (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.analysis._invocation_compose import compose_analysis_invocation_prompt
from narrare.analysis.services._readability_helpers import build_deps
from narrare_core.analysis.readability import FormulaReadabilityAnalyzer
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.agents.readability_agent import ReadabilityAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.types import ReadabilityResult
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

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
        composer: PromptComposer for Mode 1 (composer-driven) system prompt
            assembly (ADR-048). Builds the feature-specific readability
            system prompt from the bundled ``analysis/{lang}/readability``
            template.
        invocation_pipeline: Optional pipeline for invocation evidence.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.prepare``.
        base_url: Optional per-user provider base URL override.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._model_registry = model_registry
        self._model_config = model_config
        self._composer = composer
        self._formula_analyzer = FormulaReadabilityAnalyzer()
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

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
                user_id=user_id,
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
        user_id: UUID,
        language: str,
    ) -> ReadabilityResult:
        """Run both deterministic + AI analysis for a single chapter.

        Args:
            novel_id: The novel (for invocation enrichment context).
            chapter_id: The chapter to analyze.
            user_id: The user requesting analysis (for enrichment).
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
                # 3a. Compose prompt via Mode 1 (composer-driven, ADR-048)
                # with correlated evidence + enrichment. Falls back to direct
                # composition on pipeline failure.
                composed = await compose_analysis_invocation_prompt(
                    composer=self._composer,
                    invocation_pipeline=self._invocation_pipeline,
                    feature_id="analysis_readability",
                    intent=LLMIntent.ANALYSE,
                    novel_id=novel_id,
                    user_id=user_id,
                    language=language,
                    mode="readability",
                )

                agent, prepared = await self._prepare_agent(system_prompt=composed.system)
                agent_result = await agent.run(
                    prompt="Analyze readability of this text.",
                    deps=build_deps(content, language),
                    model_settings=prepared.model_settings,
                    usage_limits=prepared.usage_limits,
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

    async def _prepare_agent(
        self,
        system_prompt: str | None = None,
    ) -> tuple[ReadabilityAgent, PreparedModelCall]:
        """Prepare the model call and construct a ``ReadabilityAgent``.

        Args:
            system_prompt: Composed feature-specific system prompt (Mode 1,
                ADR-048). When ``None`` the agent falls back to Capabilities only.

        Returns:
            A fresh agent per call — agents are lightweight wrappers
            around the model — plus the coherent ``PreparedModelCall``
            triple (Task 6a-2 single assembly point): the agent's
            ``run`` must receive ``prepared.model_settings`` and
            ``prepared.usage_limits``.
        """
        from narrare_core.agents.readability_agent import ReadabilityAgent

        resolved = self._run_limit_resolver.resolve(
            config=self._model_config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._model_registry.prepare(
            self._model_config,
            intent=LLMIntent.ANALYSE,
            usage_limits=resolved.usage_limits,
            api_key=self._api_key,
            base_url=self._base_url,
        )
        return ReadabilityAgent(model=prepared.model, system_prompt=system_prompt), prepared

    @staticmethod
    def _merge_agent_result(
        formula_result: ReadabilityResult,
        agent_output: object,
    ) -> ReadabilityResult:
        """Merge AI sentence analyses into the deterministic result.

        Delegates to :func:`narrare.analysis.services._readability_helpers.merge_agent_result`
        (RULE-04 extraction).

        Args:
            formula_result: Deterministic result from ``FormulaReadabilityAnalyzer``.
            agent_output: ``ReadabilityAgentOutput`` from the AI agent.

        Returns:
            Merged ``ReadabilityResult`` with both metrics and AI analysis.
        """
        from narrare.analysis.services._readability_helpers import merge_agent_result

        return merge_agent_result(formula_result, agent_output)
