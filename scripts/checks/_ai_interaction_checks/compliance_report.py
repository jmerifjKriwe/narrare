from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._shared import ExcludeEntry


class ComplianceReport:
    """Aggregated compliance report for all 5 checks."""

    def __init__(self) -> None:
        self.checks: dict[str, dict[str, list[str]]] = {}
        self.fix_applied: list[str] = []
        self.governed: dict[str, list[ExcludeEntry]] = {}
        self.malformed: list[str] = []

    def add(
        self,
        name: str,
        passes: list[str],
        violations: list[str],
        fix_applied: list[str] | None = None,
    ) -> None:
        self.checks[name] = {"passes": passes, "violations": violations}
        if fix_applied:
            self.fix_applied.extend(fix_applied)

    def add_governed(self, check_name: str, entries: list[ExcludeEntry]) -> None:
        """Register governed exclusions (baseline debt) for a check."""
        if entries:
            self.governed[check_name] = entries

    def add_malformed(self, malformed: list[str]) -> None:
        """Register malformed exclude entries."""
        self.malformed.extend(malformed)

    @property
    def total_violations(self) -> int:
        return sum(len(c["violations"]) for c in self.checks.values())

    @property
    def total_passes(self) -> int:
        return sum(len(c["passes"]) for c in self.checks.values())

    @property
    def total_governed(self) -> int:
        return sum(len(v) for v in self.governed.values())

    @property
    def compliant(self) -> bool:
        return self.total_violations == 0

    def format_text(self, compact: bool = False) -> str:
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("  ADR-043 / section 16 AI Interaction Compliance Check")
        lines.append("=" * 60)
        lines.append("")

        for check_name, data in self.checks.items():
            violations = data["violations"]
            passes = data["passes"]
            status = "PASS" if not violations else "FAIL"
            lines.append(f"  [{status}] {check_name}")
            if violations:
                for v in violations:
                    lines.append(f"    x {v}")
            if passes and not compact:
                for p in passes:
                    lines.append(f"    v {p}")
            lines.append("")

        # -- Governed exclusions section ------------------------------------
        if self.governed:
            lines.append("-" * 60)
            lines.append(f"  Governed Exclusions — Baseline Debt ({self.total_governed})")
            for check_name, entries in self.governed.items():
                lines.append(f"    [{check_name}] ({len(entries)})")
                for e in entries:
                    lines.append(f"      {e.path}")
                    lines.append(
                        f'        owner={e.owner} | reason="{e.reason}" | exit="{e.exit_criteria}"'
                    )
                    lines.append(f"        added={e.added} | re_evaluated={e.re_evaluated}")
            lines.append("")

        # -- Malformed entries section --------------------------------------
        if self.malformed:
            lines.append("-" * 60)
            lines.append(f"  [WARN] Malformed Exclude Entries ({len(self.malformed)})")
            for msg in self.malformed:
                for part in msg.split("\n"):
                    lines.append(f"    {part}")
            lines.append("")

        lines.append("-" * 60)
        parts = [
            f"Passes: {self.total_passes}",
            f"Violations: {self.total_violations}",
            f"Governed: {self.total_governed}",
        ]
        if self.malformed:
            parts.append(f"Malformed: {len(self.malformed)}")
        lines.append(f"  {'  |  '.join(parts)}")

        if self.fix_applied:
            lines.append(f"  Auto-fixed ({len(self.fix_applied)} files):")
            for f in self.fix_applied:
                lines.append(f"    -> {f}")

        if self.compliant:
            lines.append("")
            if self.total_governed:
                lines.append(
                    "RESULT: All checks pass — "
                    f"{self.total_governed} governed exclusion(s) tracked as baseline debt"
                )
            else:
                lines.append("RESULT: All ADR-043 compliance checks pass")
        else:
            lines.append("")
            lines.append(
                f"RESULT: {self.total_violations} violation(s) found -- fix before merging"
            )
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json(self) -> str:
        governed_json: dict[str, list[dict[str, str]]] = {}
        for check_name, entries in self.governed.items():
            governed_json[check_name] = [
                {
                    "path": e.path,
                    "owner": e.owner,
                    "gate": e.gate,
                    "reason": e.reason,
                    "exit": e.exit_criteria,
                    "added": e.added,
                    "re_evaluated": e.re_evaluated,
                }
                for e in entries
            ]

        return json.dumps(
            {
                "check": "ADR-043 AI Interaction Compliance",
                "compliant": self.compliant,
                "total_passes": self.total_passes,
                "total_violations": self.total_violations,
                "total_governed": self.total_governed,
                "checks": {
                    name: {
                        "pass_count": len(data["passes"]),
                        "violation_count": len(data["violations"]),
                        "violations": data["violations"],
                    }
                    for name, data in self.checks.items()
                },
                "governed_exclusions": governed_json,
                "malformed": self.malformed,
                "fix_applied": self.fix_applied,
            },
            indent=2,
        )
