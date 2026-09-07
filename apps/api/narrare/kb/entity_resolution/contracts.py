"""Entity-resolution sub-package contracts (ADR-085 P3/P4, spec §3).

Protocol definitions for the KB entity resolution lifecycle, written
before their implementations (RULE-03). ``SnapshotBuilderProtocol`` and
``ResolutionAnalyzerProtocol`` are implemented by the P3 slice;
``MergeExecutorProtocol`` by P4; ``UncertainBandAdjudicatorProtocol``
is declared with spec §3 signatures verbatim so the Protocol surface is
stable from day one — its implementation lands in a later slice.

Result-type bindings are discharged incrementally: ``ResolutionAnalysis``,
``MergePlan``, and ``MergeExecutionResult`` resolve to their concrete
Pydantic shapes from ``schemas_resolution.py``. ``PairCandidate`` and
``Adjudication`` remain provisionally bound to ``object`` until the T12
adjudicator slice defines them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

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

# --- Result-type bindings (discharged incrementally by implementing slices) ---

type ResolutionAnalysis = ResolutionAnalysisResponse
type MergeExecutionResult = MergeExecutionResultSchema
type MergePlan = MergePlanSchema
type PairCandidate = object
type Adjudication = object


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
