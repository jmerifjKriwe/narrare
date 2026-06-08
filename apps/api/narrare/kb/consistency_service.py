"""KB Consistency Service — orchestrates all three consistency analysis sources.

Combines:
- Phase 1: Relationship asymmetry (algorithmic, free, no LLM)
- Phase 2: Entry-internal consistency (LLM per entry via KBConsistencyAnalyzer)
- Phase 3: Cross-entity consistency (LLM via WorldbuildingAnalyzer._run_phase2)

Merges all issues, sorts by severity, caches the result, and returns a
unified :class:`ConsistencyCheckResponse`.

See:
    :class:`narrare.kb.consistency_contracts.KBConsistencyProtocol`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    RelationshipAsymmetry,
)
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    ConsistencyIssue,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)

_SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "major": 1,
    "minor": 2,
    "info": 3,
}


class KBConsistencyService:
    """Orchestrates all three consistency analysis sources.

    Args:
        analyzer: Entry-internal consistency analyzer (LLM).
        asymmetry_checker: Relationship asymmetry detector (algorithmic).
        worldbuilding_analyzer: Cross-entity consistency via Phase 2.
        kb_repo: KB entry repository for building Phase 3 deps.
        rel_repo: Relationship repository for candidate pair generation.
        cache: Redis-backed cache for consistency results (10min TTL).
        invocation_pipeline: Optional pipeline for invocation evidence.
        max_phase2_pairs: Maximum number of entity pairs for Phase 2 cross-entity check.
    """

    def __init__(
        self,
        analyzer: KBConsistencyAnalyzer,
        asymmetry_checker: RelationshipAsymmetryChecker,
        worldbuilding_analyzer: WorldbuildingAnalyzer,
        kb_repo: KBRepositoryProtocol,
        rel_repo: RelationshipRepositoryProtocol,
        cache: ConsistencyCache,
        invocation_pipeline: InvocationPipeline | None = None,
        *,
        max_phase2_pairs: int = 15,
    ) -> None:
        self._analyzer = analyzer
        self._asymmetry_checker = asymmetry_checker
        self._worldbuilding_analyzer = worldbuilding_analyzer
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._cache = cache
        self._invocation_pipeline = invocation_pipeline
        self._max_phase2_pairs = max_phase2_pairs

    async def check(
        self,
        *,
        novel_id: UUID,
        request: ConsistencyCheckRequest,
    ) -> ConsistencyCheckResponse:
        """Run consistency check combining all 3 sources.

        Args:
            novel_id: The project to check.
            request: Check options and filters.

        Returns:
            Complete consistency report with all requested issue types.
        """
        novel_str = str(novel_id)
        types_hash = self._cache.hash_entity_types(request.entity_types)

        # 1. Check cache (unless refresh=True)
        if not request.refresh:
            cached = await self._cache.get(novel_str, types_hash)
            if cached is not None:
                return ConsistencyCheckResponse.model_validate_json(cached)

        all_issues: list[ConsistencyIssue] = []
        entity_count = 0

        # 2. Phase 1: Asymmetry check (algorithmic, free — runs first)
        if request.include_asymmetry:
            asymmetry_issues = await self._run_asymmetry(novel_id)
            all_issues.extend(asymmetry_issues)

        # 2a. Record invocation evidence for LLM phases (ADR-040)
        has_llm_phase = request.include_entry_internal or request.include_cross_entity
        if has_llm_phase:
            from narrare._app.invocation_context import safe_record_evidence
            from narrare_core.llm.intents import LLMIntent

            await safe_record_evidence(
                self._invocation_pipeline,
                feature_id="kb_consistency",
                intent=LLMIntent.KB_CONSISTENCY,
                project_id=novel_id,
            )

        # 3. Phase 2: Entry-internal check (LLM per entry)
        if request.include_entry_internal:
            entry_issues, count = await self._analyzer.analyze_entries(
                novel_id,
                request.entity_types,
            )
            all_issues.extend(entry_issues)
            entity_count = count

        # 4. Phase 3: Cross-entity check (LLM via WorldbuildingAnalyzer)
        if request.include_cross_entity:
            cross_issues = await self._run_cross_entity(
                novel_id,
                request.entity_types,
            )
            all_issues.extend(cross_issues)

        # 5. Sort by severity (critical first)
        all_issues.sort(
            key=lambda i: _SEVERITY_ORDER.get(i.severity.value, 1),
        )

        # 6. Build summary
        summary = {
            "entry_internal": sum(
                1 for i in all_issues if i.category == ConsistencyCategory.ENTRY_INTERNAL
            ),
            "asymmetry": sum(
                1 for i in all_issues if i.category == ConsistencyCategory.RELATIONSHIP_ASYMMETRY
            ),
            "cross_entity": sum(
                1
                for i in all_issues
                if i.category
                not in (
                    ConsistencyCategory.ENTRY_INTERNAL,
                    ConsistencyCategory.RELATIONSHIP_ASYMMETRY,
                )
            ),
        }

        response = ConsistencyCheckResponse(
            novel_id=novel_str,
            entity_count=entity_count,
            issues=all_issues,
            summary=summary,
            checked_at=datetime.now(UTC).isoformat(),
        )

        # 7. Cache result
        await self._cache.set(novel_str, response.model_dump_json(), types_hash)

        logger.info(
            "consistency_check_complete",
            novel_id=novel_str,
            total_issues=len(all_issues),
            summary=summary,
        )
        return response

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    async def _run_asymmetry(self, novel_id: UUID) -> list[ConsistencyIssue]:
        """Run Phase 1: relationship asymmetry detection (algorithmic)."""
        asymmetries = await self._asymmetry_checker.check(novel_id)
        return [_asymmetry_to_issue(idx, a) for idx, a in enumerate(asymmetries)]

    async def _run_cross_entity(
        self,
        novel_id: UUID,
        entity_types: list[str] | None,
    ) -> list[ConsistencyIssue]:
        """Run Phase 3: cross-entity consistency via WorldbuildingAnalyzer."""
        from narrare.kb.worldbuilding_entity_assembly import (
            build_entity_summaries,
            build_template_structures,
            get_adjacency_safe,
            get_relationships_for,
            list_entities,
            prioritize_entities,
        )
        from narrare_core.agents.worldbuilding_types import WorldbuildingDeps

        entities = await list_entities(self._kb_repo, novel_id, entity_types)
        if not entities:
            return []

        adjacency = await get_adjacency_safe(self._rel_repo, novel_id, entities)
        summaries = build_entity_summaries(entities, adjacency)
        prioritized = prioritize_entities(summaries)
        relationships = await get_relationships_for(prioritized, self._rel_repo)

        type_set = {e.entity_type for e in entities}
        deps = WorldbuildingDeps(
            language="en",
            entity_summaries=prioritized,
            template_structures=build_template_structures(type_set),
            existing_relationships=relationships,
        )

        pairs = _generate_candidate_pairs(adjacency, self._max_phase2_pairs)
        if not pairs:
            return []

        # Reuses WorldbuildingAnalyzer._run_phase2() per KB-004 spec (Option C).
        return await self._worldbuilding_analyzer._run_phase2(deps, pairs)  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _asymmetry_to_issue(idx: int, a: RelationshipAsymmetry) -> ConsistencyIssue:
    """Convert a :class:`RelationshipAsymmetry` to a :class:`ConsistencyIssue`."""
    return ConsistencyIssue(
        finding_index=idx,
        category=ConsistencyCategory.RELATIONSHIP_ASYMMETRY,
        entity_ids=[a.source_id, a.target_id],
        entity_names=[a.source_name, a.target_name],
        description=(
            f"Asymmetric relationship: {a.source_name} \u2192 {a.target_name} "
            f"({a.forward_rel_type})"
        ),
        contradiction=(
            f"Forward: {a.forward_rel_type}, "
            f"Reverse: {a.reverse_rel_type or 'none'}, "
            f"Expected: {a.expected_inverse or 'none'}"
        ),
        suggested_resolution=(
            f"Add {a.expected_inverse} relationship from {a.target_name} to {a.source_name}"
        )
        if a.expected_inverse
        else None,
        severity=a.severity,
        confidence=1.0,  # Algorithmic — deterministic
    )


def _generate_candidate_pairs(
    adjacency: dict[str, set[str]],
    max_pairs: int = 15,
) -> list[tuple[str, str]]:
    """Generate entity pairs from existing relationships for cross-entity check.

    Uses the adjacency map to find connected entity pairs, deduplicating
    by unordered pair.  Only pairs with actual relationships are included —
    the most likely source of cross-entity consistency issues.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()

    for entity_id, connected in adjacency.items():
        for other_id in connected:
            pair = frozenset({entity_id, other_id})
            if pair not in seen:
                seen.add(pair)
                pairs.append((entity_id, other_id))
                if len(pairs) >= max_pairs:
                    return pairs
    return pairs
