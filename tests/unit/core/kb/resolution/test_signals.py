"""Tests for KB resolution detection signals S2-S5 (ADR-085).

Core pins are taken verbatim from the Task 3 brief / spec §4 signal table;
supplemental tests pin edge semantics (gap boundary, order consistency,
containment overlap, age birth-year inference, Jaccard boundary, embedding
degeneracy) and the ``Final`` calibration constants.
"""

import math
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import narrare_core.kb.resolution as resolution_package
from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance
from narrare_core.kb.resolution.signals import (
    EMBEDDING_COS,
    HANDOFF_MAX_GAP,
    NEIGHBOR_JACCARD,
    attributes_signal,
    embedding_signal,
    neighborhood_signal,
    temporal_signal,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# --- Helpers -------------------------------------------------------------------


def make_provenance(first: int, last: int) -> EntryProvenance:
    return EntryProvenance(
        chapters=tuple(range(first, last + 1)),
        first_seen_chapter=first,
        last_seen_chapter=last,
        name_variants=(),
    )


def make_snapshot(
    *,
    name: str = "Anna Meyer",
    metadata: Mapping[str, object] | None = None,
    provenance: EntryProvenance | None = None,
    neighbor_ids: frozenset[UUID] | None = None,
    embedding: Sequence[float] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata=dict(metadata or {}),
        provenance=provenance,
        neighbor_ids=neighbor_ids if neighbor_ids is not None else frozenset(),
        embedding=embedding,
    )


def unique_ids(count: int) -> frozenset[UUID]:
    return frozenset(uuid4() for _ in range(count))


def make_neighbors(
    shared: int, only_a: int, only_b: int
) -> tuple[frozenset[UUID], frozenset[UUID]]:
    """Build neighbor sets with a deterministic Jaccard denominator.

    jaccard = shared / (shared + only_a + only_b).
    """
    common = unique_ids(shared)
    return common | unique_ids(only_a), common | unique_ids(only_b)


# --- S2 temporal: brief core pins -------------------------------------------------


def test_temporal_handoff_short_variant_earlier_is_plus_one():
    # Brief pin: "Anna" (ch 1-3) vs "Anna Meyer" (ch 4-6), s1 = 0.7.
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(4, 6))
    result = temporal_signal(a, b, 0.7)
    assert result.value == 1.0
    assert result.veto is False
    assert "handoff" in result.detail


def test_temporal_coexistence_overlap_with_fuzzy_tier_is_veto():
    # Brief pin: "Anna Meyer" (ch 4-12) vs "Anna Meier" (ch 9-10), s1 = 0.4.
    a = make_snapshot(name="Anna Meyer", provenance=make_provenance(4, 12))
    b = make_snapshot(name="Anna Meier", provenance=make_provenance(9, 10))
    result = temporal_signal(a, b, 0.4)
    assert result.value == -1.0
    assert result.veto is True
    assert "overlap" in result.detail


def test_temporal_exact_names_overlap_is_plus_one_without_veto():
    # Brief pin: s1 == 1.0 with overlap is double extraction, never a veto.
    a = make_snapshot(name="Anna Meyer", provenance=make_provenance(1, 5))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(3, 8))
    result = temporal_signal(a, b, 1.0)
    assert result.value == 1.0
    assert result.veto is False


def test_temporal_unknown_provenance_is_zero():
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer")  # provenance None
    result = temporal_signal(a, b, 0.7)
    assert result.value == 0.0
    assert result.veto is False


# --- S2 temporal: edge semantics --------------------------------------------------


def test_temporal_handoff_gap_boundary_two_is_plus_one():
    # Gap = later first_seen - earlier last_seen = 5 - 3 = 2 <= HANDOFF_MAX_GAP.
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(5, 7))
    result = temporal_signal(a, b, 0.7)
    assert result.value == 1.0
    assert result.veto is False


def test_temporal_contained_range_counts_as_overlap_veto():
    # Interleaving/containment (ch 3-5 inside ch 1-10) is an overlap shape.
    a = make_snapshot(name="Anna Meyer", provenance=make_provenance(1, 10))
    b = make_snapshot(name="Anna Meier", provenance=make_provenance(3, 5))
    result = temporal_signal(a, b, 0.4)
    assert result.value == -1.0
    assert result.veto is True


def test_temporal_incomplete_provenance_is_zero():
    # Provenance present but first_seen_chapter unknown -> S2 stays neutral.
    incomplete = EntryProvenance(
        chapters=(1, 2), first_seen_chapter=None, last_seen_chapter=2, name_variants=()
    )
    a = make_snapshot(name="Anna", provenance=incomplete)
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(4, 6))
    result = temporal_signal(a, b, 0.7)
    assert result.value == 0.0
    assert result.veto is False


def test_temporal_gap_above_maximum_is_zero():
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(9, 12))
    result = temporal_signal(a, b, 0.7)
    assert result.value == 0.0
    assert result.veto is False
    assert "gap" in result.detail


def test_temporal_longer_name_earlier_is_zero():
    # Spec §4 S2: handoff requires order consistency — the shorter-name
    # variant must appear earlier ("Anna" grows into "Anna Meyer", not the
    # reverse).  Disjoint ranges, gap 1, but the long name comes first.
    a = make_snapshot(name="Anna Meyer", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna", provenance=make_provenance(4, 6))
    result = temporal_signal(a, b, 0.7)
    assert result.value == 0.0
    assert result.veto is False
    assert "longer" in result.detail


# --- S3 attributes: brief core pins ------------------------------------------------


def test_attributes_age_progression_across_years_is_plus_one():
    # Brief pin: 24@2017 vs 27@2020 -> consistent progression.
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"age (2020)": 27})
    result = attributes_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False
    assert "age" in result.detail


def test_attributes_gender_contradiction_is_veto():
    a = make_snapshot(metadata={"gender": "female"})
    b = make_snapshot(metadata={"gender": "male"})
    result = attributes_signal(a, b)
    assert result.value == -1.0
    assert result.veto is True
    assert "contradiction" in result.detail


def test_attributes_same_year_different_age_is_veto():
    # Brief pin: equal years must match exactly.
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"age (2017)": 25})
    result = attributes_signal(a, b)
    assert result.value == -1.0
    assert result.veto is True


# --- S3 attributes: edge semantics --------------------------------------------------


def test_attributes_age_same_implied_birth_year_is_plus_one():
    # 2017-24 == 2021-28 == 1993 -> consistent birth year.
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"age (2021)": 28})
    result = attributes_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_attributes_age_one_year_drift_across_years_is_plus_one():
    # Different years, values differing by <= 1 are "progression".
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"age (2020)": 25})
    result = attributes_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_attributes_age_different_implied_birth_years_is_veto():
    # 2017-24 = 1993 vs 2020-26 = 1994 and |24-26| = 2 > 1 -> contradiction.
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"age (2020)": 26})
    result = attributes_signal(a, b)
    assert result.value == -1.0
    assert result.veto is True


def test_attributes_gender_normalized_equality_is_plus_one():
    a = make_snapshot(metadata={"gender": "Female"})
    b = make_snapshot(metadata={"gender": "female"})
    result = attributes_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_attributes_profession_match_is_plus_one():
    a = make_snapshot(metadata={"profession": "teacher"})
    b = make_snapshot(metadata={"profession": "Teacher"})
    result = attributes_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_attributes_residence_conflict_is_veto():
    # Spec §4 worked distractor example names "residence conflict" as a
    # contradiction source (same semantic key, incompatible values).
    a = make_snapshot(metadata={"residence": "Hamburg"})
    b = make_snapshot(metadata={"residence": "Munich"})
    result = attributes_signal(a, b)
    assert result.value == -1.0
    assert result.veto is True


def test_attributes_no_shared_families_is_zero():
    a = make_snapshot(metadata={"age (2017)": 24})
    b = make_snapshot(metadata={"profession": "teacher"})
    result = attributes_signal(a, b)
    assert result.value == 0.0
    assert result.veto is False


def test_attributes_age_without_year_anchor_is_zero():
    # No year anchor on either side -> no comparable (year, value) evidence;
    # differing bare ages are NOT a contradiction (unknown validity).
    a = make_snapshot(metadata={"age": 24})
    b = make_snapshot(metadata={"age": 30})
    result = attributes_signal(a, b)
    assert result.value == 0.0
    assert result.veto is False


def test_attributes_contradiction_outweighs_compatible_family():
    a = make_snapshot(metadata={"gender": "female", "profession": "teacher"})
    b = make_snapshot(metadata={"gender": "male", "profession": "teacher"})
    result = attributes_signal(a, b)
    assert result.value == -1.0
    assert result.veto is True
    assert "gender" in result.detail


# --- S4 neighborhood ----------------------------------------------------------------


def test_neighborhood_jaccard_at_threshold_is_plus_one():
    # 3 shared / 10 union = 0.3 == NEIGHBOR_JACCARD (inclusive boundary).
    neighbors_a, neighbors_b = make_neighbors(shared=3, only_a=4, only_b=3)
    a = make_snapshot(neighbor_ids=neighbors_a)
    b = make_snapshot(neighbor_ids=neighbors_b)
    result = neighborhood_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_neighborhood_disjoint_both_at_least_two_is_minus_half():
    neighbors_a, neighbors_b = make_neighbors(shared=0, only_a=3, only_b=3)
    a = make_snapshot(neighbor_ids=neighbors_a)
    b = make_snapshot(neighbor_ids=neighbors_b)
    result = neighborhood_signal(a, b)
    assert result.value == -0.5
    assert result.veto is False  # weak corroborator, never a veto


def test_neighborhood_partial_overlap_below_threshold_is_zero():
    # 1 shared / 10 union = 0.1 < 0.3, but not disjoint -> neutral.
    neighbors_a, neighbors_b = make_neighbors(shared=1, only_a=5, only_b=4)
    a = make_snapshot(neighbor_ids=neighbors_a)
    b = make_snapshot(neighbor_ids=neighbors_b)
    result = neighborhood_signal(a, b)
    assert result.value == 0.0


def test_neighborhood_single_neighbor_sides_are_zero():
    # Disjoint but sparse (both < 2 relationships) -> no penalty.
    neighbors_a, neighbors_b = make_neighbors(shared=0, only_a=1, only_b=1)
    a = make_snapshot(neighbor_ids=neighbors_a)
    b = make_snapshot(neighbor_ids=neighbors_b)
    result = neighborhood_signal(a, b)
    assert result.value == 0.0


def test_neighborhood_no_relationships_is_zero():
    a = make_snapshot()
    b = make_snapshot()
    result = neighborhood_signal(a, b)
    assert result.value == 0.0


# --- S5 embedding --------------------------------------------------------------------


def test_embedding_cosine_above_threshold_is_plus_one():
    # Unit vectors (1, 0) and (0.9, sqrt(1-0.81)) have cosine 0.9 >= 0.82.
    a = make_snapshot(embedding=(1.0, 0.0))
    b = make_snapshot(embedding=(0.9, math.sqrt(1.0 - 0.9 * 0.9)))
    result = embedding_signal(a, b)
    assert result.value == 1.0
    assert result.veto is False


def test_embedding_cosine_below_threshold_is_zero():
    # Cosine 0.5 < 0.82 -> 0.0 (never negative by design).
    a = make_snapshot(embedding=(1.0, 0.0))
    b = make_snapshot(embedding=(0.5, math.sqrt(0.75)))
    result = embedding_signal(a, b)
    assert result.value == 0.0
    assert result.veto is False


def test_embedding_missing_on_one_side_is_zero():
    a = make_snapshot(embedding=(1.0, 0.0))
    b = make_snapshot()  # embedding None
    result = embedding_signal(a, b)
    assert result.value == 0.0


def test_embedding_length_mismatch_is_zero():
    a = make_snapshot(embedding=(1.0, 0.0))
    b = make_snapshot(embedding=(1.0, 0.0, 0.0))
    result = embedding_signal(a, b)
    assert result.value == 0.0


def test_embedding_zero_vector_is_zero():
    a = make_snapshot(embedding=(0.0, 0.0))
    b = make_snapshot(embedding=(1.0, 0.0))
    result = embedding_signal(a, b)
    assert result.value == 0.0


# --- Signal names, calibration constants, package wiring ---------------------------


def test_signal_names_match_spec():
    a = make_snapshot()
    b = make_snapshot()
    assert temporal_signal(a, b, 0.0).signal == "temporal"
    assert attributes_signal(a, b).signal == "attributes"
    assert neighborhood_signal(a, b).signal == "neighborhood"
    assert embedding_signal(a, b).signal == "embedding"


def test_signal_constants_match_spec_values():
    assert HANDOFF_MAX_GAP == 2
    assert NEIGHBOR_JACCARD == 0.3
    assert EMBEDDING_COS == 0.82


def test_package_reexports_signal_functions():
    assert resolution_package.temporal_signal is temporal_signal
    assert resolution_package.attributes_signal is attributes_signal
    assert resolution_package.neighborhood_signal is neighborhood_signal
    assert resolution_package.embedding_signal is embedding_signal
