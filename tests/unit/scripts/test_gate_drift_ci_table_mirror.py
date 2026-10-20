"""Tests for the ci-table-mirror gate drift check (T17b2).

No ``test_gate_drift*.py`` existed before: the gate-drift checks had no unit
coverage at all beyond the CLI-level checks elsewhere. This file covers the
new row-equality contract between the ``ci.yml`` header table (the declared
CI-gate SSOT) and its prose mirror in ``docs/development/quality-gates.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.gate_drift_checks import (  # noqa: E402
    CI_YAML_PATH,
    QUALITY_GATES_PATH,
    check_ci_table_mirror,
    compare_gate_rows,
    extract_gate_rows,
)


def _table(*rows: tuple[str, str]) -> str:
    """Build a CI-comment table from (gate_id, tool) pairs."""
    lines = [
        "# | Gate | Tool / Check | CI Status | Notes |",
        "# |------|--------------|-----------|-------|",
    ]
    lines.extend(
        f"# | {gate:<4} | {tool} | ✅ Blocking | architecture Job |" for gate, tool in rows
    )
    return "\n".join(lines) + "\n"


class TestExtractGateRows:
    """Row extraction and normalisation."""

    def test_header_and_separator_rows_are_ignored(self) -> None:
        content = _table(("G1", "pytest"))
        assert extract_gate_rows(content) == ["pytest"]

    def test_internal_whitespace_is_collapsed(self) -> None:
        content = "# | --   |   check_doc_drift.py    --check   | ✅ Blocking | x |\n"
        assert extract_gate_rows(content) == ["check_doc_drift.py --check"]

    def test_non_gate_id_rows_are_ignored(self) -> None:
        content = "| MutMut Mutation Score | mutation-testing-monthly.yml | 📅 Monthly | x |\n"
        assert extract_gate_rows(content) == []


class TestCompareGateRows:
    """The comparison reports both drift directions."""

    def test_missing_row_each_direction_is_reported(self, tmp_path: Path) -> None:
        ci = tmp_path / "ci.yml"
        doc = tmp_path / "quality-gates.md"
        ci.write_text(
            _table(("G1", "pytest"), ("G2", "--cov-fail-under"), ("G3", "check_architecture.py")),
            encoding="utf-8",
        )
        doc.write_text(
            _table(
                ("G1", "pytest"), ("G2", "--cov-fail-under"), ("G4", "test_fake_conformance.py")
            ),
            encoding="utf-8",
        )

        ci_only, doc_only = compare_gate_rows(
            ci.read_text(encoding="utf-8"), doc.read_text(encoding="utf-8")
        )

        assert ci_only == {"check_architecture.py"}
        assert doc_only == {"test_fake_conformance.py"}

    def test_mismatched_rows_fail_and_name_both_directions(self, tmp_path: Path) -> None:
        ci = tmp_path / "ci.yml"
        doc = tmp_path / "quality-gates.md"
        ci.write_text(_table(("G1", "pytest"), ("G3", "check_architecture.py")), encoding="utf-8")
        doc.write_text(
            _table(("G1", "pytest"), ("G4", "test_fake_conformance.py")), encoding="utf-8"
        )

        item = check_ci_table_mirror(
            ci.read_text(encoding="utf-8"),
            doc.read_text(encoding="utf-8"),
            exception_ids=set(),
        )

        assert item.check_id == "ci-table-mirror"
        assert item.passed is False
        assert "only in ci.yml: check_architecture.py" in item.detail
        assert "only in quality-gates.md: test_fake_conformance.py" in item.detail
        assert item.is_ok is False

    def test_duplicated_row_on_one_side_is_a_count_mismatch(self, tmp_path: Path) -> None:
        ci = tmp_path / "ci.yml"
        doc = tmp_path / "quality-gates.md"
        ci.write_text(
            _table(("G1", "pytest"), ("G1", "pytest"), ("G3", "check_architecture.py")),
            encoding="utf-8",
        )
        doc.write_text(_table(("G1", "pytest"), ("G3", "check_architecture.py")), encoding="utf-8")

        ci_content = ci.read_text(encoding="utf-8")
        doc_content = doc.read_text(encoding="utf-8")
        ci_only, doc_only = compare_gate_rows(ci_content, doc_content)
        assert ci_only == set()
        assert doc_only == set()

        item = check_ci_table_mirror(ci_content, doc_content, exception_ids=set())

        assert item.check_id == "ci-table-mirror"
        assert item.passed is False
        assert item.is_ok is False
        assert "row counts differ: pytest (ci.yml 2, quality-gates.md 1)" in item.detail
        assert "only in" not in item.detail

    def test_equal_tables_pass(self) -> None:
        ci = _table(("G1", "pytest"), ("G3", "check_architecture.py"))
        item = check_ci_table_mirror(ci, ci, exception_ids=set())

        assert item.passed is True
        assert item.detail == "Both gate tables carry the same 2 tool/check rows"


class TestRealTree:
    """The committed tree must be mirrored."""

    def test_committed_tables_are_identical(self) -> None:
        ci_content = CI_YAML_PATH.read_text(encoding="utf-8")
        doc_content = QUALITY_GATES_PATH.read_text(encoding="utf-8")

        ci_only, doc_only = compare_gate_rows(ci_content, doc_content)
        assert ci_only == set()
        assert doc_only == set()

        item = check_ci_table_mirror(ci_content, doc_content, exception_ids=set())
        assert item.passed is True, item.detail
