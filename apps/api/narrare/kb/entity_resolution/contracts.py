"""Entity-resolution sub-package contracts (ADR-085 P3, spec §3).

Protocol definitions for the KB entity resolution lifecycle, written
before their implementations (RULE-03). ``SnapshotBuilderProtocol`` is
implemented by this slice (P3); ``ResolutionAnalyzerProtocol``,
``MergeExecutorProtocol``, and ``UncertainBandAdjudicatorProtocol`` are
declared with spec §3 signatures verbatim so the Protocol surface is
stable from day one — their implementations land in later slices.

The result types the future protocols reference (``MergePlan``,
``MergeExecutionResult``, ``PairCandidate``, ``Adjudication``) remain
provisionally bound to ``object``: their concrete Pydantic shapes are
designed together with the implementing slices and land in later
modules, at which point these aliases are replaced by real imports.
``ResolutionAnalysis`` is already discharged — the analyzer protocol
resolves to ``ResolutionAnalysisResponse`` from
``schemas_resolution.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.entity_resolution.schemas_resolution import ResolutionAnalysisResponse
    from narrare_core.kb.resolution.models import EntitySnapshot

# --- Result-type bindings (discharged incrementally by implementing slices) ---

type ResolutionAnalysis = ResolutionAnalysisResponse
type MergeExecutionResult = object
type MergePlan = object
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


__all__ = [
    "MergeExecutorProtocol",
    "ResolutionAnalyzerProtocol",
    "SnapshotBuilderProtocol",
    "UncertainBandAdjudicatorProtocol",
]
