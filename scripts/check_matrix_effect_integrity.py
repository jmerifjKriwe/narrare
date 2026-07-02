#!/usr/bin/env python3
"""Configuration Matrix Effect-Integrity Checker — ADR-061 (P1 + P2).

Runs the two ADR-061 measures over the Configuration Adoption Matrix:

  * **P2 (BLOCKING)** — aggregation prohibition: every entry maps to exactly
    one setting (``scripts/governance/_matrix_aggregation.py``). A
    ``setting_id`` that aggregates multiple settings is rejected unless it is
    in the governed ``composite_allowlist`` AND carries a
    ``composite_rationale``.
  * **P1 (WARNING-only)** — per-setting effect-integrity: each
    ``user``/``project``/``adopted`` entry's ``runtime_consumer`` references a
    REAL code location, and the cited evidence covers THIS setting
    (``scripts/governance/_matrix_effect_integrity.py``). Unproven entries are
    governed debt, reported but non-blocking this cycle.

RULE-07: reads the matrix + evidence manifests and the cited source/test FILES
(as text, never imported). Imports no application runtime modules.

Exit code: 1 if P2 (blocking) finds violations; 0 otherwise. P1 never fails the
gate (WARNING-only phasing per ADR-061).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from governance._matrix_aggregation import validate_aggregation  # noqa: E402
from governance._matrix_effect_integrity import (  # noqa: E402
    Verification,
    load_effect_evidence,
    validate_effect_integrity,
)
from governance._matrix_types import MatrixEntry, load_matrix, parse_matrix  # noqa: E402

MATRIX_PATH = ROOT / "docs" / "architecture" / "governance" / "configuration-adoption-matrix.yaml"
EVIDENCE_PATH = ROOT / "docs" / "architecture" / "governance" / "matrix-effect-evidence.yaml"

_SEP = "=" * 72


def main() -> int:
    """Run the P2 (blocking) + P1 (warning) checks and print a report."""
    try:
        matrix_data = load_matrix(MATRIX_PATH)
    except FileNotFoundError:
        print(f"FAIL: matrix file not found: {MATRIX_PATH}")
        return 1
    except Exception as exc:  # surface any parse failure visibly
        print(f"FAIL: could not parse matrix: {exc}")
        return 1

    entries, expected_ids = parse_matrix(matrix_data)

    # P2 evidence manifest also carries the composite_allowlist; fall back to an
    # empty allowlist if the manifest is absent so P2 still runs structurally.
    composite_allowlist: frozenset[str]
    try:
        _, composite_allowlist = load_effect_evidence(EVIDENCE_PATH)
    except FileNotFoundError:
        composite_allowlist = frozenset()
        print(f"WARN: evidence manifest not found: {EVIDENCE_PATH} (P1 skipped)")
    except Exception as exc:  # surface any evidence-manifest parse failure visibly
        print(f"FAIL: could not parse evidence manifest: {exc}")
        return 1

    # ── P2 — aggregation prohibition (BLOCKING) ──────────────────────────────
    p2_violations = validate_aggregation(entries, composite_allowlist)

    print("Configuration Matrix Effect-Integrity Check — ADR-061 (P1 + P2)")
    print(_SEP)
    print(f"Matrix entries: {len(entries)}  Expected ids: {len(expected_ids)}")
    print(f"Composite allowlist: {sorted(composite_allowlist) or '(empty — seeded)'}")
    print(_SEP)

    print("[P2] Aggregation prohibition (one setting per row) — BLOCKING")
    print("-" * 72)
    if p2_violations:
        print(f"  FAIL: {len(p2_violations)} aggregated setting_id(s):")
        for v in p2_violations:
            print(f"    - {v.setting_id}: {v.message}")
    else:
        print("  PASS: every entry maps to exactly one setting.")
    print()

    # ── P1 — per-setting effect-integrity (WARNING-only) ─────────────────────
    p1_exit_context = _run_p1(entries) if EVIDENCE_PATH.is_file() else None

    print(_SEP)
    blocking_failed = bool(p2_violations)
    if blocking_failed:
        print("RESULT: FAIL — P2 aggregation violations (blocking).")
    else:
        print("RESULT: PASS — P2 clean; P1 reported as WARNING (non-blocking).")
    if p1_exit_context is not None:
        print(p1_exit_context)
    return 1 if blocking_failed else 0


def _run_p1(entries: list[MatrixEntry]) -> str:
    """Run the WARNING-only P1 verification and return a summary line."""
    evidence_entries, _ = load_effect_evidence(EVIDENCE_PATH)
    evidence_by_sid = {ev.setting_id: ev for ev in evidence_entries}
    report = validate_effect_integrity(entries, evidence_by_sid, ROOT)

    graph_count = sum(
        1 for d in report.details if d.verification == Verification.GRAPH and d.verified
    )
    manifest_count = report.verified - graph_count

    print("[P1] Per-setting effect-integrity — WARNING-only (baseline)")
    print("-" * 72)
    print(f"  In scope:     {report.total_in_scope}")
    print(f"  Verified:     {report.verified}  (graph: {graph_count}, manifest: {manifest_count})")
    print(f"  Consumer-only (sibling-evidence gap): {report.consumer_only}")
    print(f"  Gaps (no manifest entry):             {report.gaps}")
    print(f"  Broken (cited file/symbol missing):   {report.broken}")

    debt = [d for d in report.details if not d.verified]
    if debt:
        print("  Governed debt (reported, non-blocking):")
        for d in debt:
            print(f"    - {d.setting_id}: {d.reason}")
    else:
        print("  Baseline clean — all in-scope entries verified.")
    print()

    return (
        f"P1 baseline: {report.verified}/{report.total_in_scope} verified "
        f"({report.consumer_only + report.gaps + report.broken} governed debt)."
    )


if __name__ == "__main__":
    raise SystemExit(main())
