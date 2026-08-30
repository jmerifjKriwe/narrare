"""Protocol-validation tests for the detection scorer (Task 12, T10 riders).

Split from ``test_detection.py`` per RULE-04. Covers the consumer-side
record-shape rules from ``benchmark.scoring.report_items``: the
author-voice-drift XOR rider (``result`` XOR ``no_profile_reason`` with
at-least-one — neither set, or both, is a protocol error, never data),
the graceful no-profile skip as legitimate zero-item data, the
duplicate-result shape assertion, and the unknown-record-shape guard.
"""

from __future__ import annotations

import pytest

from benchmark.drivers.check_records import SeriesVoiceDriftRecord
from benchmark.scoring.detection import score_detection
from benchmark.scoring.report_items import DetectionProtocolError, flatten_record
from benchmark.tests.detection_helpers import (
    L01,
    author_drift_record,
    author_drift_result,
    character_drift_record,
    detection_reference,
)


def test_author_drift_neither_set_is_protocol_error() -> None:
    record = author_drift_record(result=None, no_profile=None)
    with pytest.raises(DetectionProtocolError):
        flatten_record(record)
    with pytest.raises(DetectionProtocolError):
        score_detection(
            errors=(L01,),
            reference=detection_reference(),
            variant_reports={"CAP-CHK-07": record},
            clean_reports={},
            chapter_map={},
        )


def test_series_drift_both_set_is_protocol_error() -> None:
    record = SeriesVoiceDriftRecord(
        series_id="series-1",
        novel_id="novel-1",
        result=author_drift_result("Sprung in der Satzlaenge"),
        no_profile_reason="no_stored_profile",
    )
    with pytest.raises(DetectionProtocolError):
        flatten_record(record)


def test_author_drift_no_profile_is_data_with_zero_items() -> None:
    report = score_detection(
        errors=(L01,),
        reference=detection_reference(),
        variant_reports={
            "CAP-CHK-07": author_drift_record(result=None, no_profile="no_stored_profile")
        },
        clean_reports={},
        chapter_map={},
    )
    assert report.true_positives == ()
    assert report.false_positives == ()
    assert [row.error_id for row in report.false_negatives] == ["L01"]


def test_duplicate_character_results_are_protocol_error() -> None:
    record = character_drift_record(("entry-9", "Anna Meyer", ()), ("entry-9", "Anna Meyer", ()))
    with pytest.raises(DetectionProtocolError):
        flatten_record(record)


def test_unknown_record_shape_is_protocol_error() -> None:
    with pytest.raises(DetectionProtocolError):
        flatten_record(object())
