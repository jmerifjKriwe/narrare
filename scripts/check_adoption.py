#!/usr/bin/env python3
"""
Narrare Feature Adoption Score — CI script.

Computes per-category and overall adoption scores based on the
adoption registry and bundled prompt files.

Exit codes:
    0: Score >= 0.85 (PASS)
    2: Score 0.70-0.85 (WARN)
    1: Score < 0.70 (FAIL)

Usage:
    python scripts/check_adoption.py
    python scripts/check_adoption.py --json
    python scripts/check_adoption.py --help

The orchestration logic lives in ``scripts/adoption/cli.py`` (extracted
for RULE-04/RULE-06 compliance). Helper functions ``load_registry`` and
``adoption_debt_fingerprints`` remain here for test compatibility — tests
import this module and monkeypatch them.

See: docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

# Allow importing from scripts/ and the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from adoption.mode2_validation import Mode2ValidationReport as Mode2ValidationReport
from adoption.mode2_validation import validate_adoption_mode2 as validate_adoption_mode2
from adoption.prompt_path_adoption import check_prompt_path_adoption as check_prompt_path_adoption
from adoption.scorer import compute_adoption_report as compute_adoption_report
from adoption.script_evidence_repo import ScriptEvidenceRepository as ScriptEvidenceRepository
from prompt_checks_crossfile import discover_prompts as discover_prompts
from scripts.architecture.baselines import compare_section as compare_section
from scripts.architecture.baselines import format_comparison as format_comparison
from scripts.architecture.baselines import stable_fingerprint as stable_fingerprint

if TYPE_CHECKING:
    from adoption.scorer import AdoptionReport

# ── Constants ──────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "scripts" / "architecture" / "adoption-registry.yaml"
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
ADOPTION_BASELINE_SECTION = "adoption_debt"
DEFAULT_EVIDENCE_REPO_FILE = ROOT / ".evidence" / "invocations.jsonl"


def adoption_debt_fingerprints(report: AdoptionReport) -> set[str]:
    """Return stable fingerprints for non-failing adoption debt."""
    items: set[str] = set()
    for category in report.categories:
        if category.status == "WARN":
            items.add(stable_fingerprint(category.category, "status", category.status))
        for missing in category.missing_must:
            items.add(stable_fingerprint(category.category, "missing_must", missing))
        for missing in category.missing_should:
            items.add(stable_fingerprint(category.category, "missing_should", missing))
        for prompt_key, locales in category.missing_locales.items():
            for locale in locales:
                items.add(
                    stable_fingerprint(category.category, "missing_locale", prompt_key, locale)
                )
        if category.inline_fallbacks:
            items.add(
                stable_fingerprint(
                    category.category,
                    "inline_fallback_count",
                    category.inline_fallbacks,
                )
            )
        # Mode-level fingerprints for runtime gaps.
        for mode in category.modes:
            if mode.static_verified and not mode.runtime_verified:
                for rd in mode.runtime_details:
                    if rd.evidence_status != "verified":
                        items.add(
                            stable_fingerprint(
                                category.category,
                                mode.mode,
                                "runtime",
                                rd.requirement,
                                rd.evidence_status,
                            )
                        )
            if mode.static_verified and not mode.adopted:
                items.add(stable_fingerprint(category.category, mode.mode, "not_adopted"))
    return items


# ── Registry loading ───────────────────────────────────────────────


def load_registry(path: Path) -> dict[str, Any]:
    """Load the adoption registry YAML."""
    if not path.exists():
        print(f"ERROR: Adoption registry not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not data or not isinstance(data, dict):
        print("ERROR: Adoption registry is not a valid YAML mapping", file=sys.stderr)
        sys.exit(1)
    return cast("dict[str, Any]", data)


# ── CLI orchestration (extracted to scripts/adoption/cli.py) ───────

from scripts.adoption.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
