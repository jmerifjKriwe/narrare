"""Narrare Eval Baseline Drift Checker.

Compares the latest promptfoo eval results against stored baselines and
fails if any test case score drops more than a configurable threshold.

Usage:
    python scripts/check_eval_drift.py                        # human-readable
    python scripts/check_eval_drift.py --json                 # JSON for CI
    python scripts/check_eval_drift.py --threshold 0.10       # 10 % tolerance
    python scripts/check_eval_drift.py --update-baselines     # create baselines

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from .comparison import (
    DriftComparison,
    DriftReport,
    compare_against_baselines,
    load_baseline,
    update_baselines,
)
from .parser import (
    DEFAULT_BASELINES_DIR,
    DEFAULT_RESULTS_DIR,
    DEFAULT_THRESHOLD,
    EvalResultFile,
    TestCaseScore,
    find_result_files,
    parse_promptfoo_results,
)
from .reporting import print_human_report, print_json_report

__all__ = [
    "DEFAULT_BASELINES_DIR",
    "DEFAULT_RESULTS_DIR",
    "DEFAULT_THRESHOLD",
    "DriftComparison",
    "DriftReport",
    "EvalResultFile",
    "TestCaseScore",
    "compare_against_baselines",
    "find_result_files",
    "load_baseline",
    "parse_promptfoo_results",
    "print_human_report",
    "print_json_report",
    "update_baselines",
]
