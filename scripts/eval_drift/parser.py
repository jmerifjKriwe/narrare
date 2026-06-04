"""Promptfoo result parsing and data structures for eval drift checking.

Handles loading, parsing, and grouping of promptfoo v3 JSON output files
into structured data objects for baseline comparison.

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

# ── Constants ──────────────────────────────────────────────────

# Three parents up: eval_drift/parser.py -> eval_drift/ -> scripts/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RESULTS_DIR = REPO_ROOT / "evals" / "results"
DEFAULT_BASELINES_DIR = REPO_ROOT / "evals" / "baselines"
DEFAULT_THRESHOLD = 0.05
BASELINE_VERSION = 1


# ── Data structures ────────────────────────────────────────────


@dataclass
class TestCaseScore:
    """Aggregated scores for a single test case across multiple runs."""

    name: str
    scores: list[float] = field(default_factory=list[float])
    successes: list[bool] = field(default_factory=list[bool])

    @property
    def avg_score(self) -> float:
        """Mean score across all runs (0.0 if no runs)."""
        if not self.scores:
            return 0.0
        return sum(self.scores) / len(self.scores)

    @property
    def success_rate(self) -> float:
        """Fraction of runs that passed (0.0 if no runs)."""
        if not self.successes:
            return 0.0
        return sum(1 for s in self.successes if s) / len(self.successes)

    @property
    def run_count(self) -> int:
        """Number of individual runs recorded."""
        return len(self.scores)


@dataclass
class EvalResultFile:
    """Parsed results from a single promptfoo output file."""

    source: str  # filename stem, e.g. "writing-generation"
    test_cases: list[TestCaseScore] = field(default_factory=list[TestCaseScore])

    @property
    def avg_score(self) -> float:
        """Mean score across all test cases (0.0 if none)."""
        if not self.test_cases:
            return 0.0
        scores = [tc.avg_score for tc in self.test_cases]
        return sum(scores) / len(scores)


# ── JSON loading helper ────────────────────────────────────────


def load_json_object(path: Path) -> dict[str, Any] | None:
    """Load a JSON file as a typed dict.

    Returns ``None`` if the file does not exist, cannot be read,
    contains invalid JSON, or the top-level value is not a dict.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError, OSError:
        return None
    if isinstance(data, dict):
        return cast("dict[str, Any]", data)
    return None


# ── Result file discovery ──────────────────────────────────────


def find_result_files(results_dir: Path) -> list[Path]:
    """Find all JSON result files in *results_dir*, sorted by name."""
    if not results_dir.is_dir():
        return []
    return sorted(p for p in results_dir.glob("*.json") if p.is_file())


# ── promptfoo output parsing ───────────────────────────────────


def _vars_key(vars_dict: dict[str, Any]) -> str:
    """Create a stable hashable key from a vars dict for grouping."""
    return json.dumps(vars_dict, sort_keys=True, ensure_ascii=False)


def _make_test_case_name(vars_dict: dict[str, Any]) -> str:
    """Create a human-readable name from test case variables."""
    if not vars_dict:
        return "default"
    # Use first 2 variable values as a concise name
    parts: list[str] = []
    for value in list(vars_dict.values())[:2]:
        text = str(value)
        # Truncate long values
        if len(text) > 60:
            text = text[:57] + "..."
        parts.append(text)
    return " / ".join(parts)


def _extract_score(entry: dict[str, Any]) -> float:
    """Extract a numeric score from a promptfoo result entry."""
    # Direct score field (0-1 scale)
    score = entry.get("score")
    if isinstance(score, (int, float)):
        return float(score)

    # Fallback: average gradingResults scores
    grading_raw = entry.get("gradingResults")
    if isinstance(grading_raw, list) and grading_raw:
        grading = cast("list[dict[str, Any]]", grading_raw)
        scores: list[float] = []
        for g in grading:
            s = g.get("score")
            if isinstance(s, (int, float)):
                scores.append(float(s))
        if scores:
            return sum(scores) / len(scores)

    # Final fallback: derive from success boolean
    return 1.0 if entry.get("success") else 0.0


def parse_promptfoo_results(filepath: Path) -> EvalResultFile:
    """Parse a promptfoo v3 JSON output file into an EvalResultFile.

    Handles the standard promptfoo output format gracefully.  If the
    file is malformed or uses an unknown schema, returns an
    EvalResultFile with zero test cases rather than raising.
    """
    source = filepath.stem
    data = load_json_object(filepath)
    if data is None:
        return EvalResultFile(source=source)

    # promptfoo v3 stores results in "results" array
    raw_results_raw = data.get("results")
    if not isinstance(raw_results_raw, list):
        return EvalResultFile(source=source)
    raw_results = cast("list[dict[str, Any]]", raw_results_raw)

    # Group results by vars dict (each test case may have multiple runs)
    groups: dict[str, TestCaseScore] = {}

    for entry in raw_results:
        vars_raw = entry.get("vars", {})
        vars_dict: dict[str, Any] = (
            cast("dict[str, Any]", vars_raw) if isinstance(vars_raw, dict) else {}
        )

        key = _vars_key(vars_dict)
        if key not in groups:
            groups[key] = TestCaseScore(name=_make_test_case_name(vars_dict))

        groups[key].scores.append(_extract_score(entry))
        groups[key].successes.append(bool(entry.get("success", True)))

    return EvalResultFile(
        source=source,
        test_cases=list(groups.values()),
    )
