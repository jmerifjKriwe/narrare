"""ADR-062 P5 — content-review surface tests (CR-AUFG-01-08).

Split out of ``test_review_registry_link.py`` (RULE-04) to cover the
content-review extension: ``cr-*.md`` globbing, the ``- **CR-AUFG-NN-MM:**``
bullet form, CR-prefix dual-match, range expansion (header / row / comma-list),
and the WARNING-only severity routing for content-review findings.

The content-review findings are WARNING-only this cycle (CR-AUFG-01-08); the
blocking ratchet is tracked as CR-AUFG-01-09.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._review_registry_link import (  # noqa: E402
    ReviewTaskHeader,
    check_review_registry_link,
    collect_review_headers,
    parse_registry_meta,
    parse_review_headers,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry(
    *,
    entry_id: str = "AUFG-01-01",
    source: str = "cr-01-demo.md §1",
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


# ---------------------------------------------------------------------------
# cr-*.md globbing + bullet parsing
# ---------------------------------------------------------------------------


def test_collect_review_headers_also_globs_content_reviews(tmp_path: Path) -> None:
    """cr-*.md content reviews are scanned alongside review-*.md (CR-AUFG-01-08)."""
    _write(
        tmp_path / "_audit" / "results" / "content-review" / "cr-01-demo.md",
        "- **CR-AUFG-01-01:** A content-review task.\n",
    )
    _write(
        tmp_path / "_audit" / "results" / "content-review" / "audit-prompts" / "cr-02-nested.md",
        "- **CR-AUFG-02-01:** Nested content review.\n",
    )

    headers = collect_review_headers(tmp_path)
    ids = sorted(h.task_id for h in headers)
    assert ids == ["CR-AUFG-01-01", "CR-AUFG-02-01"]
    origins = {h.task_id: h.origin for h in headers}
    assert origins["CR-AUFG-01-01"] == "content"
    assert origins["CR-AUFG-02-01"] == "content"


def test_parse_review_headers_extracts_cr_bullet_form() -> None:
    """The content-review ``- **CR-AUFG-NN-MM:**`` bullet is parsed as a header."""
    text = (
        "## Aufgaben\n\n"
        "- **CR-AUFG-01-01:** First task. **Status DATE:** implemented.\n"
        "- **CR-AUFG-01-02:** Second task\n"
    )
    headers = parse_review_headers(text, "cr-01-demo.md")
    ids = [h.task_id for h in headers]
    assert ids == ["CR-AUFG-01-01", "CR-AUFG-01-02"]
    assert all(h.origin == "content" for h in headers)


def test_parse_review_headers_bullet_form_only_in_content_reviews() -> None:
    """Technical reviews' bold-bullet summaries are NOT parsed as task headers.

    review-05 uses ``- **AE-05-01** …`` for a recap list; those are not task
    definitions and must not surface as false source-mismatches. Only cr-*.md
    files use the bullet form for task definitions.
    """
    text = "## Recap\n\n- **AE-05-01** Some enhancement (accepted).\n"
    assert parse_review_headers(text, "review-05-release.md") == []
    cr_headers = parse_review_headers(text, "cr-05-demo.md")
    assert [h.task_id for h in cr_headers] == ["AE-05-01"]


# ---------------------------------------------------------------------------
# CR-prefix dual-match + range expansion
# ---------------------------------------------------------------------------


def test_cr_prefix_dual_match_resolves_to_unprefixed_registry_entry() -> None:
    """A ``CR-AUFG-NN-MM`` header matches an unprefixed ``AUFG-NN-MM`` registry key.

    CR-02/03/04 content tasks are stored unprefixed in the registry while the
    review files write the ``CR-`` prefix; the dual-match bridges that.
    """
    headers = [ReviewTaskHeader("CR-AUFG-03-01", "cr-03-demo.md", 1, origin="content")]
    registry = _registry(entry_id="AUFG-03-01", source="cr-03-demo.md §1", status="open")
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    assert report.content_findings == ()
    assert report.findings == ()


def test_range_id_header_section_expands_to_per_id_entries() -> None:
    """A ``### CR-AUFG-01-01..06`` set header covers all ids in the range."""
    registry_text = (
        "### CR-AUFG-01-01..06 — Set\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| IDs | CR-AUFG-01-01 through CR-AUFG-01-06 |\n"
        "| Source | cr-01-demo.md §Aufgaben |\n"
        "| Status | `resolved` |\n"
    )
    registry = parse_registry_meta(registry_text)
    for mm in range(1, 7):
        assert f"CR-AUFG-01-{mm:02d}" in registry
    headers = [ReviewTaskHeader("CR-AUFG-01-04", "cr-01-demo.md", 1, origin="content")]
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    assert report.content_findings == ()


def test_range_row_only_section_covers_each_id() -> None:
    """A set header without a parseable id, but a ``| IDs | … through … |`` row,
    expands to per-id entries (the CR-08 set shape)."""
    registry_text = (
        "### CR-08 Configuration/Effect Drift AUFG Set\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| IDs | CR-AUFG-08-01 through CR-AUFG-08-14 |\n"
        "| Source | cr-08-hardcoded-values.md |\n"
        "| Status | `resolved` |\n"
    )
    registry = parse_registry_meta(registry_text)
    assert "CR-AUFG-08-01" in registry
    assert "CR-AUFG-08-14" in registry
    headers = [ReviewTaskHeader("CR-AUFG-08-14", "cr-08-hardcoded-values.md", 1, origin="content")]
    report = check_review_registry_link(headers, registry, Path("/nonexistent"))
    assert report.content_findings == ()


def test_comma_list_ids_row_also_expands() -> None:
    """A ``| IDs | CR-AUFG-01-01, CR-AUFG-01-02 |`` row covers each listed id."""
    registry_text = (
        "### CR-AUFG-01-01+02 — Pair\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| IDs | CR-AUFG-01-01, CR-AUFG-01-02 |\n"
        "| Source | cr-01-demo.md |\n"
        "| Status | `resolved` |\n"
    )
    registry = parse_registry_meta(registry_text)
    assert "CR-AUFG-01-01" in registry
    assert "CR-AUFG-01-02" in registry


# ---------------------------------------------------------------------------
# Severity routing: content findings WARNING, technical findings BLOCKING
# ---------------------------------------------------------------------------


def test_content_review_findings_route_to_content_findings_not_blocking() -> None:
    """A missing content-review entry is a WARNING (content_findings), not blocking.

    This is the CR-AUFG-01-08 contract: content-review findings never fail the
    gate this cycle. The blocking ``findings`` bucket stays empty.
    """
    headers = [ReviewTaskHeader("CR-AUFG-99-99", "cr-99-demo.md", 1, origin="content")]
    report = check_review_registry_link(headers, {}, Path("/nonexistent"))
    assert report.findings == ()
    assert len(report.content_findings) == 1
    assert report.content_findings[0].kind == "missing_entry"


def test_technical_review_findings_remain_blocking() -> None:
    """A missing technical-review entry still goes to the blocking findings bucket."""
    headers = [ReviewTaskHeader("AUFG-99-99", "review-01-demo.md", 1, origin="technical")]
    report = check_review_registry_link(headers, {}, Path("/nonexistent"))
    assert len(report.findings) == 1
    assert report.findings[0].kind == "missing_entry"
    assert report.content_findings == ()
