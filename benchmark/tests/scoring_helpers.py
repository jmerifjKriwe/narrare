"""Fixture builders for the build-quality scorer tests (Task 11).

Synthetic reference (``benchmark.corpus_views`` shapes) vs synthetic KB
records (``benchmark.drivers.out_records`` shapes) — plain helpers, no
fixtures, no network. Split from the test module per RULE-04
(predecessor pattern: ``out_direction_helpers.py``). Also hosts the
shared single-fact scoring helper used by both scorer test modules.
"""

from __future__ import annotations

from benchmark.corpus_views import (
    Entity,
    Fact,
    PartialDate,
    Reference,
    Relation,
)
from benchmark.drivers.out_records import (
    EntityDetailRecord,
    EntrySummary,
    KbEntryDetail,
    RelationshipDetail,
)
from benchmark.scoring import FactOutcome, score_build_quality

NOVEL_ID = "novel-1"


# ---------------------------------------------------------------------------
# Reference builders
# ---------------------------------------------------------------------------


def d(year: int, month: int | None = None) -> PartialDate:
    """Partial date shorthand."""
    return PartialDate(year=year, month=month)


def ref_fact(
    fact_id: str,
    predicate: str,
    value: str,
    *,
    valid_from: PartialDate | None = None,
    valid_to: PartialDate | None = None,
) -> Fact:
    return Fact(
        id=fact_id,
        predicate=predicate,
        value=value,
        valid_from=valid_from,
        valid_to=valid_to,
        source_chapters=(1,),
    )


def ref_entity(
    entity_id: str,
    name: str,
    *,
    aliases: tuple[str, ...] = (),
    facts: tuple[Fact, ...] = (),
) -> Entity:
    return Entity(id=entity_id, name=name, aliases=aliases, facts=facts)


def ref_relation(rel_id: str, subject: str, predicate: str, target: str) -> Relation:
    return Relation(
        id=rel_id,
        subject=subject,
        predicate=predicate,
        object=target,
        valid_from=None,
        valid_to=None,
        source_chapters=(1,),
    )


def make_reference(
    persons: tuple[Entity, ...] = (),
    places: tuple[Entity, ...] = (),
    objects: tuple[Entity, ...] = (),
    relations: tuple[Relation, ...] = (),
) -> Reference:
    """Reference view with empty events (event scoring is out of Task-11 scope)."""
    return Reference(
        persons=persons,
        places=places,
        objects=objects,
        relations=relations,
        events=(),
    )


# ---------------------------------------------------------------------------
# KB-record builders (EntrySummary / EntityDetailRecord / RelationshipDetail)
# ---------------------------------------------------------------------------


def summary(
    entry_id: str,
    name: str,
    *,
    slug: str | None = None,
    entity_type: str = "character",
) -> EntrySummary:
    return EntrySummary(
        id=entry_id,
        name=name,
        entity_type=entity_type,
        slug=slug if slug is not None else name.lower().replace(" ", "-"),
        status="approved",
        review_status="approved",
    )


def detail(
    entry_id: str,
    *,
    name: str,
    slug: str | None = None,
    entity_type: str = "character",
    metadata: dict[str, object] | None = None,
    body: str | None = None,
    relationships: tuple[RelationshipDetail, ...] = (),
) -> EntityDetailRecord:
    return EntityDetailRecord(
        entry=KbEntryDetail(
            id=entry_id,
            novel_id=NOVEL_ID,
            entity_type=entity_type,
            name=name,
            slug=slug if slug is not None else name.lower().replace(" ", "-"),
            status="approved",
            tags=None,
            metadata=metadata,
            body=body,
            template_version=None,
            source="extraction",
            review_status="approved",
            embeddings_dirty=False,
        ),
        relationships=relationships,
        inverse_of=None,
        inverse_rel_type=None,
    )


def edge(
    edge_id: str,
    rel_type: str,
    source_id: str,
    target_id: str,
    *,
    source_name: str | None = None,
    target_name: str | None = None,
) -> RelationshipDetail:
    return RelationshipDetail(
        id=edge_id,
        rel_type=rel_type,
        source_id=source_id,
        target_id=target_id,
        label=None,
        direction="directed",
        source_name=source_name,
        target_name=target_name,
        metadata=None,
    )


def score_single_fact(
    metadata: dict[str, object] | None,
    body: str | None,
    *,
    valid_from: PartialDate | None = None,
    valid_to: PartialDate | None = None,
    value: str = "24",
) -> FactOutcome:
    """Score one single-fact entity against one single-entry KB detail."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F001",
                        "age_stated",
                        value,
                        valid_from=valid_from,
                        valid_to=valid_to,
                    ),
                ),
            ),
        ),
    )
    entries = (summary("e1", "Anna Meyer"),)
    details = (detail("e1", name="Anna Meyer", metadata=metadata, body=body),)
    return score_build_quality(reference, entries, details).facts[0]
