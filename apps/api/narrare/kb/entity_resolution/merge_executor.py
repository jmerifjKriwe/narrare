"""Deterministic merge executor for the KB entity resolution layer
(ADR-085 P4, spec §6).

Executes one endorsed merge: the survivor absorbs the loser's metadata
(recursive two-sided, merge-not-clobber — scalar conflicts are resolved in
the survivor's favor AND recorded in ``metadata["resolution"]["conflicts"]``),
every relationship edge referencing the loser is re-pointed to the survivor
(edges that would collide on ``uq_kb_relationships_unique(source_id,
target_id, rel_type)`` or self-reference the survivor are skipped and
counted, never deleted), the loser is set to ``status='deprecated'`` (a
CHECK-constraint value) with a ``metadata["resolution"]`` audit block, and
the survivor is flagged ``embeddings_dirty`` so the existing hooks re-embed.
The loser row is NEVER deleted — reversible, FK-safe, audit trail.

Survivor selection (§6.1) is the deterministic total order ``select_survivor``
(more metadata fact keys → more relationships → longer name → older
``created_at``); endorsement may override it but never the semantics. The
executor consumes a RESOLVED plan (survivor and loser named); the endorse
wiring (P4 router slice) calls ``select_survivor`` when the endorse body
omits the ``survivor_id`` override, so §6.1 semantics live only here.

The canonical survivor name is the ``decide_rename`` auto-result
(kb/_extraction_resolution.py) — the downgrade guard keeps the fuller name
("Anna" + "Anna Meyer" → "Anna Meyer"). Per PO ruling OQ-5 a plan-supplied
``result_name`` is accepted ONLY when it exactly equals that auto-result;
custom names raise ``ValueError`` (mapped to 422 at the HTTP seam).

The whole write phase runs inside one ``session.begin_nested()`` savepoint
(ExtractionApplyService pattern): any failure rolls the merge back cleanly
and leaves the outer transaction usable. Re-executing a loser already
deprecated BY THIS SURVIVOR is a logged no-op replaying the persisted
original counts (§6.6 idempotency, fix round 1); a deprecated loser under a
different ``merged_into`` is a stale plan and rejected. Chained merges
accumulate the survivor's ``resolution.conflicts`` — never clobbered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from narrare.kb._extraction_resolution import pick_canonical_name
from narrare.kb.entity_resolution._merge_metadata import (
    merge_metadata,
    persisted_int,
    persisted_str_list,
    read_resolution_block,
    resolution_block,
)
from narrare.kb.entity_resolution.schemas_resolution import (
    MergeExecutionResult,
    MergePlan,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.models import KBEntry
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

logger = structlog.get_logger(__name__)


def _survivor_rank(entry: KBEntry, relationship_count: int) -> tuple[int, int, int, float]:
    """Total-order rank per §6.1 — higher wins (older ``created_at`` negated)."""
    return (
        len(entry.metadata_ or {}),
        relationship_count,
        len(entry.name.strip().casefold()),
        -entry.created_at.timestamp(),
    )


def select_survivor(a: KBEntry, b: KBEntry, relationship_counts: Mapping[UUID, int]) -> UUID:
    """Pick the survivor of a candidate pair by the §6.1 deterministic order.

    Ties at every level fall through: fact keys → relationship count →
    name length (the ``decide_rename`` fuller-name guard supplies the
    canonical NAME after the survivor is chosen) → older ``created_at``.
    A total tie resolves to the first argument; the endorse wiring passes
    the pair in suggestion order ``(min_id, max_id)`` so the outcome is
    caller-independent.

    Args:
        a: First candidate entry.
        b: Second candidate entry.
        relationship_counts: Entry id → edge count (caller-resolved via the
            relationship repository).

    Returns:
        The id of the deterministic survivor.
    """
    rank_a = _survivor_rank(a, relationship_counts.get(a.id, 0))
    rank_b = _survivor_rank(b, relationship_counts.get(b.id, 0))
    return a.id if rank_a >= rank_b else b.id


class MergeExecutor:
    """Executes one endorsed merge (§6); idempotent on deprecated losers.

    Implements :class:`~narrare.kb.entity_resolution.contracts.MergeExecutorProtocol`.
    Dependencies are injected (RULE-19): the KB entry repository, the
    relationship repository, and the session owning the savepoint — the
    same collaborators the extraction apply flow consumes.
    """

    def __init__(
        self,
        kb_repo: KBRepository,
        rel_repo: RelationshipRepository,
        session: AsyncSession,
    ) -> None:
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._session = session

    async def execute(
        self,
        novel_id: UUID,
        user_id: UUID,
        plan: MergePlan,
    ) -> MergeExecutionResult:
        """Execute the merge described by ``plan`` (spec §6).

        Args:
            novel_id: Novel scope — both entries must belong to it
                (series-canon rows and foreign-novel entries are rejected
                as not-found, anti-enumeration).
            user_id: Authenticated user triggering the merge (audit log).
            plan: Resolved merge order (survivor, loser, suggestion id,
                optional OQ-5-validated result name, re-scored confidence).

        Returns:
            The merge outcome; for an idempotent re-execution on a
            deprecated loser, the zeroed result shape (logged, §6.6).

        Raises:
            ValueError: Degenerate plan (survivor == loser, deprecated
                survivor, or a custom ``result_name`` violating OQ-5) —
                mapped to 422 at the HTTP seam.
            NotFoundError: Missing or out-of-scope entry.
        """
        if plan.survivor_id == plan.loser_id:
            raise ValueError("survivor_id and loser_id must differ")
        survivor = await self._load_scoped(novel_id, plan.survivor_id)
        loser = await self._load_scoped(novel_id, plan.loser_id)
        if loser.status == "deprecated":
            prior = read_resolution_block(loser.metadata_)
            if prior.get("merged_into") != str(plan.survivor_id):
                raise ValueError("loser is already deprecated under a different merge — stale plan")
            logger.info(
                "merge_already_applied",
                novel_id=str(novel_id),
                user_id=str(user_id),
                survivor_id=str(plan.survivor_id),
                loser_id=str(plan.loser_id),
                suggestion_id=plan.suggestion_id,
            )
            return MergeExecutionResult(
                survivor_id=plan.survivor_id,
                loser_id=plan.loser_id,
                merged_fact_keys=persisted_str_list(prior, "merged_fact_keys"),
                repointed_relationships=persisted_int(prior, "repointed_relationships"),
                skipped_relationships=persisted_int(prior, "skipped_relationships"),
                conflicts=[],
            )
        if survivor.status == "deprecated":
            raise ValueError("survivor is deprecated — stale plan, re-run the analysis")
        canonical = pick_canonical_name(survivor.name, loser.name)
        if plan.result_name is not None and plan.result_name != canonical:
            raise ValueError(
                "result_name must equal the canonical name auto-pick "
                f"({canonical!r}); custom names are rejected (OQ-5)"
            )
        try:
            async with self._session.begin_nested():
                return await self._apply(plan, survivor, loser, final_name=canonical)
        except Exception as exc:
            logger.error(
                "merge_execution_failed",
                novel_id=str(novel_id),
                loser_id=str(plan.loser_id),
                error=str(exc),
                exc_info=True,
            )
            raise

    async def _load_scoped(self, novel_id: UUID, entry_id: UUID) -> KBEntry:
        """Fetch an entry that must exist inside ``novel_id`` (anti-enumeration)."""
        from narrare_core.shared.errors import NotFoundError

        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))
        return entry

    async def _apply(
        self, plan: MergePlan, survivor: KBEntry, loser: KBEntry, *, final_name: str
    ) -> MergeExecutionResult:
        """Perform all merge writes inside the caller's open savepoint."""
        merged_meta, conflicts, merged_keys = merge_metadata(survivor.metadata_, loser.metadata_)
        merged_at = datetime.now(tz=UTC).isoformat()
        merged_meta["resolution"] = resolution_block(
            read_resolution_block(merged_meta),
            conflicts,
            survivor_id=str(survivor.id),
            merged_at=merged_at,
            suggestion_id=plan.suggestion_id,
            confidence=plan.confidence,
        )
        survivor_data: dict[str, object] = {
            "metadata_": merged_meta,
            "embeddings_dirty": True,
        }
        if final_name != survivor.name:
            survivor_data["name"] = final_name
        await self._kb_repo.update(survivor, survivor_data)

        repointed, skipped = await self._repoint_edges(survivor, loser)

        loser_meta: dict[str, object] = dict(loser.metadata_ or {})
        loser_meta["resolution"] = {
            "merged_into": str(survivor.id),
            "merged_at": merged_at,
            "suggestion_id": plan.suggestion_id,
            "confidence": plan.confidence,
            "merged_fact_keys": merged_keys,
            "repointed_relationships": repointed,
            "skipped_relationships": skipped,
        }
        await self._kb_repo.update(loser, {"status": "deprecated", "metadata_": loser_meta})
        logger.info(
            "merge_executed",
            survivor_id=str(survivor.id),
            loser_id=str(loser.id),
            merged_fact_keys=merged_keys,
            repointed_relationships=repointed,
            skipped_relationships=skipped,
            conflicts=len(conflicts),
        )
        return MergeExecutionResult(
            survivor_id=survivor.id,
            loser_id=loser.id,
            merged_fact_keys=merged_keys,
            repointed_relationships=repointed,
            skipped_relationships=skipped,
            conflicts=conflicts,
        )

    async def _repoint_edges(self, survivor: KBEntry, loser: KBEntry) -> tuple[int, int]:
        """Re-point every loser edge to the survivor (§6.3).

        Edges that would self-reference the survivor (loser↔survivor ties,
        loser self-loops) or collide on ``uq_kb_relationships_unique`` are
        skipped, counted, and logged — the surviving counterpart edge is
        never deleted.
        """
        repointed = skipped = 0
        for edge in await self._rel_repo.list_for_entry(loser.id):
            new_source = survivor.id if edge.source_id == loser.id else edge.source_id
            new_target = survivor.id if edge.target_id == loser.id else edge.target_id
            if new_source == new_target:
                skipped += 1
                logger.warning(
                    "merge_edge_self_reference_skipped",
                    relationship_id=str(edge.id),
                    rel_type=edge.rel_type,
                )
                continue
            if await self._rel_repo.exists(new_source, new_target, edge.rel_type):
                skipped += 1
                logger.info(
                    "merge_edge_collision_skipped",
                    relationship_id=str(edge.id),
                    rel_type=edge.rel_type,
                    source_id=str(new_source),
                    target_id=str(new_target),
                )
                continue
            await self._rel_repo.update(edge, {"source_id": new_source, "target_id": new_target})
            repointed += 1
        return repointed, skipped
