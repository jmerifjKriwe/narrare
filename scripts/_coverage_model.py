"""Data model, classification, and parsing for per-module coverage checks.

Split from check_module_coverage.py to comply with RULE-04 (file size limit).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET  # nosec B405  # CI-generated coverage XML is trusted
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COVERAGE_XML = REPO_ROOT / "coverage.xml"
BASELINES_FILE = REPO_ROOT / "scripts" / "coverage_baselines.json"

# Source roots (relative to repo root).
_CORE_ROOT = REPO_ROOT / "packages" / "core" / "narrare_core"
_API_ROOT = REPO_ROOT / "apps" / "api" / "narrare"

# RULE-10 module coverage targets (from CONSTRAINTS.md).
# These are *aspirational targets* — warnings only until met.
RULE10_TARGETS: dict[str, int] = {
    # Core-only → 90% (llm/prompts → 95%)
    "agents": 90,
    "ai_invocation": 90,
    "ai_invocation.budgets": 90,
    "ai_invocation.enrichers": 90,
    "ai_invocation.evidence": 90,
    "ai_invocation.validators": 90,
    "cache": 90,
    "context": 90,
    "llm": 95,
    "llm._providers": 95,
    "nlp": 90,
    "nlp.languages": 90,
    "nlp.languages.emotions": 90,
    "nlp.languages.pronouns_de": 90,
    "nlp.languages.pronouns_en": 90,
    "nlp.languages.pronouns_fr": 90,
    "profiles": 90,
    "project": 90,
    "schemas": 90,
    "shared": 90,
    "prompts": 95,
    # API-only → 80%
    "_app": 80,
    "auth": 80,
    "chapters": 80,
    "consistency": 80,
    "evidence": 80,
    "generation": 80,
    "metrics": 80,
    "novels": 80,
    "setup": 80,
    "settings": 80,
    "settings.token_limits": 80,
    "tasks": 80,
    "volumes": 80,
    # Shared (both core and API) → 80%
    "analysis": 80,
    "analysis.services": 80,
    "chat": 80,
    "embeddings": 80,
    "events": 80,
    "kb": 80,
    "kb.schemas": 80,
    "memory": 80,
    "planning": 80,
    "planning.adapters": 80,
    "templates": 80,
    "templates.defaults": 80,
    "wiki": 80,
    "writing": 80,
}

# Packages to skip (non-module noise in coverage XML).
_SKIP_PACKAGES: set[str] = {".", "__pycache__"}

# Status constants.
STATUS_MEETS_TARGET = "PASS"
STATUS_BELOW_TARGET = "WARN"
STATUS_REGRESSION = "FAIL"


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


def save_baselines(packages: dict[str, float]) -> None:
    """Save per-package coverage baselines to JSON file."""
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
        # Ratchet first: coverage below the highest-achieved baseline is ALWAYS
        # a regression, even when the RULE-10 target is met. The baseline may
        # only go UP. Checking the target first made the ratchet advisory only.
        if self.coverage_pct < self.baseline:
            return STATUS_REGRESSION
        if self.coverage_pct >= self.target:
            return STATUS_MEETS_TARGET
        return STATUS_BELOW_TARGET

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
        return sum(1 for m in self.modules if m.status == STATUS_BELOW_TARGET)

    @property
    def failed(self) -> int:
        return sum(1 for m in self.modules if m.status == STATUS_REGRESSION)


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
        target = RULE10_TARGETS.get(name, 80)
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
