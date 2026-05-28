"""Narrative arc template matching for sentiment analysis.

Extracted from ``sentiment.py`` to comply with RULE-04 (file size limits).
Contains the arc matching logic used by :class:`LexiconSentimentAnalyzer`.

Usage::

    from narrare_core.analysis.sentiment_arcs import (
        score_arc, segment_avg, detect_narrative_arc, SEGMENT_NAMES,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from narrare_core.analysis.types import SentenceSentiment

SEGMENT_NAMES: list[str] = [
    "exposition",
    "rising_action",
    "climax",
    "falling_action",
    "resolution",
]

_MIN_ARCS_SENTENCES: int = 5


class ArcScoreResult(TypedDict):
    """Result of scoring a text against a narrative arc template."""

    confidence: float
    explanation: str


def score_arc(
    actual: list[float],
    expected: list[float],
    explanation: str,
) -> ArcScoreResult:
    """Compute arc confidence from segment valence vs expected pattern.

    Normalises both *actual* and *expected* to ``[0, 1]`` then computes
    ``confidence = 1 - sqrt(MSE)`` where MSE is the mean squared error.

    Args:
        actual: Mean valence per segment (5 values).
        expected: Expected template pattern (5 values).
        explanation: Human-readable description of the arc type.

    Returns:
        An :class:`ArcScoreResult` with *confidence* in ``[0.0, 1.0]``.
    """
    min_a, max_a = min(actual), max(actual)
    if max_a - min_a < 0.001:
        norm_actual = [0.5] * len(actual)
    else:
        norm_actual = [(v - min_a) / (max_a - min_a) for v in actual]

    min_e, max_e = min(expected), max(expected)
    if max_e - min_e < 0.001:
        norm_expected = [0.5] * len(expected)
    else:
        norm_expected = [(v - min_e) / (max_e - min_e) for v in expected]

    mse = sum((a - e) ** 2 for a, e in zip(norm_actual, norm_expected, strict=True)) / len(actual)
    confidence = max(0.0, 1.0 - mse**0.5)

    return ArcScoreResult(confidence=confidence, explanation=explanation)


def segment_avg(
    sentences: list[SentenceSentiment],
    seg_idx: int,
    seg_size: int,
    field: str,
) -> float:
    """Average a VAD field across a segment of sentences.

    Args:
        sentences: All sentence sentiment results.
        seg_idx: 0-based segment index.
        seg_size: Number of sentences per segment.
        field: VAD field name (``"valence"``, ``"arousal"``, ``"dominance"``).

    Returns:
        Mean value of the field for the given segment.
    """
    start = seg_idx * seg_size
    end = min(start + seg_size, len(sentences))
    chunk = sentences[start:end]
    if not chunk:
        return 0.0
    total = sum(getattr(s.vad, field, 0.0) for s in chunk)
    return round(total / len(chunk), 4)


def detect_narrative_arc(
    sentences: list[SentenceSentiment],
) -> dict[str, Any] | None:
    """Match valence progression against known narrative arc templates.

    Divides the sentence list into 5 equal segments, computes mean
    valence per segment, then scores against 5 arc templates (Freytag
    pyramid, man in hole, comedy, tragedy, reversal).

    Args:
        sentences: Per-sentence sentiment results, in order.

    Returns:
        A dict with keys ``arc_type``, ``confidence``, ``segments``,
        and ``explanation``, or ``None`` if no arc matches.
    """
    if len(sentences) < _MIN_ARCS_SENTENCES:
        return None

    n = len(sentences)
    segment_size = max(1, n // 5)
    segments: list[float] = []
    for i in range(0, n, segment_size):
        chunk = sentences[i : i + segment_size]
        if not chunk:
            break
        avg_v = sum(s.vad.valence for s in chunk) / len(chunk)
        segments.append(avg_v)

    # Pad to exactly 5 segments
    while len(segments) < 5:
        segments.append(segments[-1] if segments else 0.0)

    # Test against known arc templates
    arcs: dict[str, ArcScoreResult] = {
        "freytag_pyramid": score_arc(
            segments,
            [0.5, 0.7, 1.0, 0.6, 0.3],
            "Rising action to climax, then falling to resolution.",
        ),
        "man_in_hole": score_arc(
            segments,
            [0.5, 0.3, 0.2, 0.6, 0.9],
            "Valence drops then recovers strongly.",
        ),
        "comedy": score_arc(
            segments,
            [0.2, 0.4, 0.6, 0.8, 1.0],
            "Steadily rising valence from low to high.",
        ),
        "tragedy": score_arc(
            segments,
            [1.0, 0.8, 0.5, 0.3, 0.1],
            "Steadily falling valence from high to low.",
        ),
        "reversal": score_arc(
            segments,
            [0.8, 0.4, 0.2, 0.2, 0.2],
            "Valence drops sharply then stays low.",
        ),
    }

    best_name = max(arcs, key=lambda k: arcs[k]["confidence"])
    best = arcs[best_name]

    if best["confidence"] < 0.1:
        return None

    segment_details: list[dict[str, object]] = [
        {
            "name": SEGMENT_NAMES[i],
            "valence": round(segments[i], 4),
            "arousal": segment_avg(sentences, i, segment_size, "arousal"),
            "dominance": segment_avg(sentences, i, segment_size, "dominance"),
        }
        for i in range(5)
    ]

    return {
        "arc_type": best_name,
        "confidence": round(best["confidence"], 3),
        "segments": segment_details,
        "explanation": best["explanation"],
    }
