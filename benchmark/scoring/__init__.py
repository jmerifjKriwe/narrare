"""KB scoring: build quality (Task 11), detection (Task 12), retrieval (Task 13).

Public surfaces: ``score_build_quality`` plus ``score_retrieval`` with their
typed records. Matching-rule contracts live in the matcher module docstrings
(``entity_match`` / ``fact_match`` / ``relation_match`` / ``detection`` /
``retrieval``); aggregation conventions on ``score_records.BuildQualityScore``
and ``retrieval_records.RetrievalScore``.
"""

from __future__ import annotations

from benchmark.scoring.build_quality import score_build_quality
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
    "EntityOutcome",
    "EntityStatus",
    "FactEvidence",
    "FactOutcome",
    "FactStatus",
    "QueryKind",
    "RelationOutcome",
    "RelationStatus",
    "RetrievalQuery",
    "RetrievalScore",
    "SpuriousEntity",
    "SpuriousFact",
    "SpuriousRelation",
    "Surface",
    "score_build_quality",
    "score_retrieval",
]
