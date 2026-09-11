"""Typed outputs of the detection scorer (plan Task 12).

Every row is mechanically traceable: true positives carry the registry
error id (``L*``/``X*``) plus the capability and the report-item index
that claimed it; false positives carry the capability and item index
plus the normalized evidence fingerprint that identifies the finding;
false negatives carry the error ids no report located.

Aggregate conventions: one matrix cell per (capability, injected error
class). ``expected`` is the number of injected errors of that class;
``tp`` counts the class errors the capability's report located;
``fn = expected - tp`` (the capability's class detection rate =
``recall``). ``fp`` counts the capability's unmatched new-to-variant
findings — a false finding matched NO injected error by construction,
so class attribution is undefined and the capability's TOTAL fp is
repeated on every class cell (documented limitation, not per-class
noise). ``precision`` is ``None`` when ``tp + fp == 0`` (nothing was
claimed — undefined, not zero); ``f1`` is ``None`` when a component is
undefined, else ``2PR/(P+R)`` with ``f1 = 0.0`` when ``P + R == 0``.
All records are frozen with tuple sequences (``score_records``
precedent).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchedError:
    """A true positive: one report item plausibly located one error."""

    error_id: str
    error_class: str
    capability: str
    item_index: str


@dataclass(frozen=True)
class MissedError:
    """A false negative: an injected error no report item located."""

    error_id: str
    error_class: str


@dataclass(frozen=True)
class FalsePositive:
    """An unmatched new-to-variant finding (not in the clean-run baseline)."""

    capability: str
    item_index: str
    fingerprint: str


@dataclass(frozen=True)
class DetectionScore:
    """One (capability, error class) matrix cell with P/R/F1."""

    capability: str
    error_class: str
    expected: int
    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None


@dataclass(frozen=True)
class DetectionReport:
    """Detection quality of one variant run: matrix + itemized evidence."""

    matrix: tuple[DetectionScore, ...]
    true_positives: tuple[MatchedError, ...]
    false_negatives: tuple[MissedError, ...]
    false_positives: tuple[FalsePositive, ...]
