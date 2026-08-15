"""Tests for scripts/doc_drift/ — ADR cross-reference and status checks.

Validates ADR cross-reference and status consistency checks using tmp_path
with mock ADR files and INDEX.md for isolation.

See: ADR-041 Decision 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


from doc_drift.adr_checks import (  # noqa: E402
    _extract_adr_id,
    _parse_adr_status,
    _parse_index_entries,
    _parse_related_adrs,
    _parse_superseded_by,
    _parse_supersedes,
    check_adr_consistency,
)

# ── ADR Parsing Helpers ───────────────────────────────────────


class TestExtractADRId:
    """Test ADR ID extraction from filenames."""

    def test_standard_prefix(self) -> None:
        assert _extract_adr_id("ADR-001-llm-gateway.md") == "ADR-001"

    def test_no_prefix(self) -> None:
        # The extractor tolerates the legacy (prefixless) form even though
        # all current ADR files now use the `ADR-XXX-` prefix (see
        # scripts/check_adr_naming.py for enforcement).
        assert _extract_adr_id("017-some-legacy-name.md") == "ADR-017"

    def test_template_excluded(self) -> None:
        assert _extract_adr_id("_TEMPLATE.md") is None

    def test_index_excluded(self) -> None:
        assert _extract_adr_id("INDEX.md") is None

    def test_non_adr_file(self) -> None:
        assert _extract_adr_id("notes.md") is None


class TestParseADRStatus:
    """Test status parsing from ADR content."""

    def test_blockquote_accepted(self) -> None:
        content = "> **Status:** ✅ Accepted\n"
        assert _parse_adr_status(content) == "accepted"

    def test_blockquote_proposed(self) -> None:
        content = "> **Status:** 🔄 Proposed\n"
        assert _parse_adr_status(content) == "proposed"

    def test_blockquote_superseded(self) -> None:
        content = "> **Status:** ⛔ Superseded by ADR-031\n"
        assert _parse_adr_status(content) == "superseded"

    def test_blockquote_superseded_markdown_link(self) -> None:
        content = "> **Status:** ⛔ Superseded by [ADR-080](ADR-080-task-deletion.md)\n"
        assert _parse_adr_status(content) == "superseded"

    def test_heading_format(self) -> None:
        content = "## Status\n\n⛔ Superseded by ADR-033\n"
        assert _parse_adr_status(content) == "superseded"

    def test_implemented_variant(self) -> None:
        content = "> **Status:** ✅ Implemented\n"
        assert _parse_adr_status(content) == "implemented"

    def test_no_status_returns_none(self) -> None:
        assert _parse_adr_status("no status here") is None


class TestParseSupersedes:
    """Test Supersedes: line parsing."""

    def test_single_adr(self) -> None:
        content = "> **Supersedes:** ADR-006\n"
        assert _parse_supersedes(content) == ["ADR-006"]

    def test_none_dash(self) -> None:
        content = "> **Supersedes:** —\n"
        assert _parse_supersedes(content) == []

    def test_no_line(self) -> None:
        assert _parse_supersedes("no supersedes line") == []


class TestParseSupersededBy:
    """Test superseded-by reference parsing."""

    def test_in_status_line(self) -> None:
        content = "> **Status:** ⛔ Superseded by ADR-031\n"
        assert _parse_superseded_by(content) == ["ADR-031"]

    def test_no_reference(self) -> None:
        content = "> **Status:** ✅ Accepted\n"
        assert _parse_superseded_by(content) == []

    def test_in_status_line_markdown_link(self) -> None:
        content = "> **Status:** ⛔ Superseded by [ADR-080](ADR-080-task-deletion.md)\n"
        assert _parse_superseded_by(content) == ["ADR-080"]

    def test_markdown_link_in_body(self) -> None:
        content = (
            "> **Status:** ⛔ Superseded by [ADR-012](ADR-012-event-driven.md)\n\n"
            "See the replacement for the new mechanism.\n"
        )
        assert _parse_superseded_by(content) == ["ADR-012"]

    def test_plain_and_link_mixed_dedup(self) -> None:
        content = (
            "> **Status:** ⛔ Superseded by [ADR-080](ADR-080-task-deletion.md)\n\n"
            "The successor is Superseded by ADR-080 again in the body.\n"
        )
        assert _parse_superseded_by(content) == ["ADR-080"]


class TestParseRelatedADRs:
    """Test Related: line parsing."""

    def test_multiple_refs(self) -> None:
        content = "> **Related:** ADR-002, ADR-015, CONSTRAINTS.md RULE-01b\n"
        assert _parse_related_adrs(content) == ["ADR-002", "ADR-015"]

    def test_no_refs(self) -> None:
        content = "> **Related:** —\n"
        assert _parse_related_adrs(content) == []


class TestParseIndexEntries:
    """Test INDEX.md table parsing."""

    def test_extracts_entries(self) -> None:
        content = (
            "| [ADR-001](ADR-001-llm-gateway.md) | Single LLM Gateway | ✅ | init |\n"
            "| [ADR-002](ADR-002-prompt-system.md) | Unified prompt | 🔄 | 2026-05 |\n"
        )
        entries = _parse_index_entries(content)
        assert "ADR-001" in entries
        assert "ADR-002" in entries
        assert entries["ADR-001"]["status_emoji"] == "✅"
        assert entries["ADR-002"]["status_emoji"] == "🔄"


# ── ADR Consistency Checks ────────────────────────────────────


def _make_adr_file(
    tmp_path: Path,
    adr_id: str,
    status: str = "Accepted",
    supersedes: str = "—",
    related: str = "—",
    superseded_by: str = "",
) -> Path:
    """Create a mock ADR file in tmp_path."""
    if status == "Proposed":
        status_line = "> **Status:** 🔄 Proposed"
    elif status == "Superseded":
        status_line = (
            f"> **Status:** ⛔ Superseded by {superseded_by}"
            if superseded_by
            else "> **Status:** ⛔ Superseded"
        )
    elif status == "Deprecated":
        status_line = "> **Status:** 🗄️ Deprecated"
    else:
        status_line = f"> **Status:** ✅ {status}"

    filename = f"{adr_id}-test-decision.md"
    content = (
        f"# {adr_id} — Test Decision\n\n"
        f"{status_line}\n"
        f"> **Date:** 2026-01-01\n"
        f"> **Deciders:** Test\n"
        f"> **Supersedes:** {supersedes}\n"
        f"> **Related:** {related}\n\n"
        f"## Context\n\nTest context.\n"
    )
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


def _make_index_md(
    tmp_path: Path,
    entries: list[tuple[str, str, str]],
) -> Path:
    """Create a mock INDEX.md in tmp_path.

    Args:
        entries: List of (adr_id, title, status_emoji).
    """
    lines = [
        "# Architecture Decision Records — Index\n",
        "| ID | Title | Status | Date |\n",
        "|----|-------|--------|------|\n",
    ]
    for adr_id, title, emoji in entries:
        filename = f"{adr_id}-test-decision.md"
        lines.append(f"| [{adr_id}]({filename}) | {title} | {emoji} | init |\n")
    p = tmp_path / "INDEX.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TestADRIndexConsistency:
    """ADR file exists but not in INDEX = drift."""

    def test_file_not_in_index_gives_warning(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Accepted")
        _make_index_md(tmp_path, [])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        assert any(f.severity == "warning" and "no row in INDEX" in f.message for f in findings)

    def test_index_without_file_gives_critical(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Accepted")
        _make_index_md(tmp_path, [("ADR-001", "Test", "✅"), ("ADR-002", "Ghost", "✅")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        assert any(f.severity == "critical" and "ADR-002" in f.message for f in findings)

    def test_fully_consistent_no_findings(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Accepted")
        _make_index_md(tmp_path, [("ADR-001", "Test", "✅")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) == 0


class TestADRStatusAlignment:
    """Status mismatch between ADR file and INDEX.md."""

    def test_status_mismatch_critical(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Proposed")
        _make_index_md(tmp_path, [("ADR-001", "Test", "✅")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        assert any(f.severity == "critical" and "status mismatch" in f.message for f in findings)

    def test_matching_status_no_findings(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Accepted")
        _make_index_md(tmp_path, [("ADR-001", "Test", "✅")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        status_findings = [f for f in findings if "status mismatch" in f.message]
        assert len(status_findings) == 0


class TestCrossReferenceExists:
    """ADR references non-existent ADR = critical."""

    def test_broken_reference_critical(self, tmp_path: Path) -> None:
        _make_adr_file(
            tmp_path,
            "ADR-001",
            "Accepted",
            related="ADR-999, ADR-998",
        )
        _make_index_md(tmp_path, [("ADR-001", "Test", "✅")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        assert any(f.severity == "critical" and "ADR-999" in f.message for f in findings)

    def test_valid_reference_no_finding(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Accepted", related="ADR-002")
        _make_adr_file(tmp_path, "ADR-002", "Accepted")
        _make_index_md(
            tmp_path,
            [("ADR-001", "Test 1", "✅"), ("ADR-002", "Test 2", "✅")],
        )

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        xref_findings = [
            f for f in findings if "does not exist" in f.message and "Related" in f.message
        ]
        assert len(xref_findings) == 0


class TestSupersededLinkage:
    """Superseded ADR must reference the replacing ADR."""

    def test_superseded_without_replacing_adr_warning(self, tmp_path: Path) -> None:
        _make_adr_file(tmp_path, "ADR-001", "Superseded", superseded_by="")
        _make_index_md(tmp_path, [("ADR-001", "Test", "⛔")])

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        assert any(
            f.severity == "warning" and "does not reference the replacing" in f.message
            for f in findings
        )

    def test_superseded_with_replacing_adr_ok(self, tmp_path: Path) -> None:
        _make_adr_file(
            tmp_path,
            "ADR-001",
            "Superseded",
            superseded_by="ADR-002",
        )
        _make_adr_file(tmp_path, "ADR-002", "Accepted")
        _make_index_md(
            tmp_path,
            [("ADR-001", "Old", "⛔"), ("ADR-002", "New", "✅")],
        )

        findings = check_adr_consistency(
            adr_dir=tmp_path,
            index_path=tmp_path / "INDEX.md",
        )
        supersede_findings = [f for f in findings if "replacing ADR" in f.message]
        assert len(supersede_findings) == 0
