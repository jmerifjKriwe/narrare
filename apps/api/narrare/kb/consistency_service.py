"""KB Consistency Service — orchestrates all three consistency analysis sources.

Combines:
- Phase 1: Relationship asymmetry (algorithmic, free, no LLM)
- Phase 2: Entry-internal consistency (LLM per entry via KBConsistencyAnalyzer)
- Phase 3: Cross-entity consistency (LLM via WorldbuildingAnalyzer._run_phase2)

Merges all issues, sorts by severity, caches the result, and returns a
unified :class:`ConsistencyCheckResponse`.

Every ``check`` call is gated on novel ownership at service entry (IDOR
fix S9): foreign and unknown novels are indistinguishable —
``NotFoundError`` → 404 — BEFORE the cache probe and before any phase
reads the novel's data.

See:
    :class:`narrare.kb.consistency_contracts.KBConsistencyProtocol`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.kb._consistency_helpers import (
    SEVERITY_ORDER,
    asymmetry_to_issue,
    generate_candidate_pairs,
)
from narrare.kb._consistency_invocation import compose_consistency_invocation
from narrare.kb._consistency_suppress import suppress_dismissed_issues
from narrare.kb._novel_gate import verify_novel_owned
from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
)
from narrare.kb.worldbuilding_contracts import ConsistencyCategory, ConsistencyIssue

if TYPE_CHECKING:
    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.contracts import (
        KBRepositoryProtocol,
        RelationshipRepositoryProtocol,
    )
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.memory.protocols import ConsistencyFeedbackCollector

logger = structlog.get_logger(__name__)


class KBConsistencyService:
    """Orchestrates all three consistency analysis sources.

    Args:
        analyzer: Entry-internal consistency analyzer (LLM).
        asymmetry_checker: Relationship asymmetry detector (algorithmic).
        worldbuilding_analyzer: Cross-entity consistency via Phase 2.
        kb_repo: KB entry repository for building Phase 3 deps.
        rel_repo: Relationship repository for candidate pair generation.
        novel_repo: Novel repository — the novel ownership gate (IDOR
            fix S9), checked before the cache probe and every phase.
        cache: In-memory cache for consistency results (10min TTL, ADR-080).
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
        novel_repo: NovelRepositoryProtocol,
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
        self._novel_repo = novel_repo
        self._invocation_pipeline = invocation_pipeline
        self._feedback_memory = feedback_memory
        self._max_phase2_pairs = max_phase2_pairs

    async def check(
        self,
        *,
        novel_id: UUID,
        request: ConsistencyCheckRequest,
        user_id: str,
    ) -> ConsistencyCheckResponse:
        """Run consistency check combining all 3 sources.

        Ownership gate first (IDOR fix S9): the caller must own
        ``novel_id`` — BEFORE the cache probe (a cached report must not
        leak to a foreign caller) and before any phase, algorithmic or
        LLM, reads the novel's data.

        Args:
            novel_id: The project to check.
            request: Check options and filters.
            user_id: Authenticated user identifier — REQUIRED (IDOR fix
                S9). Gates novel ownership before any phase; also scopes
                mem0 semantic-suppression queries (CR-AUFG-03-10).

        Returns:
            Complete consistency report with all requested issue types.

        Raises:
            NotFoundError: If the novel is unknown or not owned by the caller.
            ConfigurationError: If the user has no AI provider configured —
                raised loudly at the dual first-use resolve (ADR-086 L15),
                before the cache probe, so a warm cache never masks it.
        """
        # 0. Ownership gate — before the cache probe and every phase
        # (RULE-11: authorization gates RAISE, never degrade). It also
        # stays AHEAD of resolution (ADR-086): the routing cascades'
        # DB reads must not run for a caller who does not own the novel.
        await verify_novel_owned(self._novel_repo, novel_id, UUID(user_id))

        # 0a. Dual first-use resolve (ADR-086 L15): BOTH cascades resolve
        # here — after the gate, BEFORE the cache probe — so an
        # unconfigured provider stays a loud 400 even with a warm cache
        # (the eager factory resolved before any cache access; semantics
        # preserved, timing moved past validation). Idempotent: the
        # analyzers cache their triples, later phase calls re-read them.
        await self._analyzer.ensure_resolved()
        await self._worldbuilding_analyzer.ensure_resolved()

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
        # for LLM phases (ADR-048). Covers both Phase 2 (entry-internal) and
        # Phase 3 (cross-entity); best-effort — see
        # compose_consistency_invocation.
        has_llm_phase = request.include_entry_internal or request.include_cross_entity
        if has_llm_phase:
            await compose_consistency_invocation(
                invocation_pipeline=self._invocation_pipeline,
                novel_id=novel_id,
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
            key=lambda i: SEVERITY_ORDER.get(i.severity.value, 1),
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
