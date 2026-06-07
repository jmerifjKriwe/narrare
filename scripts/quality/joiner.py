"""Join adoption, audit, eval, and evidence data into quality metrics.

Merges data from four sources per (category, mode) key and produces
:class:`ModeQualityMetric` instances.

See ADR-041 Decision 3.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adoption.audit_report import AuditReport
    from adoption.scorer import AdoptionReport
    from eval_drift.parser import EvalResultFile

from quality.quality_report import ModeQualityMetric

# ── Gap detection thresholds ──────────────────────────────────────

#: Eval score above this but adoption below ADOPTION_GAP_THRESHOLD → gap.
EVAL_GAP_THRESHOLD = 0.7

#: Adoption score above this but eval below EVAL_GAP_THRESHOLD → gap.
ADOPTION_GAP_THRESHOLD = 0.85


# ── Gap detection ─────────────────────────────────────────────────


def _detect_gap(eval_score: float | None, static_score: float) -> bool:
    """Detect quality-adoption gap between eval and adoption scores.

    A gap exists when:
    - eval is strong (> *EVAL_GAP_THRESHOLD*) but adoption is weak
      (< *ADOPTION_GAP_THRESHOLD*) — good tests, poor adoption.
    - eval is weak (< *EVAL_GAP_THRESHOLD*) but adoption is strong
      (> *ADOPTION_GAP_THRESHOLD*) — good adoption, poor tests.

    Returns ``False`` when ``eval_score`` is None (no eval data to judge).
    """
    if eval_score is None:
        return False
    return (eval_score > EVAL_GAP_THRESHOLD and static_score < ADOPTION_GAP_THRESHOLD) or (
        eval_score < EVAL_GAP_THRESHOLD and static_score > ADOPTION_GAP_THRESHOLD
    )


# ── Eval result matching ──────────────────────────────────────────


def _find_matching_eval(
    eval_results: list[EvalResultFile],
    category: str,
    mode: str,
) -> EvalResultFile | None:
    """Find an :class:`EvalResultFile` matching *category*/*mode*.

    Tries (in order):
    1. Exact match on mode name (``source == mode``).
    2. ``category-mode`` pattern (e.g. ``writing-new_chapter``).
    3. ``category/mode`` or ``category_mode`` pattern.

    Returns ``None`` when no eval result matches.
    """
    # Direct match on mode name.
    for er in eval_results:
        if er.source == mode:
            return er

    # category-mode pattern (common eval filename convention).
    pattern = f"{category}-{mode}"
    for er in eval_results:
        if er.source == pattern:
            return er

    # category/mode or category_mode pattern.
    pattern_slash = f"{category}/{mode}"
    pattern_underscore = f"{category}_{mode}"
    for er in eval_results:
        if er.source in (pattern_slash, pattern_underscore):
            return er

    return None


# ── Evidence parsing ──────────────────────────────────────────────


def parse_evidence_lines(evidence_path: Path | str) -> list[dict[str, Any]]:
    """Parse ``.evidence/invocations.jsonl`` into a list of dicts.

    Each JSON line is expected to have at least:
    - ``feature_id``: str (format ``"category/mode"`` or ``"writing_intent"``)
    - ``mode``: str | None
    - ``intent``: str
    - ``audit_state``: str

    Returns an empty list if the file does not exist or an I/O error occurs.
    Malformed JSON lines are silently skipped.
    """
    path = Path(evidence_path)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


# ── Join logic ────────────────────────────────────────────────────


def join_quality_metrics(
    adoption: AdoptionReport | None,
    audit: AuditReport | None,
    eval_results: list[EvalResultFile],
    evidence_records: list[dict[str, Any]],
) -> list[ModeQualityMetric]:
    """Join adoption, audit, eval, and evidence data per ``(category, mode)``.

    Parameters
    ----------
    adoption:
        Computed :class:`AdoptionReport` (``None`` → empty result).
    audit:
        Computed :class:`AuditReport` (``None`` → all states default to
        ``"identified"``).
    eval_results:
        Parsed eval result files from ``eval_drift.parser``.
    evidence_records:
        Parsed evidence lines from ``.evidence/invocations.jsonl``.

    Returns
    -------
    list[ModeQualityMetric]:
        Sorted list of metrics, one per mode in the adoption report.
        Returns an empty list when *adoption* is ``None``.

    Notes
    -----
    Join key is ``(category, mode)``.  Eval results are matched
    heuristically by source name (see :func:`_find_matching_eval`).
    Evidence records are matched by parsing ``feature_id`` (``"cat/mode"``)
    or the ``mode`` field.
    """
    metrics: list[ModeQualityMetric] = []

    # No adoption report → nothing to build metrics from.
    if adoption is None:
        return []

    # Build audit state lookup: (category, mode) → state string.
    audit_map: dict[tuple[str, str], str] = {}
    if audit is not None:
        for mode_state in audit.modes:
            audit_map[(mode_state.category, mode_state.mode)] = mode_state.current_state

    # Index evidence counts per (category, mode).
    evidence_counts: dict[tuple[str, str], int] = {}
    for rec in evidence_records:
        feature_id: object = rec.get("feature_id", "")
        mode_field: object = rec.get("mode")

        cat: str | None = None
        mod: str | None = None

        if isinstance(feature_id, str) and "/" in feature_id:
            parts = feature_id.split("/", 1)
            if len(parts) == 2:
                cat, mod = parts[0], parts[1]
        elif isinstance(mode_field, str):
            mod = mode_field

        if cat is not None and mod is not None:
            key = (cat, mod)
            evidence_counts[key] = evidence_counts.get(key, 0) + 1

    # Iterate over modes in the adoption report.
    for cat_score in adoption.categories:
        for mode_score in cat_score.modes:
            key = (cat_score.category, mode_score.mode)
            adoption_state = audit_map.get(key, "identified")

            matching_eval = _find_matching_eval(eval_results, cat_score.category, mode_score.mode)

            eval_score = matching_eval.avg_score if matching_eval else None
            eval_case_count = len(matching_eval.test_cases) if matching_eval else 0
            evidence_count = evidence_counts.get(key, 0)

            gap = _detect_gap(eval_score, mode_score.score)

            metrics.append(
                ModeQualityMetric(
                    mode=mode_score.mode,
                    category=cat_score.category,
                    adoption_state=adoption_state,
                    static_score=mode_score.score,
                    runtime_verified=mode_score.runtime_verified,
                    eval_score=eval_score,
                    eval_drift=None,
                    eval_case_count=eval_case_count,
                    evidence_count=evidence_count,
                    quality_adoption_gap=gap,
                )
            )

    return sorted(metrics, key=lambda m: (m.category, m.mode))
