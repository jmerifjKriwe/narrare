#!/usr/bin/env python3
"""KG consistency checker for static CI validation.

Reads the adoption registry for entity/variable requirements per mode,
scans bundled prompt files for actual KG variable usage, and reports
mismatches. Returns non-zero exit code on critical mismatches.

See: ADR-040 Decision 2 (Platform-level checker).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

# ── Constants ──────────────────────────────────────────────────────

# KG variable patterns found in prompt templates.
_KG_VAR_PREFIXES: tuple[str, ...] = (
    "kb_",
    "character_",
    "world_context",
)

# Regex to find {{variable}} patterns in prompt content.
_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")


# ── Data models ──────────────────────────────────────────────────────


@dataclass
class KGMismatch:
    """A single mismatch between registry requirements and prompt usage."""

    category: str
    mode: str
    variable: str
    mismatch_type: str  # "missing_in_prompt" | "missing_in_registry"
    severity: str  # "critical" | "warning"
    message: str


@dataclass
class KGConsistencyResult:
    """Result of KG consistency check."""

    checked_modes: int
    mismatches: list[KGMismatch] = field(default_factory=list[KGMismatch])
    critical_count: int = 0
    warning_count: int = 0
    ok: bool = True

    def to_json(self) -> str:
        """Machine-readable JSON for CI consumption."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        """Human-readable text output."""
        lines: list[str] = []
        lines.append(f"KG Consistency Check: {self.checked_modes} modes checked")

        if not self.mismatches:
            lines.append("✅ No mismatches found.")
            return "\n".join(lines)

        lines.append(f"❌ {self.critical_count} critical, {self.warning_count} warning mismatches")
        lines.append("")

        for m in self.mismatches:
            icon = "🚫" if m.severity == "critical" else "⚠️"
            lines.append(
                f"  {icon} {m.category}/{m.mode}: {m.message} [{m.mismatch_type}] ({m.variable})"
            )

        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────


def _is_kg_variable(var: str) -> bool:
    """Check if a variable is a KG-related variable."""
    return any(var.startswith(prefix) for prefix in _KG_VAR_PREFIXES)


def _load_registry(path: Path) -> dict[str, Any]:
    """Load the adoption registry YAML."""
    if not path.exists():
        print(f"ERROR: Adoption registry not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open("r", encoding="utf-8") as fh:
        data: Any = yaml.safe_load(fh)
    if not data or not isinstance(data, dict):
        print("ERROR: Adoption registry is not valid YAML", file=sys.stderr)
        sys.exit(1)
    return cast("dict[str, Any]", data)


def _get_mode_kg_vars(
    mode_overrides: dict[str, Any],
    category_ctx: dict[str, Any],
) -> set[str]:
    """Get KG variables for a specific mode (merging overrides)."""
    override_ctx = mode_overrides.get("context_variables", {})
    must: list[str] = override_ctx.get("must", category_ctx.get("must", [])) or []
    should: list[str] = override_ctx.get("should", category_ctx.get("should", [])) or []
    all_vars = set(must + should)
    return {v for v in all_vars if _is_kg_variable(v)}


def _scan_prompt_variables(
    prompts_dir: Path,
    category: str,
    mode: str,
) -> set[str]:
    """Scan bundled prompt files for actual variable usage in a mode."""
    variables: set[str] = set()

    # Look for system.md files in the mode directory.
    mode_dir = prompts_dir / category / "en" / mode
    if not mode_dir.is_dir():
        return variables

    for md_file in mode_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        found = set(_VARIABLE_RE.findall(content))
        variables.update(found)

    return {v for v in variables if _is_kg_variable(v)}


# ── Core check ───────────────────────────────────────────────────────


def check_kg_consistency(
    registry_path: Path,
    prompts_dir: Path,
) -> KGConsistencyResult:
    """Run the KG consistency check.

    Compares registry-declared KG variables against actual prompt
    template usage. Reports:
    - Variables required by registry but missing from prompts (critical)
    - KG variables in prompts not declared in registry (warning)

    Parameters
    ----------
    registry_path:
        Path to ``adoption-registry.yaml``.
    prompts_dir:
        Path to ``_bundled/`` directory.

    Returns
    -------
    KGConsistencyResult with mismatches and summary.
    """
    registry = _load_registry(registry_path)
    features: dict[str, Any] = registry.get("features", {})
    mismatches: list[KGMismatch] = []
    checked_modes = 0

    for cat_name, cfg in sorted(features.items()):
        ctx_vars = cfg.get("context_variables", {})

        raw_modes: Any = cfg.get("modes", [])
        mode_items: list[tuple[str, dict[str, Any]]] = []
        if isinstance(raw_modes, dict):
            raw_dict = cast("dict[str, Any]", raw_modes)
            mode_items = list(raw_dict.items())
        elif isinstance(raw_modes, list):
            raw_list = cast("list[Any]", raw_modes)
            mode_items = [(str(m), {}) for m in raw_list]

        for mode_name, mode_cfg in mode_items:
            checked_modes += 1
            overrides = cast("dict[str, Any]", mode_cfg.get("overrides", {}) if mode_cfg else {})
            required_kg = _get_mode_kg_vars(overrides, ctx_vars)
            actual_kg = _scan_prompt_variables(prompts_dir, cat_name, mode_name)

            # Critical: required by registry but missing from prompts.
            missing_in_prompt = required_kg - actual_kg
            for var in sorted(missing_in_prompt):
                # Determine severity from must vs should.
                must_vars: list[str] = ctx_vars.get("must", []) or []
                is_must = var in must_vars
                severity = "critical" if is_must else "warning"
                mismatches.append(
                    KGMismatch(
                        category=cat_name,
                        mode=mode_name,
                        variable=var,
                        mismatch_type="missing_in_prompt",
                        severity=severity,
                        message=(f"Registry requires '{var}' but prompt doesn't use it"),
                    )
                )

            # Warning: used in prompts but not declared in registry.
            undeclared = actual_kg - required_kg
            for var in sorted(undeclared):
                mismatches.append(
                    KGMismatch(
                        category=cat_name,
                        mode=mode_name,
                        variable=var,
                        mismatch_type="missing_in_registry",
                        severity="warning",
                        message=(f"Prompt uses '{var}' but registry doesn't declare it"),
                    )
                )

    critical_count = sum(1 for m in mismatches if m.severity == "critical")
    warning_count = sum(1 for m in mismatches if m.severity == "warning")

    return KGConsistencyResult(
        checked_modes=checked_modes,
        mismatches=mismatches,
        critical_count=critical_count,
        warning_count=warning_count,
        ok=critical_count == 0,
    )


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point for the KG consistency checker."""
    parser = argparse.ArgumentParser(
        description="Check KG variable consistency between registry and prompts.",
        epilog="Exit codes: 0 = no critical mismatches, 1 = critical mismatches found",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "scripts"
        / "architecture"
        / "adoption-registry.yaml",
        help="Path to adoption-registry.yaml",
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "packages"
        / "core"
        / "narrare_core"
        / "prompts"
        / "_bundled",
        help="Path to _bundled/ directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    result = check_kg_consistency(args.registry, args.prompts)

    if args.json:
        print(result.to_json())
    else:
        print(result.to_text())

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
