"""Tests for the review/report policy consistency gate (throughput T11)."""

from pathlib import Path

from scripts.check_review_policy_consistency import find_policy_violations, parse_policy

ROOT = Path(__file__).resolve().parents[3]
POLICY_DOC = "docs/development/quality-gates.md"
POINTING_DOCS = ("AGENTS.md",)


def _mirror_tree(tmp_path: Path) -> Path:
    """Copy the three governed files into an isolated tree for mutation tests."""
    for rel in (POLICY_DOC, *POINTING_DOCS):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_policy_marker_is_parseable() -> None:
    text = (ROOT / POLICY_DOC).read_text(encoding="utf-8")
    assert parse_policy(text) == {"caps": "3/250", "report": "2/80"}


def test_normative_block_exists() -> None:
    text = (ROOT / POLICY_DOC).read_text(encoding="utf-8")
    assert "## Review & report policy" in text
    assert "normative" in text.lower()


def test_numbers_are_not_restated_in_the_pointing_docs() -> None:
    for rel in POINTING_DOCS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "250 new LOC" not in text
        assert "≤3 files" not in text


def test_real_tree_is_clean() -> None:
    assert find_policy_violations(ROOT) == []


def test_missing_marker_is_reported(tmp_path: Path) -> None:
    (tmp_path / "docs/development").mkdir(parents=True)
    (tmp_path / "docs/development/quality-gates.md").write_text(
        "# Quality Gates\n", encoding="utf-8"
    )
    (tmp_path / "AGENTS.md").write_text("x\n", encoding="utf-8")
    assert any("marker" in v for v in find_policy_violations(tmp_path))


def test_space_separated_caps_restatement_is_reported(tmp_path: Path) -> None:
    root = _mirror_tree(tmp_path)
    agents = root / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8") + "\n- ≤ 3 files per package.\n",
        encoding="utf-8",
    )
    violations = find_policy_violations(root)
    assert any("AGENTS.md" in violation and "files" in violation for violation in violations)


def test_missing_normative_heading_is_reported(tmp_path: Path) -> None:
    root = _mirror_tree(tmp_path)
    policy = root / POLICY_DOC
    text = policy.read_text(encoding="utf-8").replace(
        "## Review & report policy", "## Review policy"
    )
    policy.write_text(text, encoding="utf-8")
    violations = find_policy_violations(root)
    assert any(
        "heading" in violation and "Review & report policy" in violation for violation in violations
    )
