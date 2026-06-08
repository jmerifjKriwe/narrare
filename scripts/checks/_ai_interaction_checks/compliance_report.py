from __future__ import annotations

import json


class ComplianceReport:
    """Aggregated compliance report for all 5 checks."""

    def __init__(self) -> None:
        self.checks: dict[str, dict[str, list[str]]] = {}
        self.fix_applied: list[str] = []

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

    @property
    def total_violations(self) -> int:
        return sum(len(c["violations"]) for c in self.checks.values())

    @property
    def total_passes(self) -> int:
        return sum(len(c["passes"]) for c in self.checks.values())

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

        lines.append("-" * 60)
        lines.append(f"  Passes: {self.total_passes}  |  Violations: {self.total_violations}")
        if self.fix_applied:
            lines.append(f"  Auto-fixed ({len(self.fix_applied)} files):")
            for f in self.fix_applied:
                lines.append(f"    -> {f}")

        if self.compliant:
            lines.append("")
            lines.append("RESULT: All ADR-043 compliance checks pass")
        else:
            lines.append("")
            lines.append(
                f"RESULT: {self.total_violations} violation(s) found -- fix before merging"
            )
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json(self) -> str:
        return json.dumps(
            {
                "check": "ADR-043 AI Interaction Compliance",
                "compliant": self.compliant,
                "total_passes": self.total_passes,
                "total_violations": self.total_violations,
                "checks": {
                    name: {
                        "pass_count": len(data["passes"]),
                        "violation_count": len(data["violations"]),
                        "violations": data["violations"],
                    }
                    for name, data in self.checks.items()
                },
                "fix_applied": self.fix_applied,
            },
            indent=2,
        )
