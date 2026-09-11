"""Beta reader analysis service — business logic orchestration.

Orchestrates: ownership gate → validation → cache → context assembly → agent →
cache → response. No DB queries — delegated to repositories via
context_assembler. Response mapping delegated to beta_reader_mapper.py
(RULE-04).

Ownership (IDOR remediation S12a): context assembly gates novel ownership in
Step 0 (see :mod:`narrare.analysis.context_assembler`). The resulting
``NotFoundError`` (foreign ≡ unknown → 404) is re-raised UNWRAPPED — it must
never be masked by the generic ``AnalysisError`` wrap (RULE-11).

Follows the same pattern as worldbuilding_service.py and improve_service.py.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.analysis._invocation_compose import compose_analysis_invocation_prompt
from narrare.analysis.beta_reader_agent_run import run_phase1, run_phase2
from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare.analysis.beta_reader_context import assemble_context, deep_dive_deps
from narrare.analysis.beta_reader_mapper import (
    map_phase1_response,
    map_phase2_response,
)
from narrare.analysis.beta_reader_prompt import build_budgeted_prompt
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderDeepDiveResponse,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare.analysis.validation import validate_word_count
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.llm import LLMIntent, ResolvedModel
from narrare_core.llm.run_limits import DefaultRunLimitResolver

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare._app.dependencies_services import ModelResolution
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.assembler import AnalysisContextAssembler
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class BetaReaderService:
    """Implements BetaReaderProtocol.

    Orchestrates the two-phase beta reader analysis pipeline:
      Phase 1 (analyze): validate → cache → assemble → agent → cache → response
      Phase 2 (deep_dive): cache Phase 1 → assemble → agent Phase 2 → response

    Args:
        context_assembler: Builds BetaReaderDeps from chapter + KB data.
        cache: In-memory result cache (30min TTL, ADR-080).
        registry: ModelRegistry for LLM model resolution.
        model_resolution: Lazy model-routing source (ADR-086): the
            per-user cascade (config + credentials) resolves at first
            use — after body validation — and is cached by the
            implementation; tests/overrides wire ``StaticModelResolution``.
        composer: PromptComposer for system prompt assembly.
        budget_assembler_factory: Deferred ADR-082/086 composition of the
            token-limits cascade + resolved model window into the
            assembler; composed once at first use.
        invocation_pipeline: Optional pipeline for invocation evidence.
            When provided, evidence is recorded for every LLM call.
    """

    def __init__(
        self,
        context_assembler: ContextAssembler,
        cache: BetaReaderCache,
        registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer,
        budget_assembler_factory: Callable[[], Awaitable[AnalysisContextAssembler]],
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._assembler = context_assembler
        self._cache = cache
        self._registry = registry
        self._model_resolution = model_resolution
        self._composer = composer
        self._budget_assembler_factory = budget_assembler_factory
        self._invocation_pipeline = invocation_pipeline
        self._budget_assembler: AnalysisContextAssembler | None = None
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def _prepare_model(self, resolved_model: ResolvedModel) -> PreparedModelCall:
        """Single assembly point (Task 6d): run limits + credentials → prepare()."""
        resolved = self._run_limit_resolver.resolve(
            config=resolved_model.config, budget=None, invocation_id=uuid4()
        )
        return await self._registry.prepare(
            resolved_model.config,
            intent=LLMIntent.BETA_READ,
            usage_limits=resolved.usage_limits,
            api_key=resolved_model.api_key,
            base_url=resolved_model.base_url,
        )

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
            NotFoundError: The novel is unknown or owned by another user
                (ownership gate, IDOR S12a — foreign ≡ unknown → 404).
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

        # ADR-086: first use — resolve routing + budgets after request-
        # body validation; ConfigurationError propagates loudly (RULE-11).
        resolved_model = await self._model_resolution.resolve()
        if self._budget_assembler is None:
            self._budget_assembler = await self._budget_assembler_factory()
        budget_assembler = self._budget_assembler

        # 1. Assemble context (validates chapters exist)
        deps = await assemble_context(self._assembler, novel_id, user_id, request.chapter_ids)

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

        # 6. Compose prompt via Mode 1 (composer-driven, ADR-048) with
        # correlated evidence + enrichment. Falls back to direct composition
        # on pipeline failure.
        composed = await compose_analysis_invocation_prompt(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            feature_id="analysis_beta_read",
            intent=LLMIntent.BETA_READ,
            novel_id=novel_id,
            user_id=user_id,
            language=deps.language,
            mode="beta_reader",
        )
        prepared = await self._prepare_model(resolved_model)

        agent = BetaReaderAgent(model=prepared.model, system_prompt=composed.system)
        user_prompt = await build_budgeted_prompt(deps, budget_assembler)
        result = await run_phase1(
            agent,
            user_prompt,
            deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

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
            NotFoundError: The novel is unknown or owned by another user
                (ownership gate, IDOR S12a — foreign ≡ unknown → 404).
            CacheRetrievalError: If Phase 1 cache is missing.
            AnalysisError: If context assembly or agent execution fails.
        """
        logger.info(
            "beta_reader_deep_dive_start",
            novel_id=str(novel_id),
            category=request.category.value,
        )

        # ADR-086: first use — resolve the routing cascade after request-
        # body validation; ConfigurationError propagates loudly (RULE-11).
        resolved_model = await self._model_resolution.resolve()

        # 1-2. Assemble deep-dive deps + cached Phase 1 retrieval (context
        # module owns the gate + content-aware cache key — RULE-04).
        deps = await deep_dive_deps(
            self._assembler,
            self._cache,
            novel_id=novel_id,
            user_id=user_id,
            chapter_ids=request.chapter_ids,
            category_value=request.category.value,
        )

        # 3. Compose Phase 2 prompt via Mode 1 (composer-driven, ADR-048)
        # with correlated evidence + enrichment. Falls back to direct
        # composition on pipeline failure.
        composed = await compose_analysis_invocation_prompt(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            feature_id="analysis_beta_read_deepdive",
            intent=LLMIntent.BETA_READ,
            novel_id=novel_id,
            user_id=user_id,
            language=deps.language,
            mode="beta_reader_deepdive",
        )
        prepared = await self._prepare_model(resolved_model)

        agent = BetaReaderAgent(model=prepared.model, system_prompt=composed.system)
        result = await run_phase2(
            agent,
            deps,
            prepared.model,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        # 4. Map to response
        response = map_phase2_response(result, novel_id, request.category)

        logger.info(
            "beta_reader_deep_dive_complete",
            novel_id=str(novel_id),
            category=request.category.value,
            feedback_count=len(response.detailed_feedback),
        )

        return response
