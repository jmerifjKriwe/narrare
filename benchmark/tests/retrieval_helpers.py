"""Fixture builders for the retrieval scorer tests (Task 13).

Synthetic reference (``benchmark.corpus_views`` shapes) vs synthetic OUT
driver records (``benchmark.drivers.out_records`` shapes), mirroring the
real corpus reference shapes (interval facts with ``{year, month}``
bounds, directed relations). Plain helpers — no fixtures, no network.
Extends ``scoring_helpers.py`` (entity/fact/relation/detail/edge
builders live there); only retrieval-specific builders are added here.
Split from the test module per RULE-04 (predecessor pattern:
``detection_helpers.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.corpus_views import PartialDate, Reference, Relation
from benchmark.drivers.out_records import (
    CharacterAge,
    EntityDetailRecord,
    RelationshipDetail,
    TimelineEventRef,
    TimelineReadRecord,
)
from benchmark.scoring import score_retrieval
from benchmark.scoring.retrieval_queries import generate_queries
from benchmark.tests.scoring_helpers import (
    d as _d,
)
from benchmark.tests.scoring_helpers import (
    detail,
    make_reference,
    ref_entity,
    ref_fact,
    ref_relation,
)

if TYPE_CHECKING:
    from benchmark.scoring.retrieval_records import RetrievalScore

__all__ = [
    "d",
    "detail",
    "edge_meta",
    "empty_timeline",
    "expected_outcome",
    "generate_queries",
    "ref_relation_interval",
    "reference",
    "retrieve",
]


def d(year: int, month: int | None = None) -> PartialDate:
    """Partial date shorthand (re-exported for test readability)."""
    return _d(year, month)


# ---------------------------------------------------------------------------
# Reference: 4 facts (2 entity_lookup, 2 state_at_time) + 1 relation
# ---------------------------------------------------------------------------


def reference() -> Reference:
    """Five-candidate reference: F001/F0F1 plain facts, F002/F003 interval
    facts, R001 relation — candidate order F001, F002, F003, F0F1, R001."""
    return make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F001", "age_stated", "24"),
                    ref_fact(
                        "F002",
                        "profession",
                        "Projektarchitektin",
                        valid_from=d(2017, 3),
                        valid_to=d(2021, 8),
                    ),
                ),
            ),
            ref_entity(
                "p2",
                "Ben Schulz",
                facts=(
                    ref_fact(
                        "F003",
                        "residence",
                        "Eppendorfer Baum 14",
                        valid_from=d(2015),
                    ),
                ),
            ),
        ),
        objects=(
            ref_entity("ob1", "Café Krume", facts=(ref_fact("OF001", "owner", "Ilse Krume"),)),
        ),
        relations=(ref_relation("R001", "p1", "sibling_of", "p2"),),
    )


def ref_relation_interval(
    rel_id: str,
    subject: str,
    predicate: str,
    target: str,
    *,
    valid_from: PartialDate | None = None,
    valid_to: PartialDate | None = None,
) -> Relation:
    """Relation with interval bounds (rider-b material)."""
    relation = ref_relation(rel_id, subject, predicate, target)
    return Relation(
        id=relation.id,
        subject=relation.subject,
        predicate=relation.predicate,
        object=relation.object,
        valid_from=valid_from,
        valid_to=valid_to,
        source_chapters=relation.source_chapters,
    )


# ---------------------------------------------------------------------------
# KB-record builders
# ---------------------------------------------------------------------------


def edge_meta(
    edge_id: str,
    rel_type: str,
    source_id: str,
    target_id: str,
    metadata: dict[str, object] | None = None,
) -> RelationshipDetail:
    """Relationship edge with optional interval metadata (rider-b plane)."""
    return RelationshipDetail(
        id=edge_id,
        rel_type=rel_type,
        source_id=source_id,
        target_id=target_id,
        label=None,
        direction="directed",
        source_name=None,
        target_name=None,
        metadata=metadata,
    )


def empty_timeline() -> TimelineReadRecord:
    """Driven-but-empty timeline read record (coverage-row material)."""
    event = TimelineEventRef(
        id="ev-1",
        event_name="Einzug",
        event_type="milestone",
        timestamp_raw="2015-04",
        source="extraction",
        confidence=None,
        is_confirmed=True,
        chapter_id="ch-1",
    )
    age = CharacterAge(
        character_name="Anna Meyer",
        character_id="e1",
        birth_date="1992-01",
        birth_date_narrative=None,
        age_available=True,
    )
    return TimelineReadRecord(
        events=(event,),
        single=event,
        ages=(age,),
        characters_with_age=1,
        characters_without_age=0,
    )


# ---------------------------------------------------------------------------
# Scoring shortcuts
# ---------------------------------------------------------------------------


def retrieve(
    details: tuple[EntityDetailRecord, ...],
    timeline: TimelineReadRecord | None = None,
    sample_size: int = 12,
) -> RetrievalScore:
    """Score the module reference against the given detail records."""
    return score_retrieval(
        reference(),
        details,
        timeline,
        sample_size=sample_size,
    )


def expected_outcome(score: RetrievalScore, ref_id: str):
    """The answer outcome for one reference id (queries are few; linear scan)."""
    for outcome in score.outcomes:
        if outcome.ref_id == ref_id:
            return outcome
    raise AssertionError(f"no outcome for {ref_id}")
