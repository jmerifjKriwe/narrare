#!/usr/bin/env python3
"""Governance Drift Checker — ADR-062 Phase 2 (P3 + P5), WARNING-only.

Runs the two ADR-062 drift measures over the repository's governance surfaces:

  * **P3** — doc↔status-SSOT consistency (``governance/_status_consistency.py``):
    scans derived status docs for claims about governed subjects and flags
    contradictions against the authoritative SSOT status
    (``status_vocabulary.yaml``).
  * **P5** — review→registry metadata linking (``governance/_review_registry_link.py``):
    asserts every ``### [AUFG-XX-YY]`` review header maps to a consistent
    registry entry (matching id, source referencing the review, valid dependency
    paths, no id collision), recognizing documented re-homings.

WARNING-only this cycle (ADR-062 enforcement phasing): all findings are reported
but the exit code is always 0, so this checker cannot break CI green. Both
measures ratchet to blocking in a follow-up once the baseline is proven stable.
RULE-07: reads docs/registry/review markdown and resolves cited paths against
the repo filesystem (never imported). Imports no application runtime modules.

Exit code: 0 (always — WARNING-only baseline). Infrastructure errors (a missing
or malformed baseline file) are surfaced as visible warnings but remain
non-blocking this cycle.

See: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_VOCAB_PATH = ROOT / "docs" / "architecture" / "governance" / "status_vocabulary.yaml"
_REGISTRY_PATH = ROOT / "docs" / "architecture" / "governance" / "aufg-registry.md"

_SEP = "=" * 72


def main() -> int:
    """Run P3 + P5 and print a WARNING-only report. Always returns 0."""
    print("Governance Drift Check — ADR-062 Phase 2 (P3 + P5), WARNING-only")
    print(_SEP)

    p3_findings = _run_p3()
    p5_findings = _run_p5()

    print(_SEP)
    total = p3_findings + p5_findings
    if total:
        print(
            f"RESULT: {total} finding(s) reported as WARNING (non-blocking). "
            "Both measures ratchet to blocking in a follow-up (ADR-062)."
        )
    else:
        print("RESULT: PASS — clean baseline (no status contradictions, no link issues).")
    return 0


def _run_p3() -> int:
    """Run the P3 status-consistency measure; return its finding count."""
    from governance._status_consistency import check_status_consistency, scan_repo_docs
    from governance._status_vocab import load_status_vocabulary

    print("[P3] Doc↔status-SSOT consistency — WARNING-only (baseline)")
    print("-" * 72)

    try:
        vocab = load_status_vocabulary(_VOCAB_PATH)
        docs = scan_repo_docs(ROOT, vocab)
        report = check_status_consistency(docs, vocab)
    except FileNotFoundError as exc:
        print(f"  WARN: status vocabulary not found ({exc.filename}); P3 skipped.")
        return 0
    except Exception as exc:  # surface visibly, never fail the gate (WARNING-only)
        print(f"  WARN: P3 could not run ({type(exc).__name__}: {exc}); skipped.")
        return 0

    print(f"  Docs scanned: {len(docs)}   Status claims: {report.claims_scanned}")
    if report.contradictions:
        print(f"  ⚠️  {len(report.contradictions)} status contradiction(s):")
        for c in report.contradictions:
            print(f"    - {c.subject}: {c.statuses[0]} vs {c.statuses[1]}  ({', '.join(c.docs)})")
            print(f"        {c.reason}")
    else:
        print("  ✅ No status contradictions (clean baseline).")
    print()
    return len(report.contradictions)


def _run_p5() -> int:
    """Run the P5 review→registry linking measure; return its finding count."""
    from governance._review_registry_link import (
        check_review_registry_link,
        collect_review_headers,
        parse_registry_meta,
    )

    print("[P5] Review→registry metadata linking — WARNING-only (baseline)")
    print("-" * 72)

    try:
        headers = collect_review_headers(ROOT)
        registry = parse_registry_meta(_REGISTRY_PATH.read_text(encoding="utf-8"))
        report = check_review_registry_link(headers, registry, ROOT)
    except FileNotFoundError as exc:
        print(f"  WARN: registry not found ({exc.filename}); P5 skipped.")
        return 0
    except Exception as exc:  # surface visibly, never fail the gate (WARNING-only)
        print(f"  WARN: P5 could not run ({type(exc).__name__}: {exc}); skipped.")
        return 0

    print(
        f"  Review headers: {len(headers)}   Registry entries: {len(registry)}   "
        f"Re-homings recognized: {len(report.rehomings_recognized)}"
    )
    if report.rehomings_recognized:
        print(f"    re-homed ids: {', '.join(report.rehomings_recognized)}")
    if report.findings:
        print(f"  ⚠️  {len(report.findings)} review→registry link issue(s):")
        for f in report.findings:
            print(f"    - [{f.kind}] {f.task_id} ({f.review_file}): {f.detail}")
    else:
        print("  ✅ No review→registry link issues (clean baseline).")
    print()
    return len(report.findings)


if __name__ == "__main__":
    raise SystemExit(main())
