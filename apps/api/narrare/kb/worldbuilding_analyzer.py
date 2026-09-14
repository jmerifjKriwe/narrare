"""WorldbuildingAnalyzer — LLM orchestration for worldbuilding analysis.

Assembles entity data from KB repositories into WorldbuildingDeps,
manages token budgets for large projects (100+ entities), and orchestrates
Phase 1 (gaps + connections) and Phase 2 (consistency) via WorldbuildingAgent.

The per-user model routing cascade is wired as a ``LazyModelResolution``
and resolves on first use (ADR-086) — never at construction.

Entity assembly helpers live in :mod:`narrare.kb.worldbuilding_entity_assembly`.

See:
    :class:`narrare.kb.worldbuilding_contracts.WorldbuildingProtocol`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.kb.worldbuilding_cache import WorldbuildingCache
from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    ConsistencyCategory,
    ConsistencyIssue,
    GapFinding,
    GapType,
    WorldbuildingAnalysisRequest,
    WorldbuildingAnalysisResponse,
    WorldbuildingSeverity,
)
from narrare.kb.worldbuilding_entity_assembly import build_deps
from narrare.kb.worldbuilding_prompt_formatting import (
    format_candidate_pairs,
    format_entity_details,
    format_relationships,
)
from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import WorldbuildingDeps
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class WorldbuildingAnalyzer:
    """LLM orchestration for worldbuilding analysis.

    Assembles entity data, manages token budgets, and orchestrates
    Phase 1 (gaps + connections) and Phase 2 (consistency) via
    WorldbuildingAgent.

    Args:
        kb_repo: KB entry repository.
        rel_repo: Relationship repository.
        cache: In-memory worldbuilding cache (ADR-080).
        registry: Model registry for LLM access.
        model_resolution: Lazy per-user model resolution (ADR-086) — the
            routing cascade resolves on first use, never at construction.
        composer: Prompt composer for building prompts (both phases).
        max_phase2_pairs: Maximum number of entity pairs for Phase 2 consistency check.
        invocation_pipeline: Optional pipeline for invocation evidence (ADR-040).
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        rel_repo: RelationshipRepositoryProtocol,
        cache: WorldbuildingCache,
        registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer,
        *,
        max_phase2_pairs: int = 15,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._cache = cache
        self._registry = registry
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._composer = composer
        self._max_phase2_pairs = max_phase2_pairs
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        caches the triple; repeat calls return the cached value without
        re-running the cascade. Errors propagate loudly and are never
        cached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a 400 on this AI-mandatory endpoint.
        """
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

    async def _prepare(self) -> PreparedModelCall:
        """Resolve the coherent call triple lazily from the registry.

        Single assembly point (Task 6c — Task 4/5 pattern): model +
        intent-aware runtime settings + usage limits as one result.
        Forwards the per-user provider credentials from the resolved
        cascade triple (model-routing cascade, ADR-086).
        """
        resolved = await self.ensure_resolved()
        limit_resolved = self._run_limit_resolver.resolve(
            config=resolved.config, budget=None, invocation_id=uuid4()
        )
        return await self._registry.prepare(
            resolved.config,
            intent=LLMIntent.KB_WORLDBUILD,
            usage_limits=limit_resolved.usage_limits,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

    async def analyze(
        self,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
    ) -> WorldbuildingAnalysisResponse:
        """Full analysis: cache → build deps → phase 1 → phase 2 → cache store."""
        # ADR-086: resolve BEFORE the cache lookup so an unconfigured
        # provider stays a loud 400 even with a warm cache (the eager
        # factory resolved before any cache access — semantics preserved).
        await self.ensure_resolved()

        novel_str = str(novel_id)
        types_hash = WorldbuildingCache.hash_entity_types(request.entity_types)

        if not request.refresh:
            cached = await self._cache.get(novel_str, types_hash)
            if cached is not None:
                return WorldbuildingAnalysisResponse.model_validate_json(cached)

        deps, total_count = await build_deps(
            self._kb_repo, self._rel_repo, novel_id, request.entity_types
        )
        gaps, connections, pairs, score, assessment = await self._run_phase1(deps, novel_id)

        issues: list[ConsistencyIssue] = []
        if request.include_consistency and pairs:
            issues = await self._run_phase2(deps, pairs, novel_id)

        response = WorldbuildingAnalysisResponse(
            novel_id=novel_str,
            entity_count=total_count,
            gap_findings=gaps if request.include_gaps else [],
            connection_suggestions=connections if request.include_connections else [],
            consistency_issues=issues,
            worldbuilding_score=score,
            overall_assessment=assessment,
            summary={
                "total_entities": total_count,
                "gaps_found": len(gaps),
                "connections_suggested": len(connections),
                "consistency_issues": len(issues),
                "entities_in_analysis": len(deps.entity_summaries),
            },
            analyzed_at=datetime.now(UTC).isoformat(),
        )

        await self._cache.set(novel_str, response.model_dump_json(), types_hash)
        return response

    # ------------------------------------------------------------------
    # Phase Execution
    # ------------------------------------------------------------------

    async def _run_phase1(
        self,
        deps: WorldbuildingDeps,
        novel_id: UUID,
    ) -> tuple[list[GapFinding], list[ConnectionSuggestion], list[tuple[str, str]], float, str]:
        """Execute Phase 1: gap detection + connection suggestions."""
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation

        ctx = PromptContext(
            language="en",
            mode="worldbuilding/phase1",
            extra={
                "entity_count": str(len(deps.entity_summaries)),
                "entity_types": ", ".join(sorted(deps.template_structures.keys())),
            },
        )
        invocation_context = build_invocation_context(
            feature_id="kb_worldbuilding_phase1",
            intent=LLMIntent.KB_WORLDBUILD,
            project_id=novel_id,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._composer,
                prompt_context=ctx,
                intent=LLMIntent.KB_WORLDBUILD,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt = invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="kb_worldbuilding_phase1",
                exc_info=True,
            )
            composed = await self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)
            system_prompt = composed.system

        prepared = await self._prepare()
        agent = WorldbuildingAgent(model=prepared.model, system_prompt=system_prompt)
        result = await agent.run_phase1(
            prompt=(
                f"Analyze worldbuilding for {len(deps.entity_summaries)} entities. "
                "Identify gaps, suggest connections, evaluate health."
            ),
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        type_map = {s.entry_id: s.entity_type for s in deps.entity_summaries}
        gaps = [
            GapFinding(
                gap_type=_safe_gap_type(g.gap_type),
                severity=_safe_severity(g.severity),
                **{k: v for k, v in g.model_dump().items() if k not in ("gap_type", "severity")},
            )
            for g in result.gaps
        ]
        connections = [
            ConnectionSuggestion(
                finding_index=idx,
                source_entity_type=type_map.get(c.source_entity_id, ""),
                target_entity_type=type_map.get(c.target_entity_id, ""),
                **c.model_dump(),
            )
            for idx, c in enumerate(result.connection_suggestions)
        ]
        return (
            gaps,
            connections,
            result.candidate_pairs_for_consistency,
            result.worldbuilding_score,
            result.assessment,
        )

    async def _run_phase2(
        self,
        deps: WorldbuildingDeps,
        candidate_pairs: list[tuple[str, str]],
        novel_id: UUID,
    ) -> list[ConsistencyIssue]:
        """Execute Phase 2: consistency checking on candidate pairs."""
        pairs = candidate_pairs[: self._max_phase2_pairs]

        # Load full entity details for pair entities
        entity_details: dict[str, dict[str, object]] = {}
        for src_id, tgt_id in pairs:
            for eid in (src_id, tgt_id):
                if eid not in entity_details:
                    entry = await self._kb_repo.get_by_id(UUID(eid))
                    if entry:
                        entity_details[eid] = {
                            "name": entry.name,
                            "entity_type": entry.entity_type,
                            "metadata": dict(entry.metadata_ or {}),
                            "body": (entry.body[:2000] if entry.body else ""),
                            "tags": list(entry.tags) if entry.tags else [],
                        }

        phase2_deps = WorldbuildingDeps(
            language="en",
            entity_summaries=deps.entity_summaries,
            entity_details=entity_details,
            template_structures=deps.template_structures,
            existing_relationships=deps.existing_relationships,
            candidate_pairs=pairs,
        )

        # Compose Phase 2 prompt via compose_invocation (Mode 1 — composer-driven,
        # ADR-046/048). "worldbuilding/phase2" is a governed route for
        # KB_WORLDBUILD (see route_table.py allowed_context_modes).
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation

        ctx = PromptContext(
            language="en",
            mode="worldbuilding/phase2",
            extra={
                "candidate_pairs": format_candidate_pairs(pairs, entity_details),
                "entity_details": format_entity_details(entity_details),
                "existing_relationships": format_relationships(
                    deps.existing_relationships,
                ),
            },
        )
        invocation_context = build_invocation_context(
            feature_id="kb_worldbuilding_phase2",
            intent=LLMIntent.KB_WORLDBUILD,
            project_id=novel_id,
        )
        phase2_user_prompt = f"Check consistency for {len(pairs)} entity pairs."
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._composer,
                prompt_context=ctx,
                intent=LLMIntent.KB_WORLDBUILD,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt = invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="kb_worldbuilding_phase2",
                exc_info=True,
            )
            composed = await self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)
            system_prompt = composed.system

        prepared = await self._prepare()
        agent = WorldbuildingAgent(model=prepared.model)
        result = await agent.run_phase2(
            prompt=phase2_user_prompt,
            deps=phase2_deps,
            model=prepared.model,
            system_prompt=system_prompt,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        return [
            ConsistencyIssue(
                finding_index=idx,
                category=_safe_category(i.category),
                severity=_safe_severity(i.severity),
                **{k: v for k, v in i.model_dump().items() if k not in ("category", "severity")},
            )
            for idx, i in enumerate(result.issues)
        ]


def _safe_gap_type(raw: str) -> GapType:
    """Parse gap type, defaulting to MISSING_FIELD."""
    try:
        return GapType(raw)
    except ValueError:
        return GapType.MISSING_FIELD


def _safe_severity(raw: str) -> WorldbuildingSeverity:
    """Parse severity, defaulting to MAJOR."""
    try:
        return WorldbuildingSeverity(raw)
    except ValueError:
        return WorldbuildingSeverity.MAJOR


def _safe_category(raw: str) -> ConsistencyCategory:
    """Parse category, defaulting to SYSTEM_RULES."""
    try:
        return ConsistencyCategory(raw)
    except ValueError:
        return ConsistencyCategory.SYSTEM_RULES
