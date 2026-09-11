"""Detection scoring: injected errors vs check-capability reports (Task 12).

Matching rule — citation-proximity. An injected error counts as DETECTED
(TP) by a capability iff one of the capability's report items
(``report_items.flatten_record``) plausibly locates it:

1. **Chapter citation.** Chapter-pinned shapes (CAP-CHK-05 flagged
   lines) must reference the error's chapter: the item's ``chapter_ref``
   (a run chapter id) must resolve via ``chapter_map`` (run chapter id →
   corpus stem such as ``"ch-12"``) to the error's ``chapter`` stem. An
   item pinned to a different chapter — or pinned to an id the map
   cannot resolve — NEVER matches (fail-closed: no proximity without
   resolution). Novel-scoped shapes (CHK-01 consistency issues, CHK-02
   canon conflicts, CHK-04 temporal issues, drift verdicts) report over
   ALL chapters of the run's single novel; their chapter half is
   satisfied for every error.
2. **Topic overlap.** The item's normalized token set
   (``normalize_text`` — the shared German-aware normalizer: casefold,
   non-alphanumeric runs → single spaces) must contain at least
   ``TOPIC_OVERLAP_THRESHOLD`` of the error's ground-truth topic
   tokens. The topic is derived from the error's ``ground_truth_ref``
   reference row:
   - ``F*``/``PF*``/``OF*`` (entity fact): owning entity name + aliases
     + fact predicate + fact value tokens;
   - ``R*`` (relation): subject + predicate + object tokens;
   - ``E*`` (event): name + participant + location tokens.
   Interval bounds (``PartialDate``) contribute NO tokens: dates are
   structured data, and a report paraphrasing ``August 2021`` as
   ``Sommer 2021`` must still match via the prose tokens. An id-valued
   token (``pl_tuerkenstrasse``) keeps its underscore-free normalized
   form. An unknown ``ground_truth_ref`` is registry/reference drift →
   ``ValueError`` (hard error, never silent).

FP / FN / clean-run baseline (spec §5). The clean run's same-capability
report is the FP baseline, applied BEFORE claiming: an item whose
normalized fingerprint also occurs in the clean report is a pre-existing
honest finding — it exists without the injection, so it claims NO error
and counts NEITHER tp NOR fp. A variant item matching no error whose
fingerprint is new relative to the baseline is a FALSE POSITIVE. An
injected error no item claims is a FALSE NEGATIVE.

Assignment. Items scan the errors in registry order; the first error
passing both halves claims the item, and each error is claimed at most
once per capability (deterministic first-match). Documented trade-off:
same-topic errors (e.g. L06/X07 both referencing OF010) are
distinguished by report items, not by assignment cleverness — a single
item cannot evidence both.

Matrix. One cell per (capability, injected error class); aggregation
conventions (including the class-agnostic fp repetition) are documented
on ``detection_records.DetectionScore``. The top-level ``false_negatives``
list carries each error matched by NO capability once; per-capability
misses are visible in the matrix ``fn`` column. Pure and deterministic:
no clocks, no randomness (plan Global Constraints).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.scoring.detection_records import (
    DetectionReport,
    DetectionScore,
    FalsePositive,
    MatchedError,
    MissedError,
)
from benchmark.scoring.normalize import normalize_text
from benchmark.scoring.report_items import DetectionItem, flatten_record

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import ErrorSpec, Reference

TOPIC_OVERLAP_THRESHOLD: Final[float] = 0.5
"""Fraction of the error's ground-truth topic tokens an item must share.

0.5 rejects topic-unrelated findings (typical accidental overlap is one
generic token) while accepting German paraphrase that names at least
half the topic (entity AND value, or two of entity/value/predicate).
Exact-half comparisons are IEEE-754 exact (``n / 2n == 0.5``).
"""


def score_detection(
    errors: tuple[ErrorSpec, ...],
    reference: Reference,
    variant_reports: Mapping[str, object],
    clean_reports: Mapping[str, object],
    chapter_map: Mapping[str, str],
) -> DetectionReport:
    """Score one variant run's check reports against the error registry.

    ``variant_reports``/``clean_reports`` map capability id → parsed
    record (one per capability per run); ``chapter_map`` maps the run's
    chapter ids to corpus stems. Protocol-invalid records (T10 riders)
    raise via ``flatten_record``.
    """
    topics = {error.id: _topic_tokens(error.ground_truth_ref, reference) for error in errors}
    clean_fingerprints = {
        capability: {item.fingerprint for item in flatten_record(record)}
        for capability, record in clean_reports.items()
    }
    true_positives: list[MatchedError] = []
    false_positives: list[FalsePositive] = []
    matched_by: dict[str, set[str]] = {}
    for capability in sorted(variant_reports):
        items = flatten_record(variant_reports[capability])
        matched = _claim_items(
            capability,
            items,
            errors,
            topics,
            chapter_map,
            clean_fingerprints.get(capability, set()),
            true_positives,
            false_positives,
        )
        matched_by[capability] = matched
    return DetectionReport(
        matrix=_matrix(errors, matched_by, false_positives),
        true_positives=tuple(true_positives),
        false_negatives=tuple(
            MissedError(error_id=error.id, error_class=error.error_class)
            for error in errors
            if not any(error.id in matched for matched in matched_by.values())
        ),
        false_positives=tuple(false_positives),
    )


def _claim_items(
    capability: str,
    items: tuple[DetectionItem, ...],
    errors: tuple[ErrorSpec, ...],
    topics: dict[str, frozenset[str]],
    chapter_map: Mapping[str, str],
    baseline: set[str],
    true_positives: list[MatchedError],
    false_positives: list[FalsePositive],
) -> set[str]:
    """First-match assignment; appends tp/fp rows, returns claimed error ids."""
    matched: set[str] = set()
    for item in items:
        if item.fingerprint in baseline:
            continue
        error = _first_match(item, errors, matched, topics, chapter_map)
        if error is None:
            false_positives.append(
                FalsePositive(
                    capability=capability, item_index=item.index, fingerprint=item.fingerprint
                )
            )
        else:
            matched.add(error.id)
            true_positives.append(
                MatchedError(
                    error_id=error.id,
                    error_class=error.error_class,
                    capability=capability,
                    item_index=item.index,
                )
            )
    return matched


def _first_match(
    item: DetectionItem,
    errors: tuple[ErrorSpec, ...],
    matched: set[str],
    topics: dict[str, frozenset[str]],
    chapter_map: Mapping[str, str],
) -> ErrorSpec | None:
    """First registry-order error the item plausibly locates (else None)."""
    tokens = frozenset(normalize_text(item.evidence).split())
    for error in errors:
        if error.id in matched or not _chapter_ok(item, error, chapter_map):
            continue
        topic = topics[error.id]
        if len(tokens & topic) / len(topic) >= TOPIC_OVERLAP_THRESHOLD:
            return error
    return None


def _chapter_ok(item: DetectionItem, error: ErrorSpec, chapter_map: Mapping[str, str]) -> bool:
    """Novel-scoped items pass; pinned items must resolve to the error's stem."""
    if item.chapter_ref is None:
        return True
    return chapter_map.get(item.chapter_ref) == error.chapter


def _topic_tokens(ref_id: str, reference: Reference) -> frozenset[str]:
    """Ground-truth topic tokens for one reference id (module docstring rules)."""
    for entity in reference.persons + reference.places + reference.objects:
        for fact in entity.facts:
            if fact.id == ref_id:
                return _tokens(entity.name, *entity.aliases, fact.predicate, fact.value)
    for relation in reference.relations:
        if relation.id == ref_id:
            return _tokens(relation.subject, relation.predicate, relation.object)
    for event in reference.events:
        if event.id == ref_id:
            return _tokens(event.name, *event.participants, event.location)
    msg = f"detection scoring: ground_truth_ref {ref_id!r} not found in reference"
    raise ValueError(msg)


def _tokens(*parts: str) -> frozenset[str]:
    return frozenset(normalize_text(" ".join(parts)).split())


def _matrix(
    errors: tuple[ErrorSpec, ...],
    matched_by: dict[str, set[str]],
    false_positives: list[FalsePositive],
) -> tuple[DetectionScore, ...]:
    """One (capability, class) cell per capability with a report."""
    classes = sorted({error.error_class for error in errors})
    rows: list[DetectionScore] = []
    for capability in sorted(matched_by):
        capability_fp = sum(1 for row in false_positives if row.capability == capability)
        for error_class in classes:
            class_errors = [error for error in errors if error.error_class == error_class]
            tp = sum(1 for error in class_errors if error.id in matched_by[capability])
            expected = len(class_errors)
            precision = tp / (tp + capability_fp) if tp + capability_fp else None
            recall = tp / expected if expected else None
            f1 = _f1(precision, recall)
            rows.append(
                DetectionScore(
                    capability=capability,
                    error_class=error_class,
                    expected=expected,
                    tp=tp,
                    fp=capability_fp,
                    fn=expected - tp,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                )
            )
    return tuple(rows)


def _f1(precision: float | None, recall: float | None) -> float | None:
    """``2PR/(P+R)``; ``None`` when a component is undefined, ``0.0`` at P+R=0."""
    if precision is None or recall is None:
        return None
    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
