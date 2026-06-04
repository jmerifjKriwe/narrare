"""Test coverage gap analysis package.

Checks that service/repository files have corresponding test files,
as required by RULE-10. Detects the *absence* of test files and low
test-to-method ratios.

Usage:
    python scripts/check_test_coverage_gaps.py
    python scripts/check_test_coverage_gaps.py --json
    python scripts/check_test_coverage_gaps.py --fail-on-missing

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from .discovery import AnalysisConfig, SourceFile, discover_source_files
from .mapping import find_test_files
from .reporting import format_json, format_report

__all__ = [
    "AnalysisConfig",
    "SourceFile",
    "discover_source_files",
    "find_test_files",
    "format_json",
    "format_report",
]
