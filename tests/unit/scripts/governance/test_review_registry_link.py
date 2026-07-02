"""ADR-062 P5 — review→registry metadata linking checker tests.

The checker asserts that every ``### [AUFG-XX-YY]`` / ``### [CR-AUFG-XX-YY]``
header in a review file maps to exactly one consistent registry entry: matching
id, source referencing the originating review, valid dependency paths (for
active entries), and no id collision — with documented re-homings recognized.

WARNING-only this cycle: findings are reported but never fail the gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._review_registry_link import (  # noqa: E402
    ReviewLinkFinding,
    ReviewLinkReport,
    ReviewTaskHeader,
    check_review_registry_link,
    collect_review_headers,
    parse_registry_meta,
    parse_review_headers,
)

_REVIEW = "review-01-architektur.md"


# ---------------------------------------------------------------------------
# parse_review_headers
# ---------------------------------------------------------------------------


def test_parse_review_headers_extracts_aufg_headers() -> None:
    text = "## Aufgaben\n\n### [AUFG-01-01] Retry-Settings\n\nbody\n\n### [AUFG-01-02] voice\n"
    headers = parse_review_headers(text, _REVIEW)
    ids = [h.task_id for h in headers]
    assert ids == ["AUFG-01-01", "AUFG-01-02"]
    assert all(h.review_file == _REVIEW for h in headers)
    assert headers[0].line >= 1


def test_parse_review_headers_extracts_cr_prefixed_headers() -> None:
    text = "### [CR-AUFG-07-07] KB Field Suggest\n"
    headers = parse_review_headers(text, _REVIEW)
    assert headers[0].task_id == "CR-AUFG-07-07"


def test_parse_review_headers_ignores_plain_aufg_mentions() -> None:
    """Only bracketed task headers count, not prose mentions."""
    text = "See AUFG-01-01 above.\n\nbody AUFG-99-99\n"
    assert parse_review_headers(text, _REVIEW) == []


# ---------------------------------------------------------------------------
# collect_review_headers — repo-wide review-file globbing
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_review_headers_globs_audit_results(tmp_path: Path) -> None:
    """Headers are collected from _audit/results/**/review-*.md (recursive)."""
    _write(
        tmp_path / "_audit" / "results" / "technical-review" / "review-42-demo.md",
        "### [AUFG-42-01] Demo\n",
    )
    _write(
        tmp_path / "_audit" / "results" / "release" / "review-99-release.md",
        "### [CR-AUFG-99-01] Release\n",
    )
    # Non-review markdown is ignored.
    _write(tmp_path / "_audit" / "results" / "notes.md", "### [AUFG-00-01] Note\n")

    headers = collect_review_headers(tmp_path)
    ids = sorted(h.task_id for h in headers)
    assert ids == ["AUFG-42-01", "CR-AUFG-99-01"]


def test_collect_review_headers_empty_when_no_reviews(tmp_path: Path) -> None:
    """A repo with no review files yields an empty header list (not an error)."""
    assert collect_review_headers(tmp_path) == []


# ---------------------------------------------------------------------------
# parse_registry_meta
# ---------------------------------------------------------------------------


def test_parse_registry_meta_extracts_id_source_status_deps() -> None:
    text = (
        "### AUFG-01-01 — Retry\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| ID | AUFG-01-01 |\n"
        "| Source | review-01-architektur.md §5 |\n"
        "| Status | `resolved` |\n"
        "| Dependencies | `packages/core/retry.py`; RULE-18b |\n\n"
    )
    meta = parse_registry_meta(text)
    assert "AUFG-01-01" in meta
    m = meta["AUFG-01-01"]
    assert m.entry_id == "AUFG-01-01"
    assert "review-01-architektur.md" in m.source
    assert m.status == "resolved"
    assert "packages/core/retry.py" in m.dependencies_text


def test_parse_registry_meta_accepted_risk_uses_type_row() -> None:
    text = (
        "### AR-05-02 — Rate-Limit\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| Type | `accepted_risk` |\n"
        "| Source | AUFG-05-07 audit |\n\n"
    )
    meta = parse_registry_meta(text)
    assert meta["AR-05-02"].status == "accepted_risk"


# ---------------------------------------------------------------------------
# check_review_registry_link — link consistency
# ---------------------------------------------------------------------------


def _registry(
    *,
    entry_id: str = "AUFG-01-01",
    source: str = "review-01-architektur.md §5",
    status: str = "open",
    deps: str = "",
    extra_section: str = "",
) -> dict[str, object]:
    text = (
        f"### {entry_id} — Title\n\n"
        "| Field | Value |\n|-------|-------|\n"
        f"| ID | {entry_id} |\n"
        f"| Source | {source} |\n"
        f"| Status | `{status}` |\n"
        f"| Dependencies | {deps} |\n\n"
        f"{extra_section}\n"
    )
    return parse_registry_meta(text)


def test_direct_link_with_matching_source_is_clean() -> None:
    headers = [ReviewTaskHeader("AUFG-01-01", _REVIEW, 1)]
    registry = _registry(entry_id="AUFG-01-01", source=_REVIEW, status="open")
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    assert report.findings == ()
    assert report.headers_scanned == 1


def test_missing_registry_entry_is_flagged() -> None:
    headers = [ReviewTaskHeader("AUFG-01-99", _REVIEW, 1)]
    report = check_review_registry_link(headers, {}, Path("/nonexistent"))
    kinds = {f.kind for f in report.findings}
    assert "missing_entry" in kinds
    assert report.findings[0].task_id == "AUFG-01-99"


def test_source_mismatch_is_flagged() -> None:
    """id exists but its source does not reference the originating review."""
    headers = [ReviewTaskHeader("AUFG-01-03", _REVIEW, 1)]
    registry = _registry(
        entry_id="AUFG-01-03",
        source="review-05-release.md §5",
        status="accepted_enhancement",
    )
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    kinds = {f.kind for f in report.findings}
    assert "source_mismatch" in kinds


# ---------------------------------------------------------------------------
# Re-homing recognition (AUFG-01-03 editor → AUFG-01-08)
# ---------------------------------------------------------------------------


def test_documented_rehoming_is_recognized(tmp_path: Path) -> None:
    """A re-homed entry claims the original header id without false-positive.

    Models the real case: review-01 ``### [AUFG-01-03]`` (editor hotspots) was
    re-homed to AUFG-01-08. AUFG-01-08's source references review-01 and its
    section notes the re-homing from AUFG-01-03.
    """
    headers = [ReviewTaskHeader("AUFG-01-03", _REVIEW, 1)]
    registry_text = (
        "### AUFG-01-08 — Editor Hotspots\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| ID | AUFG-01-08 |\n"
        "| Source | review-01-architektur.md §Aufgaben (review-01 AUFG-01-03, "
        "re-homed to avoid collision). |\n"
        "| Status | `resolved` |\n\n"
        "Rationale: review-01's editor task was re-homed from AUFG-01-03.\n"
    )
    registry = parse_registry_meta(registry_text)
    report = check_review_registry_link(headers, registry, tmp_path)

    assert report.findings == ()
    assert "AUFG-01-03" in report.rehomings_recognized


def test_rehoming_requires_source_reference_to_review(tmp_path: Path) -> None:
    """A re-homing note in an entry whose source is a different review is NOT a claim."""
    headers = [ReviewTaskHeader("AUFG-01-03", _REVIEW, 1)]
    registry_text = (
        "### AUFG-01-08 — Editor Hotspots\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| Source | review-05-release.md (re-homed from AUFG-01-03). |\n"
        "| Status | `resolved` |\n\n"
    )
    registry = parse_registry_meta(registry_text)
    report = check_review_registry_link(headers, registry, tmp_path)
    kinds = {f.kind for f in report.findings}
    # No claiming entry for review-01 → source_mismatch (AUFG-01-03 in registry
    # would be needed; absent here → missing_entry).
    assert "missing_entry" in kinds or "source_mismatch" in kinds


# ---------------------------------------------------------------------------
# Dependency path validity (active entries only)
# ---------------------------------------------------------------------------


def test_active_entry_invalid_dependency_path_is_flagged(tmp_path: Path) -> None:
    headers = [ReviewTaskHeader("AUFG-09-01", _REVIEW, 1)]
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    registry = _registry(
        entry_id="AUFG-09-01",
        source=_REVIEW,
        status="open",
        deps="`real.py`; `does/not/exist.py`",
    )
    report = check_review_registry_link(headers, registry, tmp_path)
    dep_findings = [f for f in report.findings if f.kind == "invalid_dependency_path"]
    assert len(dep_findings) == 1
    assert "does/not/exist.py" in dep_findings[0].detail


def test_resolved_entry_dependency_paths_are_not_checked(tmp_path: Path) -> None:
    """Resolved entries' deps are historical (e.g. a since-deleted file)."""
    headers = [ReviewTaskHeader("AUFG-09-01", _REVIEW, 1)]
    registry = _registry(
        entry_id="AUFG-09-01",
        source=_REVIEW,
        status="resolved",
        deps="`packages/core/deleted.py`",
    )
    report = check_review_registry_link(headers, registry, tmp_path)
    assert [f for f in report.findings if f.kind == "invalid_dependency_path"] == []


def test_glob_dependency_patterns_are_skipped(tmp_path: Path) -> None:
    headers = [ReviewTaskHeader("AUFG-09-01", _REVIEW, 1)]
    registry = _registry(
        entry_id="AUFG-09-01",
        source=_REVIEW,
        status="open",
        deps="`lookup/*.md`",
    )
    report = check_review_registry_link(headers, registry, tmp_path)
    assert [f for f in report.findings if f.kind == "invalid_dependency_path"] == []


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


def test_report_records_scan_counts() -> None:
    headers = [
        ReviewTaskHeader("AUFG-01-01", _REVIEW, 1),
        ReviewTaskHeader("AUFG-01-02", _REVIEW, 5),
    ]
    registry = {
        "AUFG-01-01": _registry(entry_id="AUFG-01-01", source=_REVIEW)["AUFG-01-01"],
        "AUFG-01-02": _registry(entry_id="AUFG-01-02", source=_REVIEW)["AUFG-01-02"],
    }
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    assert isinstance(report, ReviewLinkReport)
    assert report.headers_scanned == 2
    assert report.entries_scanned == 2
    assert report.findings == ()


def test_finding_carries_task_and_review() -> None:
    headers = [ReviewTaskHeader("AUFG-01-99", _REVIEW, 9)]
    report = check_review_registry_link(headers, {}, Path("/nonexistent"))
    f = report.findings[0]
    assert isinstance(f, ReviewLinkFinding)
    assert f.task_id == "AUFG-01-99"
    assert f.review_file == _REVIEW
