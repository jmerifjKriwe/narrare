"""Scoring assembly: driven answers → the three scorers (plan Tasks 11-13).

``score_run`` extracts the scoring surfaces from the run's capability
answers and invokes the REAL scorers:

- build quality (Task 11): CAP-OUT-01's ``EntryBrowseRecord`` supplies
  the KB listing, CAP-OUT-03's ``EntityDetailRecord`` the detail surface
  (entry + relationships). Records are consumed ONLY from OK answers —
  an errored/skipped fetch means "no evidence", never a fabricated one;
- detection (Task 12): every OK check-direction answer's parsed record
  becomes a variant report. The clean-run FP baseline is OPTIONAL input:
  v1 supplies NONE (the clean run is a separate full run) —
  ``clean_reports={}`` means NO baseline subtraction, and the run's
  artifacts say so (``RunInputs.fp_baseline=False``);
- retrieval (Task 13): the detail records plus CAP-OUT-07's timeline
  read (absent → ``None``, the documented downgrade).

Clean variant: NO injected errors — detection is an EMPTY report. The
clean run's check reports are the FP-baseline MATERIAL for later
comparison, not detection evidence; scoring an empty registry would
misreport every honest finding as FP (the matrix contract documents
``expected=0`` cells as "nothing scored"). Pure and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.capabilities import capability
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.out_records import (
    EntityDetailRecord,
    EntryBrowseRecord,
    TimelineReadRecord,
)
from benchmark.scoring.build_quality import score_build_quality
from benchmark.scoring.detection import score_detection
from benchmark.scoring.detection_records import DetectionReport
from benchmark.scoring.retrieval import score_retrieval

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from benchmark.artifacts_records import CapabilityAnswer
    from benchmark.corpus_loader import Corpus
    from benchmark.corpus_views import ErrorSpec, Reference
    from benchmark.scoring.retrieval_records import RetrievalScore
    from benchmark.scoring.score_records import BuildQualityScore

__all__ = ["RunScores", "score_run"]


@dataclass(frozen=True)
class RunScores:
    """The three scorer outputs of one run, in artifacts order."""

    build_quality: BuildQualityScore
    detection: DetectionReport
    retrieval: RetrievalScore


def score_run(
    corpus: Corpus,
    variant: str,
    answers: Sequence[CapabilityAnswer],
    chapter_map: Mapping[str, str],
) -> RunScores:
    """Score one finished run from its answers (module docstring rules)."""
    reference = corpus.reference()
    browse = _ok_parsed(answers, "CAP-OUT-01", EntryBrowseRecord)
    details = _ok_detail(answers)
    timeline = _ok_parsed(answers, "CAP-OUT-07", TimelineReadRecord)
    return RunScores(
        build_quality=score_build_quality(
            reference, () if browse is None else browse.entries, details
        ),
        detection=_detection(corpus, variant, answers, reference, chapter_map),
        retrieval=score_retrieval(reference, details, timeline),
    )


def _detection(
    corpus: Corpus,
    variant: str,
    answers: Sequence[CapabilityAnswer],
    reference: Reference,
    chapter_map: Mapping[str, str],
) -> DetectionReport:
    """Variant detection; empty report for clean runs (module docstring)."""
    errors: tuple[ErrorSpec, ...] = (
        corpus.errors(variant) if variant in corpus.variant_names else ()
    )
    if not errors:
        return DetectionReport(matrix=(), true_positives=(), false_negatives=(), false_positives=())
    variant_reports: dict[str, object] = {
        answer.cap_id: answer.parsed
        for answer in answers
        if answer.status is CapabilityStatus.OK
        and answer.parsed is not None
        and capability(answer.cap_id).direction == "check"
    }
    return score_detection(errors, reference, variant_reports, {}, chapter_map)


def _ok_detail(answers: Sequence[CapabilityAnswer]) -> tuple[EntityDetailRecord, ...]:
    """CAP-OUT-03's detail record, only from an OK answer."""
    detail = _ok_parsed(answers, "CAP-OUT-03", EntityDetailRecord)
    return () if detail is None else (detail,)


def _ok_parsed[T: object](
    answers: Sequence[CapabilityAnswer], cap_id: str, record_type: type[T]
) -> T | None:
    """The parsed payload of an OK answer, checked against ``record_type``.

    An absent answer, a non-OK answer, or an unexpected payload shape
    yields ``None`` — "no evidence", never a fabricated record.
    """
    for answer in answers:
        if answer.cap_id == cap_id:
            if answer.status is CapabilityStatus.OK and isinstance(answer.parsed, record_type):
                return answer.parsed
            return None
    return None
    return None
