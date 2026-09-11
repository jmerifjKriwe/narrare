"""KB scoring: build quality (Task 11), detection (Task 12), retrieval (Task 13),
entity resolution (CAP-IN-10, ADR-085 P6).

Public surfaces: ``score_build_quality`` plus ``score_retrieval`` with their
typed records, and the resolution scorer (``score_resolution``) with its
binding/group derivation. Matching-rule contracts live in the matcher module
docstrings (``entity_match`` / ``fact_match`` / ``relation_match`` /
``detection`` / ``retrieval`` / ``resolution_match``); aggregation conventions
on ``score_records.BuildQualityScore``, ``retrieval_records.RetrievalScore``,
and ``resolution_match.ResolutionScore``.
"""

from __future__ import annotations

from benchmark.scoring.build_quality import score_build_quality
from benchmark.scoring.resolution_match import (
    ClaimEntry,
    ResolutionScore,
    claim_groups,
    pair_key,
    score_resolution,
)
from benchmark.scoring.retrieval import score_retrieval
from benchmark.scoring.retrieval_records import (
    AnswerOutcome,
    AnswerStatus,
    CapabilityCoverage,
    QueryKind,
    RetrievalQuery,
    RetrievalScore,
    Surface,
)
from benchmark.scoring.score_records import (
    BuildQualityScore,
    EntityOutcome,
    EntityStatus,
    FactEvidence,
    FactOutcome,
    FactStatus,
    RelationOutcome,
    RelationStatus,
    SpuriousEntity,
    SpuriousFact,
    SpuriousRelation,
)

__all__ = [
    "AnswerOutcome",
    "AnswerStatus",
    "BuildQualityScore",
    "CapabilityCoverage",
    "ClaimEntry",
    "EntityOutcome",
    "EntityStatus",
    "FactEvidence",
    "FactOutcome",
    "FactStatus",
    "QueryKind",
    "RelationOutcome",
    "RelationStatus",
    "ResolutionScore",
    "RetrievalQuery",
    "RetrievalScore",
    "SpuriousEntity",
    "SpuriousFact",
    "SpuriousRelation",
    "Surface",
    "claim_groups",
    "pair_key",
    "score_build_quality",
    "score_resolution",
    "score_retrieval",
]
