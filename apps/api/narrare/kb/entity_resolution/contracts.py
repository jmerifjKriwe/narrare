"""Entity-resolution sub-package contracts (ADR-085 P3-P5, spec §3).

Protocol definitions for the KB entity resolution lifecycle, written
before their implementations (RULE-03). ``SnapshotBuilderProtocol`` and
``ResolutionAnalyzerProtocol`` are implemented by the P3 slice;
``MergeExecutorProtocol`` by P4; ``UncertainBandAdjudicatorProtocol`` by
the P5 adapter (``adjudicator.py``).

Result-type bindings are all discharged: ``ResolutionAnalysis``,
``MergePlan``, and ``MergeExecutionResult`` resolve to their concrete
Pydantic shapes from ``schemas_resolution.py``; ``PairCandidate`` and
``Adjudication`` resolve to their concrete Pydantic shapes from
``schemas_adjudication.py`` (T12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

# Runtime imports: PEP 695 aliases evaluate lazily, so the schema names
# must exist when ``__value__`` is accessed (they are NOT annotation-only).
from narrare.kb.entity_resolution.schemas_adjudication import (
    Adjudication as AdjudicationSchema,
)
from narrare.kb.entity_resolution.schemas_adjudication import (
    PairCandidate as PairCandidateSchema,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.entity_resolution.schemas_resolution import (
        MergeExecutionResult as MergeExecutionResultSchema,
    )
    from narrare.kb.entity_resolution.schemas_resolution import (
        MergePlan as MergePlanSchema,
    )
    from narrare.kb.entity_resolution.schemas_resolution import (
        ResolutionAnalysisResponse,
    )
    from narrare_core.kb.resolution.models import EntitySnapshot

# --- Result-type bindings (all discharged; no provisional aliases remain) --------

type ResolutionAnalysis = ResolutionAnalysisResponse
type MergeExecutionResult = MergeExecutionResultSchema
type MergePlan = MergePlanSchema
type PairCandidate = PairCandidateSchema
type Adjudication = AdjudicationSchema


@runtime_checkable
class SnapshotBuilderProtocol(Protocol):
    """Assembles pure EntitySnapshot tuples for one novel scope."""

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]: ...


@runtime_checkable
class ResolutionAnalyzerProtocol(Protocol):
    """Detection pass: snapshots → scored, banded suggestions."""

    async def analyze(
        self,
        novel_id: UUID,
        user_id: UUID,
        *,
        refresh: bool = False,
    ) -> ResolutionAnalysis: ...

    async def invalidate(self, novel_id: UUID) -> None:
        """Drop the cached analysis for a novel (post-merge hook, §7)."""
        ...


@runtime_checkable
class MergeExecutorProtocol(Protocol):
    """Executes one endorsed merge; idempotent."""

    async def execute(
        self,
        novel_id: UUID,
        user_id: UUID,
        plan: MergePlan,
    ) -> MergeExecutionResult: ...


@runtime_checkable
class UncertainBandAdjudicatorProtocol(Protocol):
    """LLM annotation for mid-band pairs (adapter over KBMergeService)."""

    async def adjudicate(
        self,
        novel_id: UUID,
        user_id: UUID,
        pairs: Sequence[PairCandidate],
    ) -> Sequence[Adjudication]: ...


@runtime_checkable
class DismissedSuggestionStoreProtocol(Protocol):
    """Persistence seam for rejected resolution suggestions (spec §7).

    Implemented over the EXISTING dismissed-findings fingerprint table
    (the consistency-dismissal pattern); the concrete adapter owns the
    reserved ``resolution:`` namespace so the two domains stay disjoint.
    """

    async def dismiss(self, novel_id: UUID, suggestion_id: str) -> None: ...

    async def rejected_ids(self, novel_id: UUID) -> frozenset[str]: ...


__all__ = [
    "DismissedSuggestionStoreProtocol",
    "MergeExecutorProtocol",
    "ResolutionAnalyzerProtocol",
    "SnapshotBuilderProtocol",
    "UncertainBandAdjudicatorProtocol",
]
