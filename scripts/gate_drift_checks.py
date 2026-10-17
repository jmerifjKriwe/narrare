"""Gate drift check logic — constants, data structures, helpers, and checks.

Extracted from check_gate_drift.py for RULE-04 compliance.
This module contains the "business logic" for detecting drift between
gate-exceptions.json / the CI workflow and the documented gate baseline.

Authority: ADR-098, re-anchored by CI-R1 W1-9a — the gate SSOT is the ci.yml
header audit table (G1-G10 + G6a) plus CONSTRAINTS.md §6, mirrored in prose by
docs/development/quality-gates.md (QUALITY_GATES_PATH). The retired agent-context
anchor .opencode/context/narrare-dev/processes/quality-gates.md (removed in
f11eb44a, retired by ADR-098) stays retired. ADR-098 is also the process authority
for the gate-exception registry (scripts/gate-exceptions.json).

A MISSING quality-gates.md is a hard failure (check "ssot-present"), not a vacuous
pass: the pre-W1-9 design treated the SSOT as optional and silently degraded on
absence — but a missing SSOT is drift by definition, the exact condition this
checker exists to catch. The ssot-present item is never exception-eligible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_YAML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
EXCEPTIONS_PATH = REPO_ROOT / "scripts" / "gate-exceptions.json"
QUALITY_GATES_PATH = REPO_ROOT / "docs" / "development" / "quality-gates.md"


# ── Data structures ────────────────────────────────────────────


@dataclass
class DriftItem:
    """Result of a single drift comparison."""

    check_id: str
    passed: bool
    detail: str
    has_exception: bool = False
    exception_id: str | None = None

    @property
    def is_ok(self) -> bool:
        """True if drift is acceptable (no drift, or drift has exception)."""
        return self.passed or self.has_exception


@dataclass
class DriftReport:
    """Aggregated report of all drift checks."""

    items: list[DriftItem] = field(default_factory=list[DriftItem])

    @property
    def has_unregistered_drift(self) -> bool:
        """True if any drift lacks a registered exception."""
        return any(not item.is_ok for item in self.items)

    @property
    def warnings(self) -> int:
        """Count of drifts that have registered exceptions."""
        return sum(1 for item in self.items if not item.passed and item.has_exception)

    @property
    def criticals(self) -> int:
        """Count of drifts without registered exceptions."""
        return sum(1 for item in self.items if not item.is_ok)


# ── Helpers ────────────────────────────────────────────────────


def _read_file(path: Path) -> str | None:
    """Read a file, returning None if it does not exist."""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _load_exceptions() -> dict[str, Any]:
    """Load gate-exceptions.json, returning empty structure on failure."""
    content = _read_file(EXCEPTIONS_PATH)
    if content is None:
        return {"exceptions": []}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"exceptions": []}


def _get_exception_ids(data: dict[str, Any]) -> set[str]:
    """Extract set of active exception IDs from the registry."""
    return {exc["id"] for exc in data.get("exceptions", []) if exc.get("status") == "active"}


def _find_cov_fail_under(ci_content: str) -> str | None:
    """Extract the --cov-fail-under value from CI YAML."""
    match = re.search(r"--cov-fail-under=(\d+)", ci_content)
    return match.group(1) if match else None


def _check_step_in_architecture_job(ci_content: str, script_name: str) -> bool:
    """Check if a script is run in the architecture job."""
    return bool(re.search(rf"(?:uv run )?python\s+scripts/{re.escape(script_name)}", ci_content))


def _has_continue_on_error(ci_content: str, script_name: str) -> bool:
    """Check if a script step has continue-on-error: true."""
    lines = ci_content.splitlines()
    for i, line in enumerate(lines):
        if script_name in line:
            # Check surrounding context (within 5 lines above the run step)
            for j in range(max(0, i - 5), i):
                if re.search(r"continue-on-error:\s*true", lines[j], re.IGNORECASE):
                    return True
    return False


# ── Check functions ────────────────────────────────────────────


def check_coverage_threshold(
    ci_content: str,
    exception_ids: set[str],
) -> DriftItem:
    """Check CI coverage threshold against the documented gate baseline."""
    ci_value = _find_cov_fail_under(ci_content)

    if ci_value is None:
        return DriftItem(
            check_id="coverage-threshold",
            passed=False,
            detail="Could not find --cov-fail-under in CI configuration",
            has_exception="coverage-threshold" in exception_ids,
            exception_id="coverage-threshold" if "coverage-threshold" in exception_ids else None,
        )

    # Documented target is 80% (core 90%, api 80%) per ci.yml gate row G2 and
    # CONSTRAINTS.md §6 (RULE-10); re-anchored by ADR-098.
    ci_int = int(ci_value)
    target = 80
    has_drift = ci_int < target

    detail = (
        f"CI --cov-fail-under={ci_value}, documented target {target}%"
        f"{' (exception registered)' if has_drift else ''}"
    )

    return DriftItem(
        check_id="coverage-threshold",
        passed=not has_drift,
        detail=detail,
        has_exception="coverage-threshold" in exception_ids if has_drift else False,
        exception_id="coverage-threshold"
        if has_drift and "coverage-threshold" in exception_ids
        else None,
    )


def check_streaming_compliance(
    ci_content: str,
    exception_ids: set[str],
) -> DriftItem:
    """Check streaming compliance script is blocking in CI."""
    script = "check_streaming_compliance.py"
    in_arch = _check_step_in_architecture_job(ci_content, script)

    if not in_arch:
        return DriftItem(
            check_id="streaming-compliance",
            passed=False,
            detail=f"{script} not found in CI architecture job",
            has_exception="streaming-compliance" in exception_ids,
            exception_id="streaming-compliance"
            if "streaming-compliance" in exception_ids
            else None,
        )

    has_soft = _has_continue_on_error(ci_content, script)
    if has_soft:
        return DriftItem(
            check_id="streaming-compliance",
            passed=False,
            detail=f"{script} uses continue-on-error (not blocking)",
            has_exception="streaming-compliance" in exception_ids,
            exception_id="streaming-compliance"
            if "streaming-compliance" in exception_ids
            else None,
        )

    return DriftItem(
        check_id="streaming-compliance",
        passed=True,
        detail="Blocking in CI",
    )


def check_locale_sync(
    ci_content: str,
    exception_ids: set[str],
) -> DriftItem:
    """Check locale sync script is blocking in CI."""
    script = "check_locale_sync.py"
    in_arch = _check_step_in_architecture_job(ci_content, script)

    if not in_arch:
        return DriftItem(
            check_id="locale-sync",
            passed=False,
            detail=f"{script} not found in CI architecture job",
            has_exception="locale-sync" in exception_ids,
            exception_id="locale-sync" if "locale-sync" in exception_ids else None,
        )

    has_soft = _has_continue_on_error(ci_content, script)
    if has_soft:
        return DriftItem(
            check_id="locale-sync",
            passed=False,
            detail=f"{script} uses continue-on-error (not blocking)",
            has_exception="locale-sync" in exception_ids,
            exception_id="locale-sync" if "locale-sync" in exception_ids else None,
        )

    return DriftItem(
        check_id="locale-sync",
        passed=True,
        detail="Blocking in CI",
    )


def check_ssot_present() -> DriftItem:
    """Check that the quality-gates SSOT doc exists.

    Root cause (W1-9a): the pre-W1-9 read silently degraded to "" when the file
    was absent — the design assumed an optional SSOT. That was wrong: a missing
    SSOT is drift by definition, so absence fails loudly here and can never be
    silenced via the exception registry (``has_exception`` stays False by
    construction; this check does not consult the registry).
    """
    rel_path = QUALITY_GATES_PATH.relative_to(REPO_ROOT)
    if QUALITY_GATES_PATH.is_file():
        return DriftItem(
            check_id="ssot-present",
            passed=True,
            detail=f"Quality gates SSOT present at {rel_path}",
        )
    return DriftItem(
        check_id="ssot-present",
        passed=False,
        detail=(
            f"Quality gates SSOT MISSING at {rel_path} — a missing SSOT is drift "
            "by definition; restore docs/development/quality-gates.md or fix "
            "QUALITY_GATES_PATH (not exception-eligible)"
        ),
    )


# ── Orchestration ──────────────────────────────────────────────


def run_all_checks() -> DriftReport:
    """Run all drift checks and return the aggregated report."""
    ci_content = _read_file(CI_YAML_PATH) or ""
    exceptions_data = _load_exceptions()
    exception_ids = _get_exception_ids(exceptions_data)

    report = DriftReport()
    report.items.append(check_ssot_present())
    report.items.append(check_coverage_threshold(ci_content, exception_ids))
    report.items.append(check_streaming_compliance(ci_content, exception_ids))
    report.items.append(check_locale_sync(ci_content, exception_ids))

    return report
