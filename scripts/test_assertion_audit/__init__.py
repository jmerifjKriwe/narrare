"""Test assertion quality audit package.

Scans Python test files for weak assertion patterns using AST-based analysis.
Detects trivial truthy checks, missing schema validation, pytest.raises
without match parameters, and other low-quality test assertions.

Usage:
    python scripts/audit_test_assertions.py
    python scripts/audit_test_assertions.py --path tests/unit/ --top-n 10
    python scripts/audit_test_assertions.py --json report.json --fail-on 0.5
"""

from .models import AuditReport, FileReport, Finding, WeaknessCategory
from .scanner import scan_directory, scan_file

__all__ = [
    "AuditReport",
    "FileReport",
    "Finding",
    "WeaknessCategory",
    "scan_directory",
    "scan_file",
]
