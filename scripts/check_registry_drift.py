"""Registry drift detection — validates adoption-registry.yaml against prompt files.

Checks that every registered mode has a corresponding prompt file and vice versa.
Part of ADR-041 Decision 1: JSON Schema validation + drift detection.

Exit codes:
    0 — no critical drift
    1 — critical findings (registered mode with no prompt file)
    2 — schema validation failure
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import jsonschema
import yaml

# ── Constants ───────────────────────────────────────────────────────────

_SCHEMA_NAME = "adoption-registry.schema.json"
_REGISTRY_NAME = "adoption-registry.yaml"

_ARCH_DIR = Path(__file__).resolve().parent / "architecture"
_DEFAULT_REGISTRY = _ARCH_DIR / _REGISTRY_NAME
_DEFAULT_SCHEMA = _ARCH_DIR / _SCHEMA_NAME
_DEFAULT_PROMPTS = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
)

# Categories that are infrastructure, not feature prompts.
_SKIP_CATEGORIES = frozenset({"meta", "universal"})

# Subdirectories that are auxiliary resources, not modes.
_SKIP_SUBDIRS = frozenset({"tones", "name-styles"})

# File names that are not primary mode prompts.
_SKIP_FILENAMES = frozenset({"system.lite.md"})


# ── Data ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DriftFinding:
    """A single drift finding between registry and filesystem."""

    severity: str  # "critical" | "warning" | "info"
    category: str
    mode: str
    message: str
    detail: str = ""


@dataclass
class DriftReport:
    """Aggregated drift report."""

    findings: list[DriftFinding] = field(default_factory=lambda: cast("list[DriftFinding]", []))

    @property
    def has_critical(self) -> bool:
        return any(f.severity == "critical" for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == "warning" for f in self.findings)

    def summary(self) -> str:
        crit = sum(1 for f in self.findings if f.severity == "critical")
        warn = sum(1 for f in self.findings if f.severity == "warning")
        info = sum(1 for f in self.findings if f.severity == "info")
        return f"Drift: {crit} critical, {warn} warnings, {info} info"


# ── Schema Validation ──────────────────────────────────────────────────


def _load_schema(schema_path: Path) -> dict[str, Any]:
    """Load JSON Schema from disk."""
    import json

    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_registry_schema(
    registry: dict[str, Any],
    schema_path: Path,
) -> list[DriftFinding]:
    """Validate registry data against JSON Schema.

    Returns critical findings for each validation error.
    """
    findings: list[DriftFinding] = []
    schema = _load_schema(schema_path)

    try:
        jsonschema.validate(instance=registry, schema=schema)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        findings.append(
            DriftFinding(
                severity="critical",
                category="",
                mode="",
                message=f"Schema validation failed at {path}: {exc.message}",
                detail=str(exc),
            )
        )

    return findings


# ── Prompt File Discovery ──────────────────────────────────────────────


@dataclass(frozen=True)
class PromptRef:
    """A discovered prompt file mapped to category + mode."""

    path: Path
    category: str
    mode: str  # empty string for modeless categories


def _discover_prompts(prompts_dir: Path) -> list[PromptRef]:
    """Walk _bundled/ and discover all mode prompt files."""
    refs: list[PromptRef] = []
    if not prompts_dir.is_dir():
        return refs

    for system_file in prompts_dir.rglob("system.md"):
        rel = system_file.relative_to(prompts_dir)
        parts = rel.parts

        # Skip non-mode auxiliary files.
        if any(skip in parts for skip in _SKIP_SUBDIRS):
            continue

        category = parts[0]

        # Skip infrastructure categories.
        if category in _SKIP_CATEGORIES:
            continue

        # Must have locale as second component.
        if len(parts) < 2:
            continue

        locale = parts[1]
        # Only check the primary locale for mode registration.
        if locale != "en":
            continue

        # system.md directly under locale → modeless category.
        if len(parts) == 3 and parts[2] == "system.md":
            refs.append(PromptRef(path=system_file, category=category, mode=""))
            continue

        # system.md under mode subdirectory → mode-based prompt.
        if parts[-1] == "system.md" and len(parts) > 3:
            mode = "/".join(parts[2:-1])
            refs.append(PromptRef(path=system_file, category=category, mode=mode))

    return refs


# ── Registry Parsing ───────────────────────────────────────────────────


def _registered_modes(registry: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract (category, mode) pairs from the registry."""
    result: list[tuple[str, str]] = []
    features = cast("dict[str, Any]", registry.get("features", {}))
    for category, cfg in features.items():
        cfg_dict = cast("dict[str, Any]", cfg)
        modes: object = cfg_dict.get("modes")
        if isinstance(modes, dict):
            modes_dict = cast("dict[str, Any]", modes)
            for mode_name in modes_dict:
                result.append((category, str(mode_name)))
        elif isinstance(modes, list) and len(cast("list[Any]", modes)) == 0:
            # Modeless category — no individual modes.
            pass
    return result


# ── Drift Detection ────────────────────────────────────────────────────


def check_registry_drift(
    registry_path: Path | None = None,
    prompts_dir: Path | None = None,
) -> list[DriftFinding]:
    """Detect drift between the registry and the prompt filesystem.

    Parameters
    ----------
    registry_path
        Path to adoption-registry.yaml. Defaults to script's sibling.
    prompts_dir
        Path to ``_bundled/`` directory. Defaults to core prompts.

    Returns
    -------
    list[DriftFinding]
        Ordered by severity: critical → warning → info.
    """
    reg_path = registry_path or _DEFAULT_REGISTRY
    p_dir = prompts_dir or _DEFAULT_PROMPTS
    schema_path = reg_path.parent / _SCHEMA_NAME

    # Load registry.
    registry: dict[str, Any] = yaml.safe_load(reg_path.read_text(encoding="utf-8"))

    # Step 1: Schema validation.
    findings = validate_registry_schema(registry, schema_path)
    if findings:
        return findings  # schema broken → stop early

    # Step 2: Discover prompt files.
    prompt_refs = _discover_prompts(p_dir)

    # Build lookup: (category, mode) → PromptRef
    prompt_map: dict[tuple[str, str], PromptRef] = {}
    for ref in prompt_refs:
        prompt_map[(ref.category, ref.mode)] = ref

    # Also track modeless categories that have prompt files.
    modeless_with_prompts: set[str] = {ref.category for ref in prompt_refs if ref.mode == ""}

    # Step 3: Check registered modes have prompt files.
    registered = _registered_modes(registry)
    registered_set = {(cat, mode) for cat, mode in registered}
    features = cast("dict[str, Any]", registry.get("features", {}))

    for cat, mode in registered:
        if (cat, mode) not in prompt_map:
            findings.append(
                DriftFinding(
                    severity="critical",
                    category=cat,
                    mode=mode,
                    message=f"Registered mode '{mode}' has no prompt file",
                    detail=f"Expected: _bundled/{cat}/en/{mode}/system.md",
                )
            )

    # Step 4: Check modeless categories have their system.md.
    for cat, cfg in features.items():
        cfg_dict = cast("dict[str, Any]", cfg)
        modes = cfg_dict.get("modes")
        if (
            isinstance(modes, list)
            and len(cast("list[Any]", modes)) == 0
            and cat not in modeless_with_prompts
        ):
            findings.append(
                DriftFinding(
                    severity="critical",
                    category=cat,
                    mode="(modeless)",
                    message=f"Modeless category '{cat}' has no prompt file",
                    detail=f"Expected: _bundled/{cat}/en/system.md",
                )
            )

    # Step 5: Check for unregistered prompt files.
    for ref in prompt_refs:
        if ref.category not in features:
            findings.append(
                DriftFinding(
                    severity="warning",
                    category=ref.category,
                    mode=ref.mode,
                    message=f"Category '{ref.category}' not in registry",
                    detail=f"Prompt file: {ref.path}",
                )
            )
        elif ref.mode == "":
            pass  # modeless — already checked
        elif (ref.category, ref.mode) not in registered_set:
            findings.append(
                DriftFinding(
                    severity="warning",
                    category=ref.category,
                    mode=ref.mode,
                    message=f"Mode '{ref.mode}' not registered in '{ref.category}'",
                    detail=f"Prompt file: {ref.path}",
                )
            )

    # Step 6: Info — mode counts.
    for cat, cfg in features.items():
        cfg_dict = cast("dict[str, Any]", cfg)
        modes = cfg_dict.get("modes")
        if isinstance(modes, dict):
            reg_count = len(cast("dict[str, Any]", modes))
            fs_count = sum(1 for r in prompt_refs if r.category == cat and r.mode != "")
            if reg_count == fs_count:
                findings.append(
                    DriftFinding(
                        severity="info",
                        category=cat,
                        mode="",
                        message=f"{cat}: {reg_count} modes registered, {fs_count} prompt files",
                    )
                )

    # Sort: critical first, then warning, then info.
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 9))

    return findings


# ── CLI Entry Point ─────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Run drift detection and print report. Returns exit code."""
    findings = check_registry_drift()

    report = DriftReport(findings=findings)

    for f in findings:
        prefix = {
            "critical": "❌ CRITICAL",
            "warning": "⚠️  WARNING",
            "info": "i INFO",
        }.get(f.severity, "  ?")

        loc = f"{f.category}/{f.mode}" if f.mode else f.category
        print(f"{prefix}: [{loc}] {f.message}")
        if f.detail:
            print(f"         {f.detail}")

    print(f"\n{report.summary()}")

    if report.has_critical:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
