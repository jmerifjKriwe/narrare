"""Unit tests for the detection scorer (Task 12).

Synthetic check records + registry-shaped errors (fixtures in
``detection_helpers.py``): citation-proximity matching (chapter pin +
topic-overlap threshold), per-shape itemization rules, clean-run FP
baseline subtraction, first-match determinism, XOR/duplicate protocol
validation (T10 riders), matrix precision/recall/F1 math, and id
traceability (error ids + report-item indices).
"""

from __future__ import annotations

import pytest

from benchmark.scoring.detection import score_detection
from benchmark.tests.detection_helpers import (
    E900,
    L01,
    L03,
    L06,
    X07,
    author_drift_record,
    author_drift_result,
    canon_conflict_record,
    consistency_finding,
    consistency_issue,
    consistency_record,
    detection_reference,
    synthetic_reference,
    temporal_record,
    temporal_record_no_issues,
    voice_check_record,
)

CHAPTER_MAP = {"chapter-1": "ch-01", "chapter-9": "ch-09"}


# ---------------------------------------------------------------------------
# TP path: citation-proximity (topic overlap, novel-scoped shapes)
# ---------------------------------------------------------------------------


def test_consistency_issue_matching_error_counts_tp() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-01": consistency_issue(
                0,
                ("Anna Meyer",),
                "Im Rueckblick ist Anna 36 Jahre alt",
                "age_stated 36 widerspricht 35",
            )
        },
        clean_reports={},
        chapter_map=CHAPTER_MAP,
    )
    assert len(report.true_positives) == 1
    matched = report.true_positives[0]
    assert matched.error_id == "L01"
    assert matched.error_class == "attribute_value"
    assert matched.capability == "CAP-CHK-01"
    assert matched.item_index == "issues[0]"
    assert report.false_negatives == ()
    assert report.false_positives == ()


def test_german_normalization_folds_case_and_punctuation() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-01": consistency_issue(
                0, ("ANNA   MEYER",), "Ueber die Rueckblick-Angabe", "36 statt 35!"
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [row.error_id for row in report.true_positives] == ["L01"]


def test_item_without_topic_overlap_is_fp_and_error_is_fn() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-01": consistency_issue(
                0, ("Hafen",), "Der Hafen liegt im Sueden", "Orientierung unklar"
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert report.true_positives == ()
    assert [row.error_id for row in report.false_negatives] == ["L01"]
    assert len(report.false_positives) == 1
    assert report.false_positives[0].item_index == "issues[0]"
    assert report.false_positives[0].fingerprint.startswith("hafen der hafen")


# ---------------------------------------------------------------------------
# Threshold edges (deterministic token-overlap >= 0.5 of the topic)
# ---------------------------------------------------------------------------


def test_overlap_exactly_at_threshold_matches() -> None:
    report = score_detection(
        errors=(E900,),
        reference=synthetic_reference(),
        variant_reports={
            # topic = {alpha, beta, gamma, delta, w, x}; 3/6 == 0.5 -> match
            "CAP-CHK-01": consistency_issue(0, (), "Alpha, Beta und Gamma blieben", "")
        },
        clean_reports={},
        chapter_map={},
    )
    assert [row.error_id for row in report.true_positives] == ["E900"]


def test_overlap_below_threshold_does_not_match() -> None:
    report = score_detection(
        errors=(E900,),
        reference=synthetic_reference(),
        variant_reports={
            # 2/6 < 0.5 -> no match -> FP
            "CAP-CHK-01": consistency_issue(0, (), "Alpha und Beta blieben", "")
        },
        clean_reports={},
        chapter_map={},
    )
    assert report.true_positives == ()
    assert len(report.false_positives) == 1


# ---------------------------------------------------------------------------
# Chapter citation half (chapter-pinned shapes; novel-scoped shapes exempt)
# ---------------------------------------------------------------------------


def test_chapter_pinned_item_requires_resolved_same_chapter() -> None:
    item = voice_check_record(
        "chapter-1",
        ("Anna Meyer", "Anna war sechsunddreissig und nicht 35", "age_stated 35"),
    )
    matched = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-05": item},
        clean_reports={},
        chapter_map={"chapter-1": "ch-12"},
    )
    assert [row.error_id for row in matched.true_positives] == ["L01"]

    wrong_chapter = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-05": item},
        clean_reports={},
        chapter_map={"chapter-1": "ch-08"},
    )
    assert wrong_chapter.true_positives == ()
    assert [row.error_id for row in wrong_chapter.false_negatives] == ["L01"]
    assert len(wrong_chapter.false_positives) == 1

    unresolvable = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-05": item},
        clean_reports={},
        chapter_map={"chapter-x": "ch-12"},
    )
    assert unresolvable.true_positives == ()


def test_novel_scoped_shape_ignores_chapter_half() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-01": consistency_issue(
                0, ("Anna Meyer",), "Altersangabe 36", "age_stated 36 statt 35"
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [row.error_id for row in report.true_positives] == ["L01"]


# ---------------------------------------------------------------------------
# Clean-run FP baseline (spec §5): pre-existing findings claim nothing
# ---------------------------------------------------------------------------


def test_clean_baseline_item_is_subtracted_before_claiming() -> None:
    pre_existing = consistency_issue(
        0, ("Anna Meyer",), "Im Rueckblick ist Anna 36 Jahre alt", "age_stated 36 statt 35"
    )
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-01": pre_existing},
        clean_reports={"CAP-CHK-01": pre_existing},
        chapter_map={},
    )
    assert report.true_positives == ()
    assert report.false_positives == ()
    assert [row.error_id for row in report.false_negatives] == ["L01"]


def test_new_unmatched_item_is_fp_but_baseline_item_is_not() -> None:
    new_noise = temporal_record("date_conflict", "Umzug nach Bremen im Mai datiert", "pruefen")
    baseline = consistency_issue(0, ("Hafen",), "Der Hafen liegt im Sueden", "unclar")
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-01": baseline, "CAP-CHK-04": new_noise},
        clean_reports={"CAP-CHK-01": baseline},
        chapter_map={},
    )
    assert [(fp.capability, fp.item_index) for fp in report.false_positives] == [
        ("CAP-CHK-04", "issues[0]")
    ]


# ---------------------------------------------------------------------------
# Per-shape itemization rules (canon conflicts, temporal, flagged lines, drift)
# ---------------------------------------------------------------------------


def test_canon_conflict_matches_event_topic_at_threshold() -> None:
    report = score_detection(
        errors=(L03,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-02": canon_conflict_record(
                "Umzug nach Muenchen",
                "Von diesem Juli an wohnten sie in Muenchen",
                "Anna und Peter zogen im August 2021 zur Tuerkenstrasse 41",
                "Juli widerspricht August 2021",
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [(row.error_id, row.item_index) for row in report.true_positives] == [
        ("L03", "conflicts[0]")
    ]


def test_temporal_issue_matches_event_topic_at_threshold() -> None:
    report = score_detection(
        errors=(L03,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-04": temporal_record(
                "date_conflict",
                "Umzug von Anna und Peter zur Tuerkenstrasse 41 im Juli 2021 datiert",
                "Kapiteltext pruefen",
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [(row.error_id, row.item_index) for row in report.true_positives] == [
        ("L03", "issues[0]")
    ]


def test_author_drift_result_item_can_match_error() -> None:
    report = score_detection(
        errors=(X07,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-07": author_drift_record(
                result=author_drift_result(
                    "Widerspruch zu located_at pl_tuerkenstrasse: der Zeichentisch"
                ),
                no_profile=None,
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [(row.error_id, row.item_index) for row in report.true_positives] == [
        ("X07", "result.drift")
    ]


# ---------------------------------------------------------------------------
# First-match determinism (same-topic errors, registry order)
# ---------------------------------------------------------------------------


def test_same_topic_errors_first_registry_order_claims_item() -> None:
    report = score_detection(
        errors=(L06, X07),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-01": consistency_issue(
                3,
                (),
                "Der Zeichentisch steht laut Text bei Thomas",
                "located_at pl_tuerkenstrasse widerspricht Textstelle",
            )
        },
        clean_reports={},
        chapter_map={},
    )
    assert [(row.error_id, row.item_index) for row in report.true_positives] == [
        ("L06", "issues[3]")
    ]
    assert [row.error_id for row in report.false_negatives] == ["X07"]


# ---------------------------------------------------------------------------
# Matrix math: precision/recall/F1 per class x capability
# ---------------------------------------------------------------------------


def test_precision_none_when_capability_reports_nothing() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={"CAP-CHK-04": temporal_record_no_issues()},
        clean_reports={},
        chapter_map={},
    )
    assert len(report.matrix) == 1
    cell = report.matrix[0]
    assert (cell.capability, cell.error_class) == ("CAP-CHK-04", "attribute_value")
    assert (cell.expected, cell.tp, cell.fp, cell.fn) == (1, 0, 0, 1)
    assert cell.precision is None
    assert cell.recall == 0.0
    assert cell.f1 is None


def test_f1_math_with_partial_detection_and_noise() -> None:
    report = score_detection(
        errors=(L01, L03),
        reference=detection_reference(),
        variant_reports={
            # L01-locating finding + one unrelated finding -> tp=1, fp=1
            "CAP-CHK-01": consistency_record(
                consistency_finding(
                    0, ("Anna Meyer",), "Altersangabe 36", "age_stated 36 statt 35"
                ),
                consistency_finding(
                    1, ("Hafen",), "Der Hafen liegt im Sueden", "Orientierung unklar"
                ),
            ),
            "CAP-CHK-02": canon_conflict_record(
                "Hafen", "Der Hafen lag suedlich", "Kein Bezug", "Thema verfehlt"
            ),
        },
        clean_reports={},
        chapter_map={},
    )
    cells = {(cell.capability, cell.error_class): cell for cell in report.matrix}
    chk01_attr = cells[("CAP-CHK-01", "attribute_value")]
    assert (chk01_attr.tp, chk01_attr.fp, chk01_attr.fn) == (1, 1, 0)
    assert chk01_attr.precision == pytest.approx(0.5)
    assert chk01_attr.recall == pytest.approx(1.0)
    assert chk01_attr.f1 == pytest.approx(2 * 0.5 * 1.0 / 1.5)

    chk01_date = cells[("CAP-CHK-01", "date_mismatch")]
    assert (chk01_date.tp, chk01_date.fn) == (0, 1)
    assert chk01_date.precision == pytest.approx(0.0)
    assert chk01_date.f1 == pytest.approx(0.0)

    # canon-conflict noise (class-agnostic FP) appears on every CHK-02 cell
    chk02_attr = cells[("CAP-CHK-02", "attribute_value")]
    assert chk02_attr.fp == 1
    assert chk02_attr.precision == pytest.approx(0.0)
    assert chk02_attr.recall == pytest.approx(0.0)

    # L03 matched by NO capability -> the one global false negative
    assert [row.error_id for row in report.false_negatives] == ["L03"]
    assert [row.error_id for row in report.true_positives] == ["L01"]


def test_matrix_cells_are_sorted_by_capability_and_class() -> None:
    report = score_detection(
        errors=(L03, L01),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-04": temporal_record_no_issues(),
            "CAP-CHK-01": consistency_issue(0, (), "unrelated", "unrelated"),
        },
        clean_reports={},
        chapter_map={},
    )
    keys = [(cell.capability, cell.error_class) for cell in report.matrix]
    assert keys == [
        ("CAP-CHK-01", "attribute_value"),
        ("CAP-CHK-01", "date_mismatch"),
        ("CAP-CHK-04", "attribute_value"),
        ("CAP-CHK-04", "date_mismatch"),
    ]
