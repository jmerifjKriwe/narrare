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

from narrare.kb._consistency_helpers import (
    asymmetry_to_issue,
    generate_candidate_pairs,
)
from narrare.kb._consistency_suppress import suppress_dismissed_issues
from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
)
from narrare.kb.worldbuilding_contracts import ConsistencyCategory, ConsistencyIssue
from narrare_core.ai_invocation import ManualInjectionDeclaration

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.memory.protocols import ConsistencyFeedbackCollector

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration: KBConsistencyAnalyzer and WorldbuildingAnalyzer
# compose their prompts internally from deps (entity summaries, template
# structures, existing relationships). Evidence is recorded at the parent
# service layer, covering both Phase 2 (entry-internal) and Phase 3
# (cross-entity) LLM calls.
_CONSISTENCY_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "KBConsistencyAnalyzer and WorldbuildingAnalyzer compose their prompts "
        "internally from deps (entity summaries, template structures, "
        "existing relationships). See ADR-044 staged consistency pipeline."
    ),
    variables=("entity_summaries", "template_structures", "existing_relationships"),
    injection_mechanism="agent_deps",
)

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
        feedback_memory: Optional mem0-backed dismissal collector. When
            present and the caller authenticates a user, issues that match a
            past dismissal are filtered out and counted in the response's
            ``suppressed_count`` (CR-AUFG-03-10). ``None`` (default) disables
            suppression — passthrough behaviour (RULE-11).
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
        feedback_memory: ConsistencyFeedbackCollector | None = None,
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
        self._feedback_memory = feedback_memory
        self._max_phase2_pairs = max_phase2_pairs

    async def check(
        self,
        *,
        novel_id: UUID,
        request: ConsistencyCheckRequest,
        user_id: str | None = None,
    ) -> ConsistencyCheckResponse:
        """Run consistency check combining all 3 sources.

        Args:
            novel_id: The project to check.
            request: Check options and filters.
            user_id: Authenticated user identifier, used to scope mem0
                semantic-suppression queries (CR-AUFG-03-10). ``None``
                disables suppression (passthrough).

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

        # 2a. Compose invocation (Mode 2 — agent-internal) and record evidence
        # for LLM phases (ADR-048). Replaces the former placeholder-evidence
        # path. Covers both Phase 2 (entry-internal) and Phase 3 (cross-entity).
        has_llm_phase = request.include_entry_internal or request.include_cross_entity
        if has_llm_phase:
            from narrare._app.invocation_context import build_invocation_context
            from narrare_core.ai_invocation import compose_invocation
            from narrare_core.llm.intents import LLMIntent

            invocation_context = build_invocation_context(
                feature_id="kb_consistency",
                intent=LLMIntent.KB_CONSISTENCY,
                project_id=novel_id,
            )
            try:
                await compose_invocation(
                    invocation_pipeline=self._invocation_pipeline,
                    invocation_context=invocation_context,
                    manual_injection=_CONSISTENCY_MANUAL_INJECTION,
                )
            except Exception:
                logger.warning(
                    "invocation_composition_failed",
                    feature_id="kb_consistency",
                    exc_info=True,
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

        # 5a. Semantic suppression (CR-AUFG-03-10): filter out issues the
        # user previously dismissed. Best-effort (RULE-11) — fails open:
        # mem0 unavailability or a flaky query leaves all issues visible.
        all_issues, suppressed_count = await suppress_dismissed_issues(
            all_issues,
            self._feedback_memory,
            user_id,
            novel_id,
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
            suppressed_count=suppressed_count,
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
        return [asymmetry_to_issue(idx, a) for idx, a in enumerate(asymmetries)]

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

        pairs = generate_candidate_pairs(adjacency, self._max_phase2_pairs)
        if not pairs:
            return []

        # Reuses WorldbuildingAnalyzer._run_phase2() per KB-004 spec (Option C).
        return await self._worldbuilding_analyzer._run_phase2(deps, pairs, novel_id)  # pyright: ignore[reportPrivateUsage]
