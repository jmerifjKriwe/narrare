"""Tests for KB resolution name-tier classification (ADR-085, signal S1).

Core tier pins are taken verbatim from the Task 2 brief (spec §4 S1);
supplemental tests pin normalization semantics, argument-order symmetry,
and the ``Final`` calibration constants.
"""

from narrare_core.kb.resolution.name_tiers import (
    EXACT,
    FUZZY,
    FUZZY_RATIO,
    NONE,
    SUBSET,
    classify_name_tier,
    normalize_name,
)

# --- Core brief pins (spec §4 S1) -------------------------------------------


def test_exact_after_normalization():
    assert classify_name_tier("Anna Meyer", "anna  meyer!") == (1.0, "EXACT")


def test_subset_anna_in_anna_meyer():
    assert classify_name_tier("Anna", "Anna Meyer") == (0.7, "SUBSET")


def test_fuzzy_meier_vs_meyer():
    assert classify_name_tier("Anna Meier", "Anna Meyer") == (0.4, "FUZZY")


def test_none_disjoint_names():
    assert classify_name_tier("Peter Meyer", "Lisa Brandt") == (0.0, "NONE")


def test_subset_requires_shared_first_token():
    # Decision (brief §Step 1): "Meyer" is a subset token-wise of
    # "Anna Meyer", but the first tokens differ ("meyer" vs "anna"), so the
    # SUBSET tier does not apply.  The actual difflib ratio for
    # ("meyer", "anna meyer") is 0.667 < 0.87 (the brief estimated ~0.727 —
    # same verdict), so fuzzy does not apply either.  Pinned intent:
    # no shared first token -> not SUBSET -> (0.0, "NONE").
    assert classify_name_tier("Meyer", "Anna Meyer") == (0.0, "NONE")


# --- Normalization semantics -------------------------------------------------


def test_normalize_name_folds_case_diacritics_and_punctuation():
    assert normalize_name("Ánnà  MÉYER!") == "anna meyer"


def test_normalize_name_collapses_separator_runs_and_strips():
    assert normalize_name("  Jean--Luc   Picard ") == "jean luc picard"


def test_normalize_name_folds_diacritics_to_ascii_base():
    assert normalize_name("André Meyer") == "andre meyer"


# --- Tier semantics beyond the brief pins ------------------------------------


def test_subset_is_symmetric_in_argument_order():
    # "Anna" ⊂ "Anna Meyer" must hold regardless of argument order.
    assert classify_name_tier("Anna Meyer", "Anna") == (0.7, "SUBSET")


def test_subset_denied_when_first_tokens_differ_on_mutual_token_overlap():
    # Token sets are equal (mutual subset), but first tokens differ
    # ("meyer" vs "anna") -> not SUBSET; ratio("meyer anna", "anna meyer")
    # = 0.5 < 0.87 -> not FUZZY -> NONE.
    assert classify_name_tier("Meyer Anna", "Anna Meyer") == (0.0, "NONE")


def test_exact_via_diacritic_fold():
    assert classify_name_tier("André Meyer", "andre meyer") == (1.0, "EXACT")


def test_empty_names_hit_equality_path_as_exact():
    # Garbage-in edge: both names normalize to "" and compare equal, so the
    # literal EXACT path fires.  Real callers feed snapshot names; this pin
    # only documents that the empty edge never raises.
    assert classify_name_tier("", "") == (1.0, "EXACT")


# --- Calibration constants (spec §4: module-level Final) --------------------


def test_tier_constants_match_spec_values():
    assert EXACT == 1.0
    assert SUBSET == 0.7
    assert FUZZY == 0.4
    assert NONE == 0.0
    assert FUZZY_RATIO == 0.87
