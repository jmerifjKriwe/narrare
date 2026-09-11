"""Shared fakes and corpus builders for the uncertain-band adjudicator tests.

Split per RULE-04 (``_router_helpers.py`` sits near its 400-line hard
limit; the P5 slice adds the adjudicator seams). Mirrors the established
helper convention: module-level fakes + factory helpers, imported by the
test modules and by the production-fidelity app builders.

Corpora use disjoint name families (Anna*, Bella*, Carla*) so the engine's
name-tier candidate filter never pairs across families — each family's
band is exactly the §4 worked-example outcome:

- REVIEW: "Anna" (ch-01-03) / "Anna Meyer" (ch-04-06) → 0.545;
- AUTO_ELIGIBLE: "Bella" / "Bella Schmidt" (handoff + attributes +
  neighborhood + embedding) → 0.895;
- SUPPRESSED: "Carla Meyer" (ch-08-10) / "Carla Meier" (ch-09-11)
  co-active distractor → temporal veto, never surfaced.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.kb.entity_resolution.adjudicator import UncertainBandAdjudicator
from narrare.kb.entity_resolution.schemas_adjudication import Adjudication, PairCandidate
from narrare.kb.schemas_merge import MergeDecisionResponse, MergeRequest, MergeResponse
from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance

if TYPE_CHECKING:
    from uuid import UUID as UUIDT

    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare.kb.entity_resolution.contracts import (
        SnapshotBuilderProtocol,
        UncertainBandAdjudicatorProtocol,
    )
    from narrare.kb.merge_contracts import KBMergeServiceProtocol
    from narrare_core.writing.session_manager import SessionCacheProtocol

SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)


# --- Fakes ----------------------------------------------------------------------


class FakeAdjudicator:
    """Fake ``UncertainBandAdjudicatorProtocol`` recording submissions."""

    def __init__(self, note: str = "LLM: likely the same person.") -> None:
        self.calls: list[tuple[UUIDT, UUIDT, list[PairCandidate]]] = []
        self._note = note

    @property
    def calls_count(self) -> int:
        return len(self.calls)

    async def adjudicate(
        self,
        novel_id: UUIDT,
        user_id: UUIDT,
        pairs: list[PairCandidate],
    ) -> list[Adjudication]:
        self.calls.append((novel_id, user_id, list(pairs)))
        return [
            Adjudication(pair_key=p.pair_key, supports_merge=True, note=self._note) for p in pairs
        ]


class _StubMergeService:
    """Quiet KBMergeService stand-in for production-fidelity test builders.

    The builders' corpora reach the annotation path only via the REAL
    analyze wiring; the stub keeps those requests hermetic and fast (the
    verdict itself is never asserted there — the adapter tests above own
    the conversion/verdict semantics).
    """

    async def analyze_merge_candidates(
        self, novel_id: UUIDT, user_id: UUIDT, request: MergeRequest
    ) -> MergeResponse:
        return MergeResponse(
            merge_decisions=[
                MergeDecisionResponse(
                    pair_id="1", decision="merge", confidence=1.0, reasoning="stub"
                )
            ],
            overall_notes="",
        )


def stub_adjudicator() -> UncertainBandAdjudicator:
    """Adjudicator over the stub merge service (hermetic LLM stand-in)."""

    async def factory(novel_id: UUIDT, user_id: UUIDT) -> KBMergeServiceProtocol:
        return _StubMergeService()

    return UncertainBandAdjudicator(merge_service_factory=factory)


async def noop_limiter() -> None:
    """No-op stand-in for the AI_ANALYSIS_LIMITER dependency in route tests."""


# --- Corpus builders -------------------------------------------------------------


def _snapshot(
    name: str,
    *,
    chapters: tuple[int, ...],
    metadata: dict[str, object] | None = None,
    neighbor_ids: frozenset[UUID] | None = None,
    embedding: tuple[float, ...] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata=dict(metadata or {}),
        provenance=EntryProvenance(
            chapters=chapters,
            first_seen_chapter=chapters[0],
            last_seen_chapter=chapters[-1],
            name_variants=(),
        ),
        neighbor_ids=neighbor_ids if neighbor_ids is not None else frozenset(),
        embedding=embedding,
    )


def _auto_pair() -> tuple[EntitySnapshot, EntitySnapshot]:
    """ "Bella" hands off to "Bella Schmidt" with corroborating evidence → 0.895."""
    shared = frozenset({uuid4(), uuid4()})
    bella = _snapshot(
        "Bella",
        chapters=(1, 2, 3),
        metadata={"age (2017)": 30},
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    bella_schmidt = _snapshot(
        "Bella Schmidt",
        chapters=(4, 5, 6),
        metadata={"age (2018)": 31},
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    return bella, bella_schmidt


def suggestion_id_for(a: UUID, b: UUID) -> str:
    """The stateless suggestion id: sha256(min ‖ max)[:16]."""
    lo, hi = sorted((str(a), str(b)))
    return hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16]


def make_review_and_auto_corpus() -> tuple[tuple[EntitySnapshot, ...], str]:
    """One REVIEW pair (Anna family) + one AUTO pair (Bella family).

    Returns the snapshots and the REVIEW pair's suggestion id.
    """
    anna = _snapshot("Anna", chapters=(1, 2, 3))
    anna_meyer = _snapshot("Anna Meyer", chapters=(4, 5, 6))
    bella, bella_schmidt = _auto_pair()
    snapshots = (anna, anna_meyer, bella, bella_schmidt)
    review_id = suggestion_id_for(anna.entry_id, anna_meyer.entry_id)
    return snapshots, review_id


def make_auto_only_corpus_with_distractor() -> tuple[EntitySnapshot, ...]:
    """AUTO pair (Bella family) + co-active distractor (Carla family)."""
    bella, bella_schmidt = _auto_pair()
    carla_meyer = _snapshot(
        "Carla Meyer", chapters=(8, 9, 10), neighbor_ids=frozenset({uuid4(), uuid4()})
    )
    carla_meier = _snapshot(
        "Carla Meier", chapters=(9, 10, 11), neighbor_ids=frozenset({uuid4(), uuid4()})
    )
    return (bella, bella_schmidt, carla_meyer, carla_meier)


def review_candidate_for(snapshots: tuple[EntitySnapshot, ...]) -> PairCandidate:
    """The PairCandidate the analysis service must submit for the REVIEW pair.

    The Anna family is the REVIEW pair by construction; identity and name
    order mirror ``ResolutionAnalysisService._to_suggestion`` (entry_a is
    the min id, names follow).
    """
    anna, anna_meyer = (s for s in snapshots if s.name.startswith("Anna"))
    entry_a = min(anna.entry_id, anna_meyer.entry_id)
    entry_b = max(anna.entry_id, anna_meyer.entry_id)
    names = {anna.entry_id: anna.name, anna_meyer.entry_id: anna_meyer.name}
    return PairCandidate(
        pair_key=suggestion_id_for(anna.entry_id, anna_meyer.entry_id),
        entity_type=anna.entity_type,
        name_a=names[entry_a],
        name_b=names[entry_b],
    )


def make_analysis_service(
    snapshots: tuple[EntitySnapshot, ...],
    adjudicator: UncertainBandAdjudicatorProtocol | FakeAdjudicator | None = None,
) -> ResolutionAnalysisService:
    """Real analysis service over fake builder/cache, optional adjudicator."""
    from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare_core.kb.resolution.scoring import ResolutionEngine

    from ._router_helpers import FakeBuilder, FakeCacheBackend

    return ResolutionAnalysisService(
        builder=cast("SnapshotBuilderProtocol", FakeBuilder(snapshots)),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(cast("SessionCacheProtocol", FakeCacheBackend())),
        adjudicator=cast("UncertainBandAdjudicatorProtocol | None", adjudicator),
    )


__all__ = [
    "FakeAdjudicator",
    "make_analysis_service",
    "make_auto_only_corpus_with_distractor",
    "make_review_and_auto_corpus",
    "noop_limiter",
    "review_candidate_for",
    "stub_adjudicator",
    "suggestion_id_for",
]
