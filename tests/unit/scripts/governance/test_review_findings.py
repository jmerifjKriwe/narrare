"""Tests for the review-finding candidate extractor (ADR-047 Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.review_findings import (  # noqa: E402
    CandidateFinding,
    extract_candidate_findings,
    extract_references,
)

# ---------------------------------------------------------------------------
# extract_references
# ---------------------------------------------------------------------------


def test_extract_references_finds_aufg_id() -> None:
    """A single AUFG-XX-YY reference is extracted."""
    refs = extract_references("Some finding (AUFG-05-07 bleibt offen).")

    assert refs == ("AUFG-05-07",)


def test_extract_references_finds_multiple_ids() -> None:
    """Multiple distinct references are extracted in order of appearance."""
    refs = extract_references("See AUFG-05-07 and AR-05-02 and AE-05-01.")

    assert refs == ("AUFG-05-07", "AR-05-02", "AE-05-01")


def test_extract_references_deduplicates() -> None:
    """Repeated references appear only once."""
    refs = extract_references("AUFG-05-07 ... AUFG-05-07 ... AUFG-05-07")

    assert refs == ("AUFG-05-07",)


def test_extract_references_returns_empty_when_none_present() -> None:
    """Text without any lifecycle IDs returns an empty tuple."""
    refs = extract_references("Some prose without any AUFG reference.")

    assert refs == ()


def test_extract_references_handles_bracketed_ids() -> None:
    """Bracketed references like [AUFG-05-07] are extracted."""
    refs = extract_references("- **[AUFG-05-07]** Some task description.")

    assert "AUFG-05-07" in refs


# ---------------------------------------------------------------------------
# extract_candidate_findings — Offene Punkte
# ---------------------------------------------------------------------------


def test_extract_findings_from_offene_punkte_section() -> None:
    """Bullet items under an 'Offene Punkte' heading are extracted."""
    text = (
        "# Review 05\n\n"
        "## 3. Security\n\n"
        "### Offene Punkte\n"
        "- **CORS:** Rate limiting not audited.\n"
        "- **CSRF:** No token validation.\n"
        "- **Secrets:** No CI gate.\n"
    )

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 3
    assert "CORS" in findings[0].text
    assert "CSRF" in findings[1].text


def test_extract_findings_stops_at_next_header() -> None:
    """Findings are not collected beyond the next section header."""
    text = "### Offene Punkte\n- Real finding.\n\n### Befunde\n- Not a finding candidate.\n"

    findings = extract_candidate_findings(text, "review.md")

    assert len(findings) == 1
    assert "Real finding" in findings[0].text


def test_extract_findings_stops_at_horizontal_rule() -> None:
    """A horizontal rule (---) terminates the finding section."""
    text = "### Offene Punkte\n- Real finding.\n\n---\n\n- Not a finding after rule.\n"

    findings = extract_candidate_findings(text, "review.md")

    assert len(findings) == 1


def test_extract_findings_with_aufg_reference() -> None:
    """A finding containing an AUFG reference captures it in .references."""
    text = "### Offene Punkte\n- Trace correlation missing (AUFG-05-03 bleibt offen).\n"

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 1
    assert "AUFG-05-03" in findings[0].references


def test_extract_findings_without_references() -> None:
    """A prose-only finding has an empty references tuple."""
    text = "### Offene Punkte\n- CORS config not audited.\n"

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 1
    assert findings[0].references == ()


# ---------------------------------------------------------------------------
# extract_candidate_findings — Schwächen
# ---------------------------------------------------------------------------


def test_extract_findings_from_schwaechen_section() -> None:
    """Numbered items under 'Schwächen & Risiken' are extracted."""
    text = (
        "### Schwächen & Risiken (priorisiert)\n"
        "1. **CI-Blocker (Hoch):** Some blocker.\n"
        "2. **Coverage-Lücke (Mittel):** Only 60 percent.\n"
    )

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 2
    assert "CI-Blocker" in findings[0].text
    assert "Coverage" in findings[1].text


def test_extract_findings_from_schwaechen_with_umlaut() -> None:
    """The section header 'Schwächen' with umlaut is detected."""
    text = "### Schwächen\n- Risk item one.\n"

    findings = extract_candidate_findings(text, "review.md")

    assert len(findings) == 1


# ---------------------------------------------------------------------------
# extract_candidate_findings — multi-line & edge cases
# ---------------------------------------------------------------------------


def test_extract_findings_joins_multiline_bullets() -> None:
    """Multi-line bullet items are joined into a single finding."""
    text = (
        "### Offene Punkte\n"
        "- **CORS:** Cookie SameSite reduces risk, but\n"
        "  rate limiting rules and CORS config were not fully audited.\n"
    )

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 1
    assert "rate limiting" in findings[0].text


def test_extract_findings_no_finding_sections() -> None:
    """A document without finding sections produces zero candidates."""
    text = "# Review\n\n## Summary\n\n- Just a normal bullet.\n- Another bullet.\n"

    findings = extract_candidate_findings(text, "review.md")

    assert findings == []


def test_finding_records_source_file_and_line() -> None:
    """Each finding records its source file name and line number."""
    text = (
        "# Review\n\n"  # line 1, empty line 2
        "## Section\n\n"  # line 3, empty line 4
        "### Offene Punkte\n"  # line 5
        "- First finding.\n"  # line 6
    )

    findings = extract_candidate_findings(text, "review-05.md")

    assert len(findings) == 1
    assert findings[0].source_file == "review-05.md"
    assert findings[0].line_number == 6


def test_multiple_finding_sections_are_all_collected() -> None:
    """Findings from multiple 'Offene Punkte' sections are all collected."""
    text = (
        "### Offene Punkte\n"
        "- Finding A.\n"
        "\n"
        "### Some Other Section\n"
        "- Not a finding.\n"
        "\n"
        "### Offene Punkte\n"
        "- Finding B.\n"
    )

    findings = extract_candidate_findings(text, "review.md")

    assert len(findings) == 2
    assert "Finding A" in findings[0].text
    assert "Finding B" in findings[1].text


# ---------------------------------------------------------------------------
# CandidateFinding dataclass
# ---------------------------------------------------------------------------


def test_candidate_finding_is_frozen() -> None:
    """CandidateFinding is immutable."""
    finding = CandidateFinding(
        source_file="r.md",
        line_number=1,
        text="test",
        references=("AUFG-05-07",),
    )

    assert finding.source_file == "r.md"
    assert finding.line_number == 1
    assert finding.references == ("AUFG-05-07",)
