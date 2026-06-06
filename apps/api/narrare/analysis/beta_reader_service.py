"""Beta reader analysis service — business logic orchestration.

Orchestrates: validation → cache → context assembly → agent → cache → response.
No DB queries — delegated to repositories via context_assembler.
Response mapping delegated to beta_reader_mapper.py (RULE-04).

Follows the same pattern as worldbuilding_service.py and improve_service.py.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.beta_reader_agent_run import run_phase1, run_phase2
from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare.analysis.beta_reader_mapper import (
    map_phase1_response,
    map_phase2_response,
)
from narrare.analysis.beta_reader_prompt import build_budgeted_prompt
from narrare.analysis.errors import AnalysisError, CacheRetrievalError
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderDeepDiveResponse,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare.analysis.validation import validate_word_count
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare_core.agents.beta_reader_types import BetaReaderDeps
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


class BetaReaderService:
    """Implements BetaReaderProtocol.

    Orchestrates the two-phase beta reader analysis pipeline:
      Phase 1 (analyze): validate → cache → assemble → agent → cache → response
      Phase 2 (deep_dive): cache Phase 1 → assemble → agent Phase 2 → response

    Args:
        context_assembler: Builds BetaReaderDeps from chapter + KB data.
        cache: Redis-backed result cache (30min TTL).
        registry: ModelRegistry for LLM model resolution.
        config: Default ResolvedModelConfig for BETA_READ intent.
        composer: PromptComposer for system prompt assembly.
        invocation_pipeline: Optional pipeline for invocation evidence.
            When provided, evidence is recorded for every LLM call.
    """

    def __init__(
        self,
        context_assembler: ContextAssembler,
        cache: BetaReaderCache,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
        budget_assembler: AnalysisContextAssembler | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._assembler = context_assembler
        self._cache = cache
        self._registry = registry
        self._config = config
        self._composer = composer
        self._budget_assembler = budget_assembler or AnalysisContextAssembler()
        self._invocation_pipeline = invocation_pipeline

    async def analyze(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderRequest,
    ) -> BetaReaderResponse:
        """Phase 1: Full chapter analysis.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting analysis.
            request: Analysis parameters (chapter IDs, categories, options).

        Returns:
            Complete beta reader feedback with overall assessment.

        Raises:
            InsufficientWordCountError: If total word count < 1000.
            ExcessiveWordCountError: If total word count > 10000.
            AnalysisError: If context assembly or agent execution fails.
        """
        logger.info(
            "beta_reader_analyze_start",
            novel_id=str(novel_id),
            chapter_ids=request.chapter_ids,
            refresh=request.refresh,
        )

        # 1. Assemble context (validates chapters exist)
        deps = await self._assemble_context(novel_id, user_id, request.chapter_ids)

        # 2. Compute content hash for cache-key discrimination (ADR-021)
        content_hash = hashlib.sha256(deps.chapter_text.encode()).hexdigest()[:12]

        # 3. Check cache with content hash (after assembly so we know content)
        if not request.refresh:
            cached = await self._cache.get(
                str(novel_id), request.chapter_ids, content_hash=content_hash
            )
            if cached is not None:
                logger.info("beta_reader_cache_hit", novel_id=str(novel_id))
                return BetaReaderResponse.model_validate_json(cached)

        # 4. Validate word count
        validate_word_count(deps.word_count)

        # 5. Override focus categories from request
        if request.categories:
            deps.focus_categories = [c.value for c in request.categories]

        # 6. Compose prompt and run agent
        composed = await self._compose_prompt(deps.language, "beta_reader")
        model = await self._registry.get_model(self._config)

        # 6a. Record invocation evidence (ADR-040)
        from narrare._app.invocation_context import safe_record_evidence

        await safe_record_evidence(
            self._invocation_pipeline,
            feature_id="analysis_beta_read",
            intent=LLMIntent.BETA_READ,
            user_id=user_id,
            project_id=novel_id,
            language=deps.language,
        )

        agent = BetaReaderAgent(model=model, system_prompt=composed.system)
        user_prompt = await build_budgeted_prompt(deps, self._budget_assembler)
        result = await run_phase1(agent, user_prompt, deps)

        # 7. Map to response and cache
        response = map_phase1_response(result, novel_id, request.chapter_ids, deps.word_count)
        response.cache_key = BetaReaderCache.hash_chapter_ids(request.chapter_ids, content_hash)
        await self._cache.set(
            str(novel_id),
            request.chapter_ids,
            response.model_dump_json(),
            content_hash=content_hash,
        )

        logger.info(
            "beta_reader_analyze_complete",
            novel_id=str(novel_id),
            feedback_count=len(response.feedback),
            word_count=deps.word_count,
        )

        return response

    async def deep_dive(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderDeepDiveRequest,
    ) -> BetaReaderDeepDiveResponse:
        """Phase 2: Category deep-dive.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting the deep-dive.
            request: Deep-dive parameters (chapter IDs, category, cache key).

        Returns:
            Detailed category-specific feedback with revision suggestions.

        Raises:
            CacheRetrievalError: If Phase 1 cache is missing.
            AnalysisError: If context assembly or agent execution fails.
        """
        logger.info(
            "beta_reader_deep_dive_start",
            novel_id=str(novel_id),
            category=request.category.value,
        )

        # 1. Assemble context first (needed to compute content_hash for Phase 1 lookup)
        deps = await self._assemble_context(novel_id, user_id, request.chapter_ids)
        content_hash = hashlib.sha256(deps.chapter_text.encode()).hexdigest()[:12]

        # 2. Retrieve Phase 1 from cache for context (using content-aware key)
        phase1_json = await self._cache.get(
            str(novel_id), request.chapter_ids, content_hash=content_hash
        )
        if phase1_json is None:
            raise CacheRetrievalError("Phase 1 analysis not found. Run full analysis first.")

        phase1 = BetaReaderResponse.model_validate_json(phase1_json)
        deps.deepdive_category = request.category.value
        deps.phase1_strengths_summary = "; ".join(s.title for s in phase1.strengths)
        deps.phase1_feedback_summary = "; ".join(f.title for f in phase1.feedback[:10])

        # 3. Compose Phase 2 prompt and run agent
        composed = await self._compose_prompt(deps.language, "beta_reader_deepdive")
        model = await self._registry.get_model(self._config)

        # 3a. Record invocation evidence for deep-dive (ADR-040)
        from narrare._app.invocation_context import safe_record_evidence

        await safe_record_evidence(
            self._invocation_pipeline,
            feature_id="analysis_beta_read_deepdive",
            intent=LLMIntent.BETA_READ,
            user_id=user_id,
            project_id=novel_id,
            language=deps.language,
        )

        agent = BetaReaderAgent(model=model, system_prompt=composed.system)
        result = await run_phase2(agent, deps, model)

        # 4. Map to response
        response = map_phase2_response(result, novel_id, request.category)

        logger.info(
            "beta_reader_deep_dive_complete",
            novel_id=str(novel_id),
            category=request.category.value,
            feedback_count=len(response.detailed_feedback),
        )

        return response

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _assemble_context(
        self, novel_id: UUID, user_id: UUID, chapter_ids: list[str]
    ) -> BetaReaderDeps:
        """Assemble BetaReaderDeps from database.

        Raises:
            AnalysisError: If context assembly fails.
        """
        try:
            return await self._assembler.build_context(
                novel_id=novel_id,
                chapter_ids=[UUID(cid) for cid in chapter_ids],
                user_id=user_id,
            )
        except Exception as exc:
            logger.error(
                "context_assembly_failed",
                novel_id=str(novel_id),
                error=str(exc),
            )
            raise AnalysisError("Failed to assemble analysis context") from exc

    async def _compose_prompt(self, language: str, mode: str) -> ComposedPrompt:
        """Compose system prompt via PromptComposer.

        Raises:
            AnalysisError: If prompt composition fails.
        """
        ctx = PromptContext(language=language, mode=mode, project_title="")
        try:
            return await self._composer.build(LLMIntent.BETA_READ, ctx)
        except Exception as exc:
            logger.error("prompt_composition_failed", mode=mode, error=str(exc))
            raise AnalysisError("Failed to compose analysis prompt") from exc
