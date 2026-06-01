"""WorldbuildingAnalyzer — LLM orchestration for worldbuilding analysis.

Assembles entity data from KB repositories into WorldbuildingDeps,
manages token budgets for large projects (100+ entities), and orchestrates
Phase 1 (gaps + connections) and Phase 2 (consistency) via WorldbuildingAgent.

Entity assembly helpers live in :mod:`narrare.kb.worldbuilding_entity_assembly`.

See:
    :class:`narrare.kb.worldbuilding_contracts.WorldbuildingProtocol`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

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
from narrare.kb.worldbuilding_entity_assembly import (
    build_available_rel_types,
    build_entity_summaries,
    build_template_structures,
    get_adjacency_safe,
    get_relationships_for,
    list_entities,
    prioritize_entities,
)
from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import WorldbuildingDeps
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.registry import PromptRegistry

logger = structlog.get_logger(__name__)

_MAX_PHASE2_PAIRS = 15


class WorldbuildingAnalyzer:
    """LLM orchestration for worldbuilding analysis.

    Assembles entity data, manages token budgets, and orchestrates
    Phase 1 (gaps + connections) and Phase 2 (consistency) via
    WorldbuildingAgent.
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        rel_repo: RelationshipRepositoryProtocol,
        cache: WorldbuildingCache,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
        prompt_registry: PromptRegistry,
    ) -> None:
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._cache = cache
        self._registry = registry
        self._config = config
        self._composer = composer
        self._prompt_registry = prompt_registry

    async def analyze(
        self,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
    ) -> WorldbuildingAnalysisResponse:
        """Full analysis: cache → build deps → phase 1 → phase 2 → cache store."""
        novel_str = str(novel_id)
        types_hash = WorldbuildingCache.hash_entity_types(request.entity_types)

        if not request.refresh:
            cached = await self._cache.get(novel_str, types_hash)
            if cached is not None:
                return WorldbuildingAnalysisResponse.model_validate_json(cached)

        deps, total_count = await self._build_deps(novel_id, request.entity_types)
        gaps, connections, pairs, score, assessment = await self._run_phase1(deps)

        issues: list[ConsistencyIssue] = []
        if request.include_consistency and pairs:
            issues = await self._run_phase2(deps, pairs)

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
    # Deps Assembly
    # ------------------------------------------------------------------

    async def _build_deps(
        self,
        novel_id: UUID,
        entity_types: list[str] | None,
    ) -> tuple[WorldbuildingDeps, int]:
        """Assemble entity data into WorldbuildingDeps."""
        entities = await list_entities(self._kb_repo, novel_id, entity_types)
        total_count = len(entities)
        if not entities:
            return WorldbuildingDeps(language="en"), 0

        adjacency = await get_adjacency_safe(self._rel_repo, novel_id, entities)
        summaries = build_entity_summaries(entities, adjacency)
        prioritized = prioritize_entities(summaries)
        relationships = await get_relationships_for(prioritized, self._rel_repo)

        type_set = {e.entity_type for e in entities}
        return WorldbuildingDeps(
            language="en",
            entity_summaries=prioritized,
            template_structures=build_template_structures(type_set),
            existing_relationships=relationships,
            available_rel_types=build_available_rel_types(type_set),
        ), total_count

    # ------------------------------------------------------------------
    # Phase Execution
    # ------------------------------------------------------------------

    async def _run_phase1(
        self,
        deps: WorldbuildingDeps,
    ) -> tuple[list[GapFinding], list[ConnectionSuggestion], list[tuple[str, str]], float, str]:
        """Execute Phase 1: gap detection + connection suggestions."""
        ctx = PromptContext(
            language="en",
            mode=LLMIntent.KB_WORLDBUILD.value,
            extra={
                "entity_count": str(len(deps.entity_summaries)),
                "entity_types": ", ".join(sorted(deps.template_structures.keys())),
            },
        )
        composed = await self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)

        model = await self._registry.get_model(self._config)
        agent = WorldbuildingAgent(model=model, system_prompt=composed.system)
        result = await agent.run_phase1(
            prompt=(
                f"Analyze worldbuilding for {len(deps.entity_summaries)} entities. "
                "Identify gaps, suggest connections, evaluate health."
            ),
            deps=deps,
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
    ) -> list[ConsistencyIssue]:
        """Execute Phase 2: consistency checking on candidate pairs."""
        pairs = candidate_pairs[:_MAX_PHASE2_PAIRS]

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

        # Resolve Phase 2 prompt from registry (different mode from Phase 1)
        try:
            resolved = await self._prompt_registry.resolve(
                category="kb",
                language="en",
                mode="worldbuilding/phase2",
            )
            system_prompt = resolved.system_prompt
        except Exception:
            logger.warning("phase2_prompt_fallback", exc_info=True)
            system_prompt = "Check entity pairs for worldbuilding contradictions."

        model = await self._registry.get_model(self._config)
        agent = WorldbuildingAgent(model=model)
        result = await agent.run_phase2(
            prompt=f"Check consistency for {len(pairs)} entity pairs.",
            deps=phase2_deps,
            model=model,
            system_prompt=system_prompt,
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
