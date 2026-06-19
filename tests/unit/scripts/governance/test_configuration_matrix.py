"""Tests for the Configuration Adoption Matrix validator (ADR-051 / CR-AUFG-08-09).

Validates the structural and policy rules:

* required fields, controlled vocabularies, unique ids, expected-id coverage;
* the P0 gate — a ``user``/``project`` setting without a runtime_consumer or
  evidence fails (unless it is a tracked ``formal_finding``);
* the real matrix manifest on disk validates cleanly (integration check).

RULE-07: the validator imports no application runtime modules; these tests
exercise it with in-memory entries plus one read of the real manifest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.configuration_matrix import (  # noqa: E402
    MatrixEntry,
    MatrixReport,
    MatrixStatus,
    load_matrix,
    parse_matrix,
    validate_matrix,
)

_MATRIX_PATH = (
    _PROJECT_ROOT / "docs" / "architecture" / "governance" / "configuration-adoption-matrix.yaml"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    setting_id: str = "s1",
    *,
    classification: str = "operator",
    lifecycle: str = "governed_default",
    source: str = "code default",
    resolver_service: str = "Service.resolve",
    effect_semantics: str = "changes X",
    fallback_policy: str = "warning",
    runtime_consumer: str | None = "Consumer.apply",
    enforcement_evidence: tuple[str, ...] = ("tests/unit/x.py::t",),
    cross_layer_evidence: tuple[str, ...] = (),
    cr_task: str | None = None,
    finding: str | None = None,
    phase: str | None = None,
    review_trigger: str | None = None,
    rationale: str | None = None,
) -> MatrixEntry:
    """Build a fully-populated valid entry for testing."""
    return MatrixEntry(
        setting_id=setting_id,
        classification=classification,
        lifecycle=lifecycle,
        source=source,
        resolver_service=resolver_service,
        effect_semantics=effect_semantics,
        fallback_policy=fallback_policy,
        runtime_consumer=runtime_consumer,
        enforcement_evidence=enforcement_evidence,
        cross_layer_evidence=cross_layer_evidence,
        cr_task=cr_task,
        finding=finding,
        phase=phase,
        review_trigger=review_trigger,
        rationale=rationale,
    )


def _rules(report: MatrixReport) -> set[str]:
    """Return the set of violated rule names."""
    return {v.rule for v in report.violations}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_matrix_passes() -> None:
    """A well-formed matrix with full coverage validates as PASS."""
    entries = [_entry("a"), _entry("b", classification="user", lifecycle="adopted")]
    expected = ["a", "b"]

    report = validate_matrix(entries, expected)

    assert report.status == MatrixStatus.PASS
    assert report.total_entries == 2
    assert report.expected_count == 2
    assert report.violations == ()
    assert report.passed is True


def test_empty_matrix_passes_when_nothing_expected() -> None:
    """No entries and no expected ids -> PASS (nothing to track)."""
    report = validate_matrix([], [])

    assert report.status == MatrixStatus.PASS
    assert report.total_entries == 0


# ---------------------------------------------------------------------------
# Rule 6 — user/project requires runtime_consumer
# ---------------------------------------------------------------------------


def test_user_setting_without_runtime_consumer_fails() -> None:
    """A user-classified setting without a runtime_consumer is a false control."""
    entry = _entry("u", classification="user", lifecycle="adopted", runtime_consumer="")
    report = validate_matrix([entry], ["u"])

    assert report.status == MatrixStatus.FAIL
    assert "missing_runtime_consumer" in _rules(report)


def test_project_setting_without_runtime_consumer_fails() -> None:
    """A project-classified setting without a runtime_consumer fails."""
    entry = _entry("p", classification="project", lifecycle="adopted", runtime_consumer=None)
    report = validate_matrix([entry], ["p"])

    assert report.status == MatrixStatus.FAIL
    assert "missing_runtime_consumer" in _rules(report)


def test_operator_setting_without_runtime_consumer_passes() -> None:
    """Operator settings are not user-facing; runtime_consumer is optional."""
    entry = _entry(
        "o", classification="operator", runtime_consumer="", lifecycle="operator_default"
    )
    report = validate_matrix([entry], ["o"])

    assert report.status == MatrixStatus.PASS


# ---------------------------------------------------------------------------
# Rule 7 — user/project requires evidence (or a tracked formal_finding)
# ---------------------------------------------------------------------------


def test_user_setting_without_evidence_or_tracking_fails() -> None:
    """A user setting with no evidence and no tracking is a silent false control."""
    entry = _entry(
        "u",
        classification="user",
        lifecycle="governed_default",
        enforcement_evidence=(),
        cr_task=None,
        finding=None,
    )
    report = validate_matrix([entry], ["u"])

    assert report.status == MatrixStatus.FAIL
    assert "missing_enforcement_evidence" in _rules(report)


def test_user_formal_finding_with_tracking_passes_without_evidence() -> None:
    """A tracked formal_finding (cr_task) needs no enforcement_evidence yet."""
    entry = _entry(
        "u",
        classification="user",
        lifecycle="formal_finding",
        enforcement_evidence=(),
        cr_task="CR-AUFG-08-03",
        finding="FIND-013",
    )
    report = validate_matrix([entry], ["u"])

    assert report.status == MatrixStatus.PASS


def test_user_formal_finding_without_any_tracking_fails() -> None:
    """A user formal_finding with neither cr_task nor finding is untracked."""
    entry = _entry(
        "u",
        classification="user",
        lifecycle="formal_finding",
        enforcement_evidence=(),
        cr_task=None,
        finding=None,
    )
    report = validate_matrix([entry], ["u"])

    assert report.status == MatrixStatus.FAIL
    rules = _rules(report)
    assert "missing_enforcement_evidence" in rules
    assert "formal_finding_without_tracking" in rules


# ---------------------------------------------------------------------------
# Rule 8 — adopted requires evidence
# ---------------------------------------------------------------------------


def test_adopted_setting_without_evidence_fails() -> None:
    """An adopted setting must carry enforcement_evidence."""
    entry = _entry(
        "a",
        classification="operator",
        lifecycle="adopted",
        enforcement_evidence=(),
    )
    report = validate_matrix([entry], ["a"])

    assert report.status == MatrixStatus.FAIL
    assert "adopted_without_evidence" in _rules(report)


def test_adopted_setting_with_evidence_passes() -> None:
    """An adopted setting carrying evidence is valid."""
    entry = _entry("a", classification="operator", lifecycle="adopted")
    report = validate_matrix([entry], ["a"])

    assert report.status == MatrixStatus.PASS


# ---------------------------------------------------------------------------
# Rule 9 — formal_finding requires tracking
# ---------------------------------------------------------------------------


def test_formal_finding_without_tracking_fails() -> None:
    """A formal_finding without cr_task/finding is untracked prose debt."""
    entry = _entry(
        "f",
        classification="operator",
        lifecycle="formal_finding",
        enforcement_evidence=(),
        cr_task=None,
        finding=None,
    )
    report = validate_matrix([entry], ["f"])

    assert report.status == MatrixStatus.FAIL
    assert "formal_finding_without_tracking" in _rules(report)


def test_formal_finding_with_finding_only_passes() -> None:
    """A formal_finding tracked by a finding reference (no cr_task) is valid."""
    entry = _entry(
        "f",
        classification="operator",
        lifecycle="formal_finding",
        enforcement_evidence=(),
        finding="FIND-099",
    )
    report = validate_matrix([entry], ["f"])

    assert report.status == MatrixStatus.PASS


# ---------------------------------------------------------------------------
# Rule 1 — required fields
# ---------------------------------------------------------------------------


def test_missing_required_field_fails() -> None:
    """An entry missing a required structural field fails."""
    entry = MatrixEntry(
        setting_id="m",
        classification="operator",
        lifecycle="governed_default",
        source="",
        resolver_service="S",
        effect_semantics="e",
        fallback_policy="warn",
    )
    report = validate_matrix([entry], ["m"])

    assert report.status == MatrixStatus.FAIL
    assert "required_field" in _rules(report)


# ---------------------------------------------------------------------------
# Rule 2 — controlled vocabularies
# ---------------------------------------------------------------------------


def test_invalid_classification_fails() -> None:
    """An unknown classification value fails."""
    entry = _entry("c", classification="superuser", lifecycle="adopted")
    report = validate_matrix([entry], ["c"])

    assert report.status == MatrixStatus.FAIL
    assert "invalid_classification" in _rules(report)


def test_invalid_lifecycle_fails() -> None:
    """An unknown lifecycle value fails."""
    entry = _entry("l", classification="operator", lifecycle="pending")
    report = validate_matrix([entry], ["l"])

    assert report.status == MatrixStatus.FAIL
    assert "invalid_lifecycle" in _rules(report)


# ---------------------------------------------------------------------------
# Rules 3, 4, 5 — id coverage
# ---------------------------------------------------------------------------


def test_duplicate_setting_id_fails() -> None:
    """Duplicate setting_ids fail (rule 3)."""
    entries = [_entry("dup"), _entry("dup")]
    report = validate_matrix(entries, ["dup"])

    assert report.status == MatrixStatus.FAIL
    assert "duplicate_setting_id" in _rules(report)


def test_unclassified_expected_id_fails() -> None:
    """An expected id with no entry is unclassified (rule 4)."""
    report = validate_matrix([_entry("present")], ["present", "missing"])

    assert report.status == MatrixStatus.FAIL
    rules = _rules(report)
    assert "unclassified_setting" in rules


def test_unexpected_entry_id_fails() -> None:
    """An entry id not in expected_setting_ids is a typo (rule 5)."""
    report = validate_matrix([_entry("typo")], ["correct"])

    assert report.status == MatrixStatus.FAIL
    assert "unexpected_setting_id" in _rules(report)


def test_all_expected_ids_present_passes() -> None:
    """Exact expected<->entry coverage passes."""
    report = validate_matrix([_entry("a"), _entry("b")], ["a", "b"])

    assert report.status == MatrixStatus.PASS


# ---------------------------------------------------------------------------
# Integration — the real matrix manifest
# ---------------------------------------------------------------------------


def test_real_matrix_file_validates_pass() -> None:
    """The committed configuration-adoption-matrix.yaml must validate cleanly.

    This is the P0 DoD gate: the matrix on disk must pass the checker.
    """
    data = load_matrix(_MATRIX_PATH)
    entries, expected_ids = parse_matrix(data)

    report = validate_matrix(entries, expected_ids)

    assert report.status == MatrixStatus.PASS, (
        f"matrix has violations: {[(v.rule, v.setting_id, v.message) for v in report.violations]}"
    )


def test_real_matrix_classifies_all_cr08_values() -> None:
    """Every expected CR-08 setting_id has exactly one entry (no unclassified)."""
    data = load_matrix(_MATRIX_PATH)
    entries, expected_ids = parse_matrix(data)

    entry_ids = [e.setting_id for e in entries]

    # Every expected id is present.
    missing = set(expected_ids) - set(entry_ids)
    assert not missing, f"unclassified CR-08 values: {sorted(missing)}"
    # No unexpected ids (typo guard).
    extra = set(entry_ids) - set(expected_ids)
    assert not extra, f"unexpected setting_ids: {sorted(extra)}"
    # No duplicates.
    assert len(entry_ids) == len(set(entry_ids)), "duplicate setting_ids present"
    # Symmetric: expected == entries.
    assert len(expected_ids) == len(entries)


def test_real_matrix_p0_values_carry_evidence() -> None:
    """The two P0 adopted values (output limits, tier_percentages) carry evidence."""
    data = load_matrix(_MATRIX_PATH)
    entries, _ = parse_matrix(data)
    by_id = {e.setting_id: e for e in entries}

    output_limits = by_id["output_limit_enforcement"]
    tier_percentages = by_id["tier_percentages_consumption"]

    assert output_limits.lifecycle == "adopted"
    assert output_limits.enforcement_evidence, "output_limit_enforcement needs evidence"
    assert output_limits.runtime_consumer, "output_limit_enforcement needs runtime_consumer"

    assert tier_percentages.lifecycle == "adopted"
    assert tier_percentages.enforcement_evidence, "tier_percentages_consumption needs evidence"
    assert tier_percentages.runtime_consumer, "tier_percentages_consumption needs runtime_consumer"
