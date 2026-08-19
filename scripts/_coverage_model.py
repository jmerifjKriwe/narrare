"""Data model, classification, and parsing for per-module coverage checks.

Split from check_module_coverage.py to comply with RULE-04 (file size limit).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET  # nosec B405  # CI-generated coverage XML is trusted
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COVERAGE_XML = REPO_ROOT / "coverage.xml"
BASELINES_FILE = REPO_ROOT / "scripts" / "coverage_baselines.json"

# Source roots (relative to repo root).
_CORE_ROOT = REPO_ROOT / "packages" / "core" / "narrare_core"
_API_ROOT = REPO_ROOT / "apps" / "api" / "narrare"

# Stricter tier for the core/llm/ and core/prompts/ trees (tests/AGENTS.md
# coverage table: 95% minimum) — the only core subtrees above the RULE-10
# core floor of 90%.
_TIER95_CORE_TOPS = frozenset({"llm", "prompts"})

# RULE-10 target overrides: entries that GENUINELY differ from the derived
# default (see ``rule10_target``). Must stay minimal — a test asserts every
# entry differs from its derived value. Targets are aspirational (warnings
# only until met); see ``STATUS_BELOW_TARGET``.
RULE10_OVERRIDES: dict[str, int] = {}

# Packages to skip (non-module noise in coverage XML).
_SKIP_PACKAGES: set[str] = {".", "__pycache__"}

# Status constants.
# BELOW_TARGET is the hard floor (RULE-10 target) — blocking in --fail mode.
# REGRESSION is below baseline but above target — non-blocking warning.
STATUS_MEETS_TARGET = "PASS"
STATUS_REGRESSION = "WARN"
STATUS_BELOW_TARGET = "FAIL"


# ── Source classification ──────────────────────────────────────


def _is_dir_in(root: Path, name: str) -> bool:
    """Check if *name* is a sub-directory or .py file inside *root*."""
    return (root / name).is_dir() or (root / f"{name}.py").is_file()


def classify_package(package_name: str) -> str:
    """Classify a package as ``core``, ``api``, or ``shared``."""
    top = package_name.split(".")[0]
    in_core = _is_dir_in(_CORE_ROOT, top)
    in_api = _is_dir_in(_API_ROOT, top)
    if in_core and in_api:
        return "shared"
    if in_core:
        return "core"
    if in_api:
        return "api"
    return "unknown"


def rule10_target(package_name: str) -> int:
    """Derive the RULE-10 coverage target for *package_name*.

    Policy (docs/_shared/CONSTRAINTS.md §RULE-10 + tests/AGENTS.md):

    - ``core/llm/`` and ``core/prompts/`` trees  → 95
    - other ``core/`` packages                   → 90
    - ``apps/api/``, shared, unknown packages    → 80

    A top-level package named ``llm``/``prompts`` gets the 95 tier whenever
    its tree exists under the core root — even if a same-named api package
    merges into the flattened coverage entry (e.g. ``prompts``), because the
    merged entry still contains the 95%-tier core code. ``RULE10_OVERRIDES``
    entries, if any, take precedence over this derivation.
    """
    top = package_name.split(".")[0]
    if top in _TIER95_CORE_TOPS and _is_dir_in(_CORE_ROOT, top):
        return 95
    if classify_package(package_name) == "core":
        return 90
    return 80


def display_path(package_name: str) -> str:
    """Human-friendly filesystem path for a flattened package name."""
    top = package_name.split(".")[0]
    source = classify_package(package_name)
    if source == "core":
        prefix = "packages/core/narrare_core"
    elif source == "api":
        prefix = "apps/api/narrare"
    else:
        prefix = "packages/core+apps/api"
    rest = package_name[len(top) :]
    return f"{prefix}/{top}{rest.replace('.', '/')}/"


# ── Baselines ──────────────────────────────────────────────────


def load_baselines() -> dict[str, float]:
    """Load per-package coverage baselines from JSON file."""
    if not BASELINES_FILE.exists():
        return {}
    try:
        data = json.loads(BASELINES_FILE.read_text(encoding="utf-8"))
        return dict(data.get("packages", {}))
    except json.JSONDecodeError, KeyError:
        return {}


class BaselineShrinkError(RuntimeError):
    """Raised when updating baselines would remove tracked package keys.

    Triggered when any previously persisted key disappears from the new
    package set — whether by net shrinkage (reduced-scope coverage.xml,
    e.g. only one test directory) or by a drop-plus-addition mix (package
    rename, dead-key cleanup alongside a new capture) that older
    subset-only guards missed. Also raised when ``allow_removed`` names
    keys that are not actually being removed: the allowance is an
    assertion about reality and must match it exactly.

    Deliberate, documented removals opt in via ``allow_removed`` /
    ``--allow-removed <key,...>`` so every ratchet drop is named on the
    command line and auditable.
    """


def save_baselines(
    packages: dict[str, float],
    *,
    allow_removed: Collection[str] = (),
) -> None:
    """Save per-package coverage baselines to JSON file.

    Refuses any key removal unless the removed key set matches
    ``allow_removed`` exactly — see :class:`BaselineShrinkError` for why.
    A value-identical update is a byte-level no-op (the file, including
    its ``updated`` date, is left untouched) so re-running
    ``--update-baselines`` against unchanged coverage cannot drift.
    """
    existing = load_baselines()
    new_keys = set(packages)
    existing_keys = set(existing)
    removed = existing_keys - new_keys
    allowed = set(allow_removed)

    if removed != allowed:
        details: list[str] = []
        unapproved = sorted(removed - allowed)
        overstated = sorted(allowed - removed)
        if unapproved:
            details.append(
                "removed without approval: "
                + ", ".join(unapproved[:10])
                + (f" (+{len(unapproved) - 10} more)" if len(unapproved) > 10 else "")
            )
        if overstated:
            details.append(
                "named in allow_removed but not actually removed: "
                + ", ".join(overstated[:10])
                + (f" (+{len(overstated) - 10} more)" if len(overstated) > 10 else "")
            )
        raise BaselineShrinkError(
            "Refusing to shrink coverage baselines ("
            + "; ".join(details)
            + "). A disappearing key usually means --update-baselines was "
            "run against a reduced-scope coverage.xml (e.g. only one test "
            "directory); run pytest over the full tests/unit/ tree before "
            "updating. If the removal is deliberate (dead or renamed "
            "package), name the keys exactly via --allow-removed <key,...>."
        )

    if packages == existing:
        # Nothing changed — do not rewrite (keeps `updated` date stable
        # and avoids commit noise for a semantically unchanged baseline).
        return

    data = {
        "_comment": (
            "Ratcheted coverage baselines. Updated by check_module_coverage.py --update-baselines."
        ),
        "updated": date.today().isoformat(),
        "packages": dict(sorted(packages.items())),
    }
    BASELINES_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ── Data structures ────────────────────────────────────────────


@dataclass
class ModuleCoverage:
    """Coverage result for a single module/package."""

    package: str
    line_rate: float
    baseline: float
    target: int

    @property
    def coverage_pct(self) -> float:
        return round(self.line_rate * 100, 1)

    @property
    def display_path(self) -> str:
        return display_path(self.package)

    @property
    def source(self) -> str:
        return classify_package(self.package)

    @property
    def status(self) -> str:
        # Target is the hard floor: below the RULE-10 target is always a
        # failure, regardless of baseline. The baseline is a ratchet — a
        # drop below baseline (but still above target) is only a warning.
        if self.coverage_pct < self.target:
            return STATUS_BELOW_TARGET
        if self.coverage_pct < self.baseline:
            return STATUS_REGRESSION
        return STATUS_MEETS_TARGET

    @property
    def meets_target(self) -> bool:
        return self.status == STATUS_MEETS_TARGET

    @property
    def at_baseline(self) -> bool:
        return self.coverage_pct >= self.baseline


@dataclass
class CoverageReport:
    """Aggregated coverage report across all modules."""

    modules: list[ModuleCoverage] = field(default_factory=list[ModuleCoverage])

    @property
    def total(self) -> int:
        return len(self.modules)

    @property
    def passing(self) -> int:
        return sum(1 for m in self.modules if m.meets_target)

    @property
    def warned(self) -> int:
        return sum(1 for m in self.modules if m.status == STATUS_REGRESSION)

    @property
    def failed(self) -> int:
        return sum(1 for m in self.modules if m.status == STATUS_BELOW_TARGET)


# ── XML parsing ────────────────────────────────────────────────


def parse_coverage_xml(xml_path: Path, baselines: dict[str, float]) -> CoverageReport:
    """Parse *xml_path* (coverage.xml) and return a CoverageReport."""
    tree = ET.parse(xml_path)  # nosec B314  # noqa: S314
    root = tree.getroot()
    report = CoverageReport()
    packages_elem = root.find("packages")
    if packages_elem is None:
        return report

    for pkg in packages_elem.findall("package"):
        name = pkg.attrib.get("name", "")
        if name in _SKIP_PACKAGES:
            continue
        line_rate = float(pkg.attrib.get("line-rate", "0"))
        baseline = baselines.get(name, 0.0)
        target = RULE10_OVERRIDES.get(name, rule10_target(name))
        report.modules.append(
            ModuleCoverage(
                package=name,
                line_rate=line_rate,
                baseline=baseline,
                target=target,
            )
        )

    report.modules.sort(key=lambda m: m.package)
    return report
