"""KB build-quality scoring (plan Task 11).

Public surface: ``score_build_quality`` plus the typed ``BuildQualityScore``
and its itemization records. Matching-rule contracts live in the matcher
module docstrings (``entity_match`` / ``fact_match`` / ``relation_match``);
aggregation conventions on ``score_records.BuildQualityScore``.
"""

from __future__ import annotations

from benchmark.scoring.build_quality import score_build_quality
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
    "BuildQualityScore",
    "EntityOutcome",
    "EntityStatus",
    "FactEvidence",
    "FactOutcome",
    "FactStatus",
    "RelationOutcome",
    "RelationStatus",
    "SpuriousEntity",
    "SpuriousFact",
    "SpuriousRelation",
    "score_build_quality",
]
