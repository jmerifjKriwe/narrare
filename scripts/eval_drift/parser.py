"""Pydantic Evals report parsing and data structures for drift checking.

Handles Narrare's serialized Pydantic Evals summaries and converts them into
structured data objects for baseline comparison.

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
DEFAULT_PRIORITIES_FILE = REPO_ROOT / "evals" / "p0_priorities.json"
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
    """Parsed results from a single Pydantic Evals report file."""

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
    except (
        json.JSONDecodeError,
        OSError,
    ):
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


# ── Pydantic Evals report parsing ──────────────────────────────


def _extract_case_score(entry: dict[str, Any]) -> float:
    """Extract a numeric score from a serialized report case."""

    scores_raw: object = entry.get("scores")
    if isinstance(scores_raw, dict):
        score_values = cast("dict[object, object]", scores_raw).values()
        scores = [value for value in score_values if isinstance(value, (int, float))]
        if scores:
            return sum(float(value) for value in scores) / len(scores)

    assertions_raw: object = entry.get("assertions")
    if isinstance(assertions_raw, dict) and assertions_raw:
        assertion_values = cast("dict[object, object]", assertions_raw).values()
        assertions = [bool(value) for value in assertion_values]
        return sum(1 for value in assertions if value) / len(assertions)

    return 0.0


def parse_pydantic_eval_report(filepath: Path) -> EvalResultFile:
    """Parse a Narrare Pydantic Evals JSON summary into an EvalResultFile."""

    source = filepath.stem
    data = load_json_object(filepath)
    if data is None:
        return EvalResultFile(source=source)

    cases_raw = data.get("cases")
    if not isinstance(cases_raw, list):
        return EvalResultFile(source=source)
    cases = cast("list[dict[str, Any]]", cases_raw)

    test_cases: list[TestCaseScore] = []
    for entry in cases:
        name_raw = entry.get("name")
        name = name_raw if isinstance(name_raw, str) and name_raw else "default"
        test_case = TestCaseScore(name=name)
        test_case.scores.append(_extract_case_score(entry))
        test_case.successes.append(True)
        test_cases.append(test_case)

    return EvalResultFile(source=source, test_cases=test_cases)
