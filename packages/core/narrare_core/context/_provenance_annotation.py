"""Provenance annotation brackets for KBContextEnvelope renderers.

Pure functions that decide whether a KB entry's provenance is "uncertain
enough" to warrant an inline annotation, build the bracket wire format,
and report which :class:`ProvenanceField` literals were rendered (so
renderers can adjust RULE-22 accounting).

Annotation predicate (annotate when NOT suppressed AND any trigger fires):

* triggers —
    1. ``confidence < 0.7``
    2. ``review_status == "pending"``
    3. freshness stale (``wiki_status == "stale"`` /
       ``freshness == "stale"``)
    4. ``source != "manual"`` AND ``confidence < 0.9``
* suppress — ``source == "manual"`` |
  (``confidence >= 0.9`` AND ``review_status == "endorsed"``)

Suppression takes precedence over triggers. Suppressed entries receive no
annotation regardless of confidence, review, or freshness state.

.. note::

   Trigger #4 (``source != "manual"`` AND ``confidence < 0.9``) ensures
   every non-manual entry below 0.9 confidence is visibly marked so the
   LLM can distinguish auto-extracted / imported / wiki-generated facts
   from curated manual facts. It subsumes trigger #1 within the non-manual
   domain (which the suppression guard already enforces); both are kept
   explicit so the predicate maps 1:1 to its specification. Because manual
   sources are always suppressed, the original source-unaware boundary
   ``0.70 → not annotated`` is refined to be source-aware: at 0.70 with a
   non-manual source trigger #4 fires and the entry *is* annotated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.context._kb_envelope import ProvenanceField

logger = structlog.get_logger(__name__)

#: Below this confidence an entry is "low confidence" (annotated).
_LOW_CONFIDENCE_THRESHOLD: float = 0.7
#: At/above this confidence AND endorsed, an entry is "trusted" (suppressed).
_HIGH_CONFIDENCE_THRESHOLD: float = 0.9

_SOURCE_LABELS: dict[str, str] = {
    "auto_extraction": "auto-extracted",
    "imported": "imported",
    "wiki_generated": "wiki-generated",
    "manual": "manual",
}


def humanise_source(source: str) -> str:
    """Return a human-readable label for a KB entry source.

    Known sources are mapped to readable labels (``auto_extraction`` →
    ``auto-extracted``); unknown sources pass through unchanged.
    """
    return _SOURCE_LABELS.get(source, source)


@dataclass(frozen=True, slots=True)
class ProvenanceAnnotation:
    """Result of evaluating one entry's provenance for annotation.

    Attributes:
        bracket: The ``[...]`` wire-format bracket to append to the
            entry's header line, or ``None`` when the entry is suppressed
            or no trigger fires (no annotation).
        rendered_fields: Which :class:`ProvenanceField` literals the
            bracket actually rendered. Empty when ``bracket is None``.
            Consumed by renderers to move fields from ``omitted_fields``
            to ``preserved_fields`` (RULE-22).
    """

    bracket: str | None
    rendered_fields: frozenset[ProvenanceField]


def _is_suppressed(*, source: str, confidence: float, review_status: str) -> bool:
    """Return True when the entry must NOT be annotated."""
    return source == "manual" or (
        confidence >= _HIGH_CONFIDENCE_THRESHOLD and review_status == "endorsed"
    )


def compute_provenance_annotation(
    *,
    source: str,
    confidence: float,
    review_status: str,
    freshness: str,
) -> ProvenanceAnnotation:
    """Compute the provenance annotation bracket for one KB entry.

    Args:
        source: The entry's provenance source (``manual``,
            ``auto_extraction``, ``imported``, ``wiki_generated``, ...).
        confidence: Extraction confidence in ``[0.0, 1.0]``.
        review_status: ``pending`` | ``endorsed`` | ``rejected``.
        freshness: Wiki/freshness status — ``fresh`` | ``stale`` |
            ``pending`` | ``""`` (unknown). Only ``stale`` triggers
            annotation.

    Returns:
        A :class:`ProvenanceAnnotation` with the bracket (or ``None``)
        and the set of provenance fields the bracket rendered.
    """
    if _is_suppressed(source=source, confidence=confidence, review_status=review_status):
        return ProvenanceAnnotation(bracket=None, rendered_fields=frozenset())

    low_confidence = confidence < _LOW_CONFIDENCE_THRESHOLD
    pending = review_status == "pending"
    rejected = review_status == "rejected"
    stale = freshness == "stale"
    # Trigger #4: non-manual AND confidence < 0.9. The suppression guard
    # above already guaranteed source != "manual", so only the confidence
    # half remains. It subsumes trigger #1 within the non-manual domain.
    sub_high_confidence = confidence < _HIGH_CONFIDENCE_THRESHOLD

    if not (low_confidence or pending or stale or sub_high_confidence):
        return ProvenanceAnnotation(bracket=None, rendered_fields=frozenset())

    # --- Build bracket fields (fixed order) ---
    # source is always non-manual here (manual is suppressed), so it is
    # always shown. confidence is shown whenever source is shown.
    fields: list[str] = [humanise_source(source)]
    fields.append(f"confidence: {confidence:.2f}")
    rendered: set[ProvenanceField] = {"provenance"}

    if pending:
        fields.append("pending review")
        rendered.add("review_state")
    elif rejected:
        # rejected does not trigger annotation on its own, but when the
        # entry is annotated for another reason we surface it and log.
        fields.append("review rejected")
        rendered.add("review_state")
        logger.info(
            "kb_entry_review_rejected_annotated",
            source=source,
            confidence=confidence,
            freshness=freshness,
        )

    if stale:
        fields.append("stale")
        rendered.add("freshness")

    return ProvenanceAnnotation(
        bracket=f"[{', '.join(fields)}]",
        rendered_fields=frozenset(rendered),
    )


def merge_rendered_fields(
    annotations: list[ProvenanceAnnotation],
) -> frozenset[ProvenanceField]:
    """Union of ``rendered_fields`` across a rendered batch (RULE-22).

    A field is preserved at batch level when ANY entry in the batch
    rendered it. Fields not rendered for any entry stay omitted.
    """
    merged: set[ProvenanceField] = set()
    for ann in annotations:
        merged.update(ann.rendered_fields)
    return frozenset(merged)
