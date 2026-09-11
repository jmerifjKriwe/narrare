"""Resolution scorer tests (CAP-IN-10, ADR-085 P6, spec §8).

Synthetic duplicate/distractor scenario (the spec's evidence base):
"Anna" + "Anna Meyer" are one reference claim group (alias "Anna"); the
distractor "Anna Meier" is its OWN reference — any suggested cross pair
is a false positive by construction and fails the binary distractor
gate. Expected pairs derive from reference bindings alone (never from
the system's suggestions), so an unsuggested duplicate hurts recall and
an unexpected suggestion hurts precision.

The wiring tests pin the runner contract: the scored KB fetch happens
AFTER the drivers, so the endorsed merges are already applied and the
deprecated losers are HIDDEN from the listing (ADR-085 §9(c)) — the
expected-pair universe is reconstructed by re-adding the merge losers
(names from the resolution record's suggestion id→name pairs).
Builders live in ``resolution_helpers.py`` (RULE-04 split).
"""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from benchmark.artifacts_json import results_document
from benchmark.artifacts_records import RunInputs
from benchmark.drivers.in_records import MergeResult, ResolutionSuggestion
from benchmark.runner_scoring import RunScores, score_run
from benchmark.scoring.entity_match import match_entities
from benchmark.scoring.resolution_match import (
    ResolutionScore,
    claim_groups,
    pair_key,
    score_resolution,
)
from benchmark.tests.resolution_helpers import (
    ANNA_GROUP_REFS,
    E_ANNA,
    E_ANNA_MEIER,
    E_ANNA_MEYER,
    E_OTHER,
    claim_entry,
    cross_suggestion,
    duplicate_merge,
    duplicate_suggestion,
    post_merge_kb,
    resolution_answer,
    synthetic_corpus,
)
from benchmark.tests.scoring_helpers import ref_entity, summary

if TYPE_CHECKING:
    from benchmark.corpus_views import Entity

# ---------------------------------------------------------------------------
# claim_groups — reference binding (spec §8 derivation)
# ---------------------------------------------------------------------------


def test_name_and_alias_entries_form_one_group() -> None:
    groups = claim_groups(
        ANNA_GROUP_REFS,
        (
            claim_entry(E_ANNA, "Anna"),
            claim_entry(E_ANNA_MEYER, "Anna Meyer"),
            claim_entry(E_ANNA_MEIER, "Anna Meier"),
        ),
    )

    assert frozenset({E_ANNA, E_ANNA_MEYER}) in groups
    assert frozenset({E_ANNA_MEIER}) in groups


def test_normalized_slug_binds_like_a_name() -> None:
    groups = claim_groups(
        (ref("p-anna", "Anna Meyer"),),
        (claim_entry("e-slug", "Anna M.", slug="anna-meyer"),),
    )

    assert groups == (frozenset({"e-slug"}),)


def test_normalization_folds_case_and_punctuation() -> None:
    groups = claim_groups(
        (ref("p-anna", "Anna Meyer"),),
        (claim_entry("e-messy", "ANNA   meyer!"),),
    )

    assert groups == (frozenset({"e-messy"}),)


def test_first_reference_claims_a_colliding_entry() -> None:
    refs = (ref("p-first", "Anna"), ref("p-second", "Anna Meier", aliases=("Anna",)))
    groups = claim_groups(refs, (claim_entry(E_ANNA, "Anna"),))

    assert groups == (frozenset({E_ANNA}), frozenset())


def test_unbound_entries_appear_in_no_group() -> None:
    groups = claim_groups(ANNA_GROUP_REFS, (claim_entry(E_OTHER, "Ben Neumann"),))

    assert groups == (frozenset(), frozenset())


def test_pair_key_is_unordered() -> None:
    assert pair_key("b", "a") == pair_key("a", "b") == ("a", "b")


def test_claim_groups_agree_with_entity_match_bindings() -> None:
    """Cross-reference pin: the duplicated binding rule (normalized
    name/slug vs reference name + alias set) must not drift between
    ``claim_groups`` and ``entity_match`` — every entry ``match_entities``
    claims for a reference sits in the SAME reference's claim group. The
    duplicate "Anna" entry is the DOCUMENTED divergence: spurious under
    build quality's 1:1 claim rule, expected-bound for resolution."""
    refs = (ref("p-anna", "Anna Meyer", aliases=("Anna",)), ref("p-meier", "Anna Meier"))
    names = ((E_ANNA, "Anna"), (E_ANNA_MEYER, "Anna Meyer"), (E_ANNA_MEIER, "Anna Meier"))
    entries = tuple(claim_entry(entry_id, name) for entry_id, name in names)
    summaries = tuple(summary(entry_id, name) for entry_id, name in names)

    matched = match_entities(refs, summaries)
    by_ref = {
        entity.id: group for entity, group in zip(refs, claim_groups(refs, entries), strict=True)
    }

    assert {match.ref.id for match in matched.matches} == {"p-anna", "p-meier"}
    for match in matched.matches:
        assert match.entry.id in by_ref[match.ref.id]
    assert E_ANNA in by_ref["p-anna"]  # the documented divergence
    assert E_OTHER not in by_ref["p-anna"] | by_ref["p-meier"]


# ---------------------------------------------------------------------------
# score_resolution — spec §8 metrics
# ---------------------------------------------------------------------------


def expected_groups_for_corpus() -> tuple[frozenset[str], ...]:
    return claim_groups(
        ANNA_GROUP_REFS,
        (
            claim_entry(E_ANNA, "Anna"),
            claim_entry(E_ANNA_MEYER, "Anna Meyer"),
            claim_entry(E_ANNA_MEIER, "Anna Meier"),
        ),
    )


def test_full_success_precision_recall_and_gate() -> None:
    score = score_resolution(
        expected_groups_for_corpus(),
        (duplicate_suggestion(),),
        (duplicate_merge(),),
    )

    assert score == ResolutionScore(
        precision=1.0,
        recall=1.0,
        auto_band_ok=True,
        distractor_never_suggested=True,
        expected_pair_count=1,
        suggested_count=1,
        endorsed_count=1,
        endorsed_expected_pairs=1,
    )


def test_missing_duplicate_drops_recall_only() -> None:
    score = score_resolution(expected_groups_for_corpus(), (), ())

    assert score.precision == 1.0
    assert score.recall == 0.0
    assert score.auto_band_ok is True
    assert score.distractor_never_suggested is True
    assert score.expected_pair_count == 1
    assert score.suggested_count == 0


def test_cross_pair_suggested_fails_distractor_gate() -> None:
    score = score_resolution(expected_groups_for_corpus(), (cross_suggestion(),), ())

    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.distractor_never_suggested is False


def test_auto_eligible_outside_expected_fails_band_quality() -> None:
    outside = ResolutionSuggestion(
        suggestion_id="s-auto",
        entry_a_id=E_ANNA_MEYER,
        entry_b_id=E_ANNA_MEIER,
        name_a="Anna Meyer",
        name_b="Anna Meier",
        confidence=0.95,
        band="AUTO_ELIGIBLE",
        auto_merge_eligible=True,
    )

    score = score_resolution(expected_groups_for_corpus(), (outside,), ())

    assert score.auto_band_ok is False
    assert score.distractor_never_suggested is False


def test_auto_eligible_inside_expected_keeps_band_quality() -> None:
    score = score_resolution(
        expected_groups_for_corpus(),
        (duplicate_suggestion(band="AUTO_ELIGIBLE", auto_merge_eligible=True),),
        (),
    )

    assert score.auto_band_ok is True


def test_unbound_endpoint_does_not_fire_the_distractor_gate() -> None:
    stray = ResolutionSuggestion(
        suggestion_id="s-stray",
        entry_a_id=E_OTHER,
        entry_b_id=E_ANNA_MEIER,
        name_a="Ben Neumann",
        name_b="Anna Meier",
        confidence=0.6,
        band="REVIEW",
        auto_merge_eligible=False,
    )

    score = score_resolution(expected_groups_for_corpus(), (stray,), ())

    # Only ONE endpoint binds a reference — the pair is a precision miss,
    # not the spec's cross-reference distractor trap.
    assert score.precision == 0.0
    assert score.distractor_never_suggested is True


def test_empty_expected_and_suggested_is_vacuously_perfect() -> None:
    score = score_resolution((), (), ())

    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.auto_band_ok is True
    assert score.distractor_never_suggested is True


def test_endorsed_merge_outside_expected_counts_zero() -> None:
    stray_merge = MergeResult(
        survivor_id=E_ANNA_MEIER,
        loser_id=E_OTHER,
        merged_fact_keys=(),
        repointed_relationships=0,
        skipped_relationships=0,
    )

    score = score_resolution(
        expected_groups_for_corpus(), (duplicate_suggestion(),), (stray_merge,)
    )

    assert score.endorsed_count == 1
    assert score.endorsed_expected_pairs == 0


# ---------------------------------------------------------------------------
# Runner wiring — post-merge scored KB + loser reconstruction
# ---------------------------------------------------------------------------


def test_score_run_derives_expected_pairs_across_the_hidden_loser() -> None:
    scores = score_run(
        synthetic_corpus(),
        "clean",
        (resolution_answer(),),
        {},
        post_merge_kb(),
    )

    resolution = scores.resolution
    assert resolution is not None
    # The deprecated loser is absent from the scored listing, but the
    # merge record + suggestion id→name pairs reconstruct the pair —
    # recall/precision are measured, never vacuous.
    assert resolution.precision == 1.0
    assert resolution.recall == 1.0
    assert resolution.expected_pair_count == 1
    assert resolution.distractor_never_suggested is True


def test_score_run_without_cap_in_10_leaves_resolution_absent() -> None:
    scores = score_run(synthetic_corpus(), "clean", (), {}, post_merge_kb())

    assert scores.resolution is None
    assert isinstance(scores, RunScores)


def test_results_document_carries_the_resolution_section() -> None:
    scores = score_run(
        synthetic_corpus(),
        "clean",
        (resolution_answer(),),
        {},
        post_merge_kb(),
    )
    assert scores.resolution is not None

    document = results_document(
        scores.build_quality, scores.detection, scores.retrieval, scores.resolution
    )

    assert document["resolution"] == {
        "precision": 1.0,
        "recall": 1.0,
        "auto_band_ok": True,
        "distractor_gate": True,
        "expected_pair_count": 1,
        "suggested_count": 1,
    }


def test_results_document_omits_resolution_when_not_driven() -> None:
    scores = score_run(synthetic_corpus(), "clean", (), {}, post_merge_kb())

    document = results_document(
        scores.build_quality, scores.detection, scores.retrieval, scores.resolution
    )

    assert "resolution" not in document


def test_run_inputs_resolution_defaults_absent() -> None:
    resolution_field = next(field for field in fields(RunInputs) if field.name == "resolution")

    assert resolution_field.default is None


@pytest.mark.parametrize(
    ("suggested", "expected_precision", "expected_recall"),
    [
        ((), 1.0, 0.0),
        ((duplicate_suggestion(),), 1.0, 1.0),
        ((cross_suggestion(),), 0.0, 0.0),
    ],
)
def test_metric_matrix(
    suggested: tuple[ResolutionSuggestion, ...],
    expected_precision: float,
    expected_recall: float,
) -> None:
    score = score_resolution(expected_groups_for_corpus(), suggested, ())

    assert score.precision == expected_precision
    assert score.recall == expected_recall


def ref(entity_id: str, name: str, *, aliases: tuple[str, ...] = ()) -> Entity:
    return ref_entity(entity_id, name, aliases=aliases)
