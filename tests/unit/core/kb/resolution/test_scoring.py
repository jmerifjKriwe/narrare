"""Tests for the KB resolution scoring engine (ADR-085).

Core pins are taken verbatim from the Task 4 brief / spec §4 worked
examples (duplicate Anna case 0.895 AUTO_ELIGIBLE, distractor co-existence
veto ≤ 0.40 SUPPRESSED, gap-5 case 0.245 SUPPRESSED, name-only ceiling
0.40); supplemental tests pin the veto cap under corroborations, band
boundaries, candidate pairing rules, id ordering, the five-signal tuple,
and the ``Final`` calibration constants.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance
from narrare_core.kb.resolution.scoring import (
    AUTO_THRESHOLD,
    NAME_ONLY_CEILING,
    REVIEW_THRESHOLD,
    VETO_CAP,
    W_ATTRIBUTES,
    W_EMBEDDING,
    W_NAME,
    W_NEIGHBORHOOD,
    W_TEMPORAL,
    ResolutionEngine,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

engine = ResolutionEngine()

# Identical embeddings -> cosine 1.0 >= EMBEDDING_COS -> S5 = +1.0.
SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)


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
    entry_id: UUID | None = None,
    name: str = "Anna Meyer",
    entity_type: str = "character",
    metadata: Mapping[str, object] | None = None,
    provenance: EntryProvenance | None = None,
    neighbor_ids: frozenset[UUID] | None = None,
    embedding: Sequence[float] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=entry_id if entry_id is not None else uuid4(),
        name=name,
        entity_type=entity_type,
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


# --- §4 worked-example pins (brief step 1, verbatim) ------------------------------


def test_duplicate_anna_case_auto_eligible():
    # S1=0.7 -> 0.245, S2=+1 -> 0.30, S3=+1 -> 0.20, S4=+1 -> 0.10, S5=+1 -> 0.05
    neighbors_a, neighbors_b = make_neighbors(shared=2, only_a=1, only_b=1)
    anna_ch1_3 = make_snapshot(
        name="Anna",
        metadata={"age (2017)": 24},
        provenance=make_provenance(1, 3),
        neighbor_ids=neighbors_a,
        embedding=SAME_EMBEDDING,
    )
    anna_meyer_ch4_plus = make_snapshot(
        name="Anna Meyer",
        metadata={"age (2018)": 25},
        provenance=make_provenance(4, 6),
        neighbor_ids=neighbors_b,
        embedding=SAME_EMBEDDING,
    )
    score = engine.score_pair(anna_ch1_3, anna_meyer_ch4_plus)
    assert score.confidence == pytest.approx(0.895)
    assert score.band == "AUTO_ELIGIBLE"


def test_distractor_coexistence_suppressed():
    # Spec §4: "Anna Meyer" (ch 8-10) vs "Anna Meier" (ch 9-12, co-active),
    # disjoint neighborhoods both >= 2, S3 without shared families.
    neighbors_a, neighbors_b = make_neighbors(shared=0, only_a=2, only_b=2)
    anna_meyer = make_snapshot(
        name="Anna Meyer",
        provenance=make_provenance(8, 10),
        neighbor_ids=neighbors_a,
        embedding=SAME_EMBEDDING,
    )
    anna_meier_ch9 = make_snapshot(
        name="Anna Meier",
        provenance=make_provenance(9, 12),
        neighbor_ids=neighbors_b,
        embedding=SAME_EMBEDDING,
    )
    score = engine.score_pair(anna_meyer, anna_meier_ch9)
    assert score.vetoes == ("temporal",)
    assert score.confidence <= 0.40
    assert score.band == "SUPPRESSED"


def test_anna_vs_meier_gap_suppressed():
    # S1=0.7, S2=0 (gap 5), S3=0, S4=-0.5, S5=+1 -> 0.245
    neighbors_a, neighbors_b = make_neighbors(shared=0, only_a=2, only_b=2)
    anna_ch1_3 = make_snapshot(
        name="Anna",
        provenance=make_provenance(1, 3),
        neighbor_ids=neighbors_a,
        embedding=SAME_EMBEDDING,
    )
    anna_meier_ch9 = make_snapshot(
        name="Anna Meier",
        provenance=make_provenance(8, 12),
        neighbor_ids=neighbors_b,
        embedding=SAME_EMBEDDING,
    )
    score = engine.score_pair(anna_ch1_3, anna_meier_ch9)
    assert score.confidence == pytest.approx(0.245)
    assert score.band == "SUPPRESSED"


def test_name_only_ceiling():
    # stronger case: S1=1.0 exact, S2/S3/S4=0, S5=1.0 -> raw 0.40
    # -> ceiling applies -> conf min(0.40,0.55)=0.40 -> SUPPRESSED
    exact_a = make_snapshot(name="Anna Meyer", embedding=SAME_EMBEDDING)
    exact_b_unknown_rest = make_snapshot(name="Anna Meyer", embedding=SAME_EMBEDDING)
    score = engine.score_pair(exact_a, exact_b_unknown_rest)
    assert score.confidence == pytest.approx(0.40)
    assert score.band == "SUPPRESSED"


# --- Override semantics ------------------------------------------------------------


def test_veto_caps_confidence_despite_corroborations():
    # raw = 0.35 (exact) + 0.30 (double extraction) - 0.20 (gender veto)
    #      + 0.10 (neighbors) + 0.05 (embedding) = 0.60 -> veto caps at 0.40.
    neighbors_a, neighbors_b = make_neighbors(shared=2, only_a=1, only_b=1)
    a = make_snapshot(
        name="Anna Meyer",
        metadata={"gender": "female"},
        provenance=make_provenance(1, 5),
        neighbor_ids=neighbors_a,
        embedding=SAME_EMBEDDING,
    )
    b = make_snapshot(
        name="Anna Meyer",
        metadata={"gender": "male"},
        provenance=make_provenance(3, 7),
        neighbor_ids=neighbors_b,
        embedding=SAME_EMBEDDING,
    )
    score = engine.score_pair(a, b)
    assert score.vetoes == ("attributes",)
    assert score.confidence == pytest.approx(VETO_CAP)
    assert score.band == "SUPPRESSED"


def test_review_band_above_threshold():
    # S1=0.7 -> 0.245, S2=+1 -> 0.30, rest unknown -> 0.545 with exactly one
    # corroboration (no ceiling, below AUTO threshold).
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(4, 6))
    score = engine.score_pair(a, b)
    assert score.confidence == pytest.approx(0.545)
    assert score.band == "REVIEW"
    assert score.vetoes == ()


# --- PairScore shape ---------------------------------------------------------------


def test_score_pair_orders_ids_min_max():
    id_a = uuid4()
    id_b = uuid4()
    low, high = (id_a, id_b) if id_a < id_b else (id_b, id_a)
    a = make_snapshot(entry_id=id_a, name="Anna Meyer")
    b = make_snapshot(entry_id=id_b, name="Anna Meyer")
    score = engine.score_pair(a, b)
    assert score.entry_a_id == low
    assert score.entry_b_id == high
    # Argument order must not matter.
    swapped = engine.score_pair(b, a)
    assert (swapped.entry_a_id, swapped.entry_b_id) == (low, high)


def test_signals_tuple_carries_all_five_results():
    a = make_snapshot(name="Anna", provenance=make_provenance(1, 3))
    b = make_snapshot(name="Anna Meyer", provenance=make_provenance(4, 6))
    score = engine.score_pair(a, b)
    assert tuple(signal.signal for signal in score.signals) == (
        "name_tier",
        "temporal",
        "attributes",
        "neighborhood",
        "embedding",
    )
    assert score.signals[0].value == pytest.approx(0.7)
    assert score.signals[1].value == pytest.approx(1.0)


def test_calibration_constants_match_spec():
    assert W_NAME == 0.35
    assert W_TEMPORAL == 0.30
    assert W_ATTRIBUTES == 0.20
    assert W_NEIGHBORHOOD == 0.10
    assert W_EMBEDDING == 0.05
    weight_sum = W_NAME + W_TEMPORAL + W_ATTRIBUTES + W_NEIGHBORHOOD + W_EMBEDDING
    assert weight_sum == pytest.approx(1.0)
    assert AUTO_THRESHOLD == 0.85
    assert REVIEW_THRESHOLD == 0.45
    assert VETO_CAP == 0.40
    assert NAME_ONLY_CEILING == 0.55


# --- find_candidates ----------------------------------------------------------------


def test_find_candidates_pairs_each_same_type_pair_once():
    snap1 = make_snapshot(name="Anna Meyer")
    snap2 = make_snapshot(name="Anna Meyer")
    snap3 = make_snapshot(name="Anna Meyer")
    pairs = engine.find_candidates((snap1, snap2, snap3))
    assert len(pairs) == 3
    seen = {frozenset((a.entry_id, b.entry_id)) for a, b in pairs}
    assert seen == {
        frozenset((snap1.entry_id, snap2.entry_id)),
        frozenset((snap2.entry_id, snap3.entry_id)),
        frozenset((snap1.entry_id, snap3.entry_id)),
    }


def test_find_candidates_excludes_type_mismatch():
    character = make_snapshot(name="Anna Meyer", entity_type="character")
    location = make_snapshot(name="Anna Meyer", entity_type="location")
    assert engine.find_candidates((character, location)) == ()


def test_find_candidates_excludes_none_tier():
    a = make_snapshot(name="Anna Meyer")
    b = make_snapshot(name="Brunhilde Schmidt")
    assert engine.find_candidates((a, b)) == ()


def test_find_candidates_includes_fuzzy_tier():
    a = make_snapshot(name="Anna Meyer")
    b = make_snapshot(name="Anna Meier")  # FUZZY 0.4 > NONE
    pairs = engine.find_candidates((a, b))
    assert len(pairs) == 1


def test_find_candidates_excludes_self_pairs():
    shared_id = uuid4()
    a = make_snapshot(entry_id=shared_id, name="Anna Meyer")
    b = make_snapshot(entry_id=shared_id, name="Anna Meyer")
    assert engine.find_candidates((a, b)) == ()


def test_find_candidates_orders_pair_ids_min_max():
    id_a = uuid4()
    id_b = uuid4()
    first = make_snapshot(entry_id=id_a, name="Anna Meyer")
    second = make_snapshot(entry_id=id_b, name="Anna Meyer")
    low, high = (first, second) if id_a < id_b else (second, first)
    assert engine.find_candidates((first, second)) == ((low, high),)
