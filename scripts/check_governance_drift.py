#!/usr/bin/env python3
"""Governance Drift Checker — ADR-062 Phase 2 (P3 + P5), BLOCKING.

Runs the two ADR-062 drift measures over the repository's governance surfaces:

  * **P3** — doc↔status-SSOT consistency (``governance/_status_consistency.py``):
    scans derived status docs for claims about governed subjects and flags
    contradictions against the authoritative SSOT status
    (``status_vocabulary.yaml``).
  * **P5** — review→registry metadata linking (``governance/_review_registry_link.py``):
    asserts every ``### [AUFG-XX-YY]`` review header maps to a consistent
    registry entry (matching id, source referencing the review, valid dependency
    paths, no id collision), recognizing documented re-homings.

BLOCKING (ADR-062 enforcement phasing complete): findings fail the gate with
exit 1. Both measures were promoted from warning-only to blocking in the
AUFG-01-09 follow-up (2026-07-06) after the baseline was proven clean across a
full review cycle. The P5 parser hardening (rich Status cells, bare-filename
dependency paths) landed in the same follow-up, closing the known limitations
deferred at ADR-062's initial implementation.
RULE-07: reads docs/registry/review markdown and resolves cited paths against
the repo filesystem (never imported). Imports no application runtime modules.

Exit code: 1 if P3 or P5 finds findings; 0 otherwise. Infrastructure errors
(a missing or malformed baseline file) are surfaced as visible warnings and
remain non-blocking (a missing vocabulary/registry cannot be a drift finding).

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
    """Run P3 + P5 and print a BLOCKING report. Returns 1 on any finding."""
    print("Governance Drift Check — ADR-062 Phase 2 (P3 + P5), BLOCKING")
    print(_SEP)

    p3_findings = _run_p3()
    p5_findings = _run_p5()

    print(_SEP)
    total = p3_findings + p5_findings
    if total:
        print(
            f"RESULT: FAIL — {total} finding(s) (blocking). P3: {p3_findings}, P5: {p5_findings}."
        )
    else:
        print("RESULT: PASS — clean (no status contradictions, no link issues).")
    return 1 if total else 0


def _run_p3() -> int:
    """Run the P3 status-consistency measure; return its finding count."""
    from governance._status_consistency import check_status_consistency, scan_repo_docs
    from governance._status_vocab import load_status_vocabulary

    print("[P3] Doc↔status-SSOT consistency — BLOCKING")
    print("-" * 72)

    try:
        vocab = load_status_vocabulary(_VOCAB_PATH)
        docs = scan_repo_docs(ROOT, vocab)
        report = check_status_consistency(docs, vocab)
    except FileNotFoundError as exc:
        print(f"  WARN: status vocabulary not found ({exc.filename}); P3 skipped.")
        return 0
    except Exception as exc:  # surface visibly, never fail on infrastructure
        print(f"  WARN: P3 could not run ({type(exc).__name__}: {exc}); skipped.")
        return 0

    print(f"  Docs scanned: {len(docs)}   Status claims: {report.claims_scanned}")
    if report.contradictions:
        print(f"  FAIL: {len(report.contradictions)} status contradiction(s):")
        for c in report.contradictions:
            print(f"    - {c.subject}: {c.statuses[0]} vs {c.statuses[1]}  ({', '.join(c.docs)})")
            print(f"        {c.reason}")
    else:
        print("  PASS: no status contradictions.")
    print()
    return len(report.contradictions)


def _run_p5() -> int:
    """Run the P5 review→registry linking measure; return its finding count."""
    from governance._review_registry_link import (
        check_review_registry_link,
        collect_review_headers,
        parse_registry_meta,
    )

    print("[P5] Review→registry metadata linking — BLOCKING")
    print("-" * 72)

    try:
        headers = collect_review_headers(ROOT)
        registry = parse_registry_meta(_REGISTRY_PATH.read_text(encoding="utf-8"))
        report = check_review_registry_link(headers, registry, ROOT)
    except FileNotFoundError as exc:
        print(f"  WARN: registry not found ({exc.filename}); P5 skipped.")
        return 0
    except Exception as exc:  # surface visibly, never fail on infrastructure
        print(f"  WARN: P5 could not run ({type(exc).__name__}: {exc}); skipped.")
        return 0

    print(
        f"  Review headers: {len(headers)}   Registry entries: {len(registry)}   "
        f"Re-homings recognized: {len(report.rehomings_recognized)}"
    )
    if report.rehomings_recognized:
        print(f"    re-homed ids: {', '.join(report.rehomings_recognized)}")
    if report.findings:
        print(f"  FAIL: {len(report.findings)} review→registry link issue(s):")
        for f in report.findings:
            print(f"    - [{f.kind}] {f.task_id} ({f.review_file}): {f.detail}")
    else:
        print("  PASS: no review→registry link issues.")
    print()
    return len(report.findings)


if __name__ == "__main__":
    raise SystemExit(main())
